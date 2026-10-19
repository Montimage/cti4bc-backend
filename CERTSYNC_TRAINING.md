# CERT-Synchrony training integration

This branch adds an optional webinar integration. `CERTSYNC_TRAINING_ENABLED=false`
(the default), or an empty SSO secret, retains normal CTI4BC authentication,
visibility, sharing output and topic parsing. No production credentials or
cryptography keys are included. Coordinate deployment with Valeria and the
colleague maintaining CTI4BC.

## Configuration

| Setting | Value |
| --- | --- |
| `CERTSYNC_TRAINING_ENABLED` | `true` to enable |
| `CTI4BC_SSO_SECRET` | Distinct random secret, at least 32 UTF-8 bytes; shared with the platform and simulator |
| `CERTSYNC_PLATFORM_MISP_URL` | Exact URL of the existing platform MISP A server record; trailing slash ignored |
| `CERTSYNC_FRAME_ANCESTORS` | One HTTPS platform origin; default `https://certsync-platform.montimage.eu` |
| `TRAINING_ORG_PREFIX` / `TRAINING_ORG_COUNT` | `TRAIN-` / `25`; count 1–99; identical on the platform and simulator |

Apply `python manage.py migrate`. `certsync_training` owns two small tables:
consumed JWT receipts and platform identities. Keep these database tables across
container restarts: deleting receipts before expiry permits replay.

## Organisations and Kafka

```sh
python manage.py certsync_training_orgs --misp-server-id 1 --misp-org-id 7
```

Replace both example IDs. The first identifies the existing platform MISP
configuration; the second is the **fictional CI creator's organisation in MISP A**,
accessible to that server's key. The command validates the server URL, creates or
updates `TRAIN-01 → T01` through `TRAIN-25 → T25`, grants that server to each, and
prints the mapping. It neither prints keys nor contacts MISP. The prefix is ≤10
characters and unique. Resolve prefix/name collisions rather than repurposing a
partner's organisation.

The old consumer subscribes to a fixed list and seeks to the end on startup. In
training mode, consumer startup derives **all organisations' security-alert
topics**, including `T04.HEALTHCI.security_alerts`. Playbooks remain on
`T04.SOAR4BC.playbook`, read by the existing alert handler. Startup waits for
partition assignment before declaring readiness. The old `UC...` alert prefix
parser is widened only in training mode.

Run this deployment as **one CTI4BC web process**: the consumer manager already
lives in process memory. Multiple web workers would create separate consumers.
Restart the web process after adding organisations, before participants start;
no active consumer is silently replaced. Provision both Kafka topics for every
training prefix when broker auto-creation is disabled. The simulator calls
`POST /api/certsync-training/consumer-ready/` before publication and does not stop
or retarget the shared consumer. A normal administrator can also start it through
the existing Kafka page.

## Sign-on and permissions

`POST /api/certsync-training/sso/` accepts JSON `{ "token": "..." }` from the GUI.
Tokens require HS256, issuer `certsync-platform`, exact audience
`certsync-cti4bc`, a maximum 60-second lifetime, 30-second clock leeway, and a
single-use `jti`. Receipts are transactional database rows. Token values are not
logged. Errors say “Open this from the platform's Training tab”. Responses are
not cached.

An operator maps to `platform-<sub>`, with an unusable password and membership of
exactly their configured training organisation. An administrator gets a separate
platform-derived staff/superuser account. Existing ordinary accounts are never
taken over. Each successful sign-on replaces that identity's session generation;
older access **and refresh** tokens are refused.

The simulator uses the same CTI4BC audience/secret to obtain an **operator**
identity `platform-simulator-<platform sub>` in the same training organisation.
This keeps its readback session separate from the trainee's browser session.
It does not use an administrator login.

Event lists/details already enforce membership in upstream CTI4BC. A new
middleware boundary additionally blocks training settings, Kafka controls,
unrelated health/media routes and writes to MISP configuration. Attachment
readback and event update routes check the event's organisation. Training shares
(single or aggregated) reject organisation forwarding and any MISP destination
other than the configured platform server. Only the outgoing copy receives
`certsync:destination-org="TRAIN-XX"`; existing other tags are preserved, existing
destination tags are replaced, and stored event data is unchanged. No other
certsync tags are added. Normal sharing output remains unchanged when off.

## Cleanup and tests

```sh
python manage.py certsync_training_cleanup          # dry run
python manage.py certsync_training_cleanup --apply
```

Only events whose organisation **name and mapped prefix** match training are
selected; associated share logs/playbooks/attachment database rows follow their
existing cascades. Users, organisations, sign-on receipts and partner events
remain. Platform/MISP cleanup is a separate command in the platform repository.

The upstream test modules are placeholders (zero runnable tests). The added
Django integration tests use SQLite and synthetic settings, without loading
`.env` or contacting Kafka/MISP:

```sh
PYTHONPATH=../src python manage.py test certsync_training \
  --settings=certsync_training.offline_settings
python manage.py makemigrations certsync_training --check --dry-run \
  --settings=certsync_training.offline_settings
```

Install the normal application dependencies first. External sharing is mocked;
no real cryptography key is opened. See the workspace
`guides/TRAINING_SIMULATOR_VPS.md` for deployment and rollback.
