import io
import time
import uuid
from copy import deepcopy
from unittest.mock import AsyncMock, patch

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from organizations.models import Organization
from event.models import Event
from misp_servers.models import MISPServer
from .models import PlatformIdentity, TokenReceipt
from .contract import addressed_copy


def token(**overrides):
    now = int(time.time())
    claims = dict(iss='certsync-platform', aud='certsync-cti4bc', sub='42', name='trainee',
                  role='operator', org='TRAIN-04', iat=now, exp=now + 60, jti=uuid.uuid4().hex)
    claims.update(overrides)
    return jwt.encode(claims, settings.CTI4BC_SSO_SECRET, algorithm='HS256')


class IntegrationTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='TRAIN-04', prefix='T04', external_id='7')
        self.other = Organization.objects.create(name='TRAIN-05', prefix='T05', external_id='7')
        self.server = MISPServer.objects.create(name='Platform', url='https://misp.example', apikey='synthetic')
        self.server.organizations.add(self.org)
        self.foreign = MISPServer.objects.create(name='Partner', url='https://partner.example', apikey='synthetic')
        self.foreign.organizations.add(self.org)
        self.client = APIClient()

    def signon(self, **claims):
        result = self.client.post('/api/certsync-training/sso/', {'token': token(**claims)}, format='json')
        self.assertEqual(result.status_code, 200, result.data)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + result.data['access'])
        return result

    def test_signon_reuses_user_exact_membership_and_revokes_old_session(self):
        first = self.signon()
        user = get_user_model().objects.get(username='platform-42')
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_staff)
        user.organizations.add(self.other)
        second = self.signon()
        self.assertEqual(get_user_model().objects.filter(username='platform-42').count(), 1)
        self.assertEqual(list(user.organizations.values_list('name', flat=True)), ['TRAIN-04'])
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + first.data['access'])
        self.assertEqual(self.client.get('/event/').status_code, 403)
        self.assertEqual(self.client.post('/api/token/refresh/', {'refresh': first.data['refresh']}).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + second.data['access'])
        self.assertEqual(self.client.get('/event/').status_code, 200)

    def test_replay_durable_receipt_and_cross_audience(self):
        signed = token()
        self.assertEqual(self.client.post('/api/certsync-training/sso/', {'token': signed}).status_code, 200)
        self.assertEqual(TokenReceipt.objects.count(), 1)
        self.assertEqual(APIClient().post('/api/certsync-training/sso/', {'token': signed}).status_code, 403)
        for audience in ('certsync-simulator', 'certsync-anonymizer'):
            self.assertEqual(self.client.post('/api/certsync-training/sso/', {'token': token(aud=audience)}).status_code, 403)
        self.assertEqual(self.client.post('/api/certsync-training/sso/', {'token': token(exp=int(time.time())-40, iat=int(time.time())-100)}).status_code, 403)
        self.assertEqual(self.client.post('/api/certsync-training/sso/', {'token': token(org='CERT-FR')}).status_code, 403)

    def test_admin_and_service_identity_are_separate(self):
        self.signon(role='admin', org='')
        self.assertTrue(get_user_model().objects.get(username='platform-42').is_superuser)
        self.signon(sub='simulator-42')
        service = get_user_model().objects.get(username='platform-simulator-42')
        self.assertFalse(service.is_staff)
        self.assertEqual(list(service.organizations.all()), [self.org])

    def test_visibility_and_other_routes_fail_closed(self):
        own = Event.objects.create(organization=self.org, data={'info': 'Own event'})
        other = Event.objects.create(organization=self.other, data={'info': 'Other event'})
        self.signon()
        response = self.client.get('/event/')
        self.assertEqual([e['id'] for e in response.json()['events']], [own.pk])
        self.assertEqual(self.client.get(f'/event/{own.pk}/').status_code, 200)
        self.assertEqual(self.client.get(f'/event/{other.pk}/').status_code, 403)
        self.assertEqual(self.client.get(f'/event/{own.pk}').status_code, 301)
        for path in ('/consumer/env/', '/consumer/messages/', '/organizations/summary/', '/api/health/external-services/', '/media/anything'):
            self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.post('/misp_servers/', {}).status_code, 403)
        self.assertEqual(self.client.post(f'/event/update_risk_profile/{other.pk}/', {}).status_code, 403)
        user = get_user_model().objects.get(username='platform-42')
        user.is_staff = True
        user.save()
        user.organizations.add(self.other)
        self.assertEqual([e['id'] for e in self.client.get('/event/').json()['events']], [own.pk])
        self.assertEqual(self.client.get(f'/event/{other.pk}/').status_code, 403)
        self.assertEqual(self.client.get('/event/')['Content-Security-Policy'], 'frame-ancestors https://platform.example')
        available = self.client.get(f'/misp_servers/for-event/{own.pk}/').json()
        self.assertEqual([s['id'] for s in available], [self.server.pk])
        self.assertNotIn('apikey', available[0])

    def test_real_share_endpoint_restricts_and_tags_only_the_copy(self):
        original = {'info': 'Fictional incident', 'Attribute': {'AWARE4BC': []}}
        event = Event.objects.create(organization=self.org, data=deepcopy(original))
        self.signon()
        data = dict(date={'value': '2026-10-20', 'action': '%Y-%m-%d'}, info='Fictional incident',
            org_id=7, orgc_id=7, analysis='0', distribution='0', threat_level_id='1', event_creator_email='training@hospital.example',
            misp_server_ids=[self.server.pk], Attribute={'AWARE4BC': []})
        with patch('event.views.configure_anonymization_module', return_value=True), patch('event.utils_sharing._run_sharing_tasks', new_callable=AsyncMock) as sharing:
            sharing.return_value = [{'success': True, 'server_id': self.server.pk}]
            response = self.client.post(f'/event/share/{event.pk}/', data, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            pushed = sharing.call_args.args[2]
            self.assertEqual(pushed['Tag'], [{'name': 'certsync:destination-org="TRAIN-04"'}])
            event.refresh_from_db()
            self.assertEqual(event.data, original)
            data['misp_server_ids'] = [self.foreign.pk]
            self.assertEqual(self.client.post(f'/event/share/{event.pk}/', data, format='json').status_code, 403)
            data['misp_server_ids'] = [self.server.pk]
            data['organization_ids'] = [self.other.pk]
            self.assertEqual(self.client.post(f'/event/share/{event.pk}/', data, format='json').status_code, 403)
            self.assertEqual(sharing.call_count, 1)

    def test_off_preserves_sharing_payload(self):
        data = {'info': 'Existing', 'Tag': [{'name': 'tlp:amber'}], 'Attribute': []}
        with override_settings(CERTSYNC_TRAINING_ENABLED=False):
            copied = addressed_copy(data, 'TRAIN-04', [{'url': 'https://elsewhere.example'}], [{'id': 99}])
            self.assertIs(copied, data)
            from event.utils_sharing import share_all
            with patch('event.utils_sharing._run_sharing_tasks', new_callable=AsyncMock) as sharing:
                sharing.return_value = [{'success': True}]
                share_all([{'url': 'https://elsewhere.example'}], [], data)
                self.assertIs(sharing.call_args.args[2], data)
            self.assertEqual(self.client.post('/api/certsync-training/sso/', {'token': token()}).status_code, 404)

    def test_cleanup_dry_run_and_apply(self):
        own = Event.objects.create(organization=self.org, data={})
        real_org = Organization.objects.create(name='Hospital', prefix='HOSP', external_id='7')
        real = Event.objects.create(organization=real_org, data={})
        out = io.StringIO()
        call_command('certsync_training_cleanup', stdout=out)
        self.assertIn('Dry run: 1', out.getvalue())
        self.assertTrue(Event.objects.filter(pk=own.pk).exists())
        call_command('certsync_training_cleanup', apply=True, stdout=io.StringIO())
        self.assertFalse(Event.objects.filter(pk=own.pk).exists())
        self.assertTrue(Event.objects.filter(pk=real.pk).exists())

    def test_org_setup_is_repeatable_and_grants_only_platform_server(self):
        with override_settings(TRAINING_ORG_COUNT=5):
            for _ in range(2):
                call_command('certsync_training_orgs', misp_server_id=self.server.pk, misp_org_id='7', stdout=io.StringIO())
            self.assertEqual(Organization.objects.filter(name__startswith='TRAIN-').count(), 5)
            self.assertEqual(self.server.organizations.count(), 5)

    def test_copy_has_exactly_one_destination_and_keeps_other_tags(self):
        data = {'Tag': [{'name': 'certsync:destination-org="TRAIN-05"'}, {'name': 'tlp:amber'}]}
        result = addressed_copy(data, 'TRAIN-04', [{'url': 'https://misp.example'}], [])
        self.assertEqual(result['Tag'], [{'name': 'tlp:amber'}, {'name': 'certsync:destination-org="TRAIN-04"'}])
        self.assertEqual(data['Tag'][0]['name'], 'certsync:destination-org="TRAIN-05"')

    def test_consumer_topics_include_training_orgs_and_require_assignment(self):
        from unittest.mock import Mock
        from certsync_training.consumer import all_topics, ensure_consumer
        topics = ['T04.HEALTHCI.security_alerts', 'T05.HEALTHCI.security_alerts']
        self.assertEqual(all_topics(), topics)
        manager = Mock(topics=topics, assigned_topics={topics[0]})
        manager.thread.is_alive.return_value = True
        manager.ready_event.is_set.return_value = True
        with patch('cti4bc_backend.kafka_views.consumer_manager', manager):
            self.assertFalse(ensure_consumer(timeout=0)[0])
            manager.assigned_topics = set(topics)
            self.assertTrue(ensure_consumer(timeout=0)[0])
            Organization.objects.create(name='TRAIN-06', prefix='T06', external_id='7')
            self.assertFalse(ensure_consumer(timeout=0)[0])
            manager.stop.assert_not_called()

    def test_training_topic_parser_and_original_off_parser(self):
        from event.views import new_security_alert
        with patch('event.views.parse_alert_message', side_effect=ValueError('synthetic parse stop')):
            with self.assertLogs('event.views', level='ERROR'):
                self.assertEqual(new_security_alert('{}', 'T04.HEALTHCI.security_alerts').status_code, 400)
            with override_settings(CERTSYNC_TRAINING_ENABLED=False):
                with self.assertRaises(Organization.DoesNotExist):
                    new_security_alert('{}', 'T04.HEALTHCI.security_alerts')
