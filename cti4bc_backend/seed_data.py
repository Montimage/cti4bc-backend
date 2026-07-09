"""
CTI4BC — Comprehensive Seed Script
Run: docker compose exec web python /app/cti4bc_backend/seed_data.py
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cti4bc_backend.settings')
django.setup()

from datetime import timedelta, datetime
from django.contrib.auth.models import User
from django.utils import timezone
from organizations.models import Organization, Sector
from event.models import Event, EventShareLog
from forms.models import Form, FormAnswer
from reports.models import Report
from playbook.models import Playbook
from misp_servers.models import MISPServer
from strategies.models import Strategy

now = timezone.now()

def h(h): return timedelta(hours=h)
def m(m): return timedelta(minutes=m)
def d(d): return timedelta(days=d)

# ─────────────────────────────────────────────────────────
# 1. USERS
# ─────────────────────────────────────────────────────────
print("1/10  Users...")
users = {}
for uname, email, first, last, staff in [
    ("admin",    "admin@cti4bc.local",     "Admin",    "CTI4BC",  True),
    ("analyst1", "sophie@montimage.com",   "Sophie",   "Martin",  True),
    ("analyst2", "lucas@montimage.com",    "Lucas",    "Bernard", True),
    ("analyst3", "claire@montimage.com",   "Claire",   "Moreau",  True),
    ("viewer1",  "emma@rte-france.com",    "Emma",     "Dubois",  False),
    ("viewer2",  "jean@sncf.fr",           "Jean",     "Leroy",   False),
    ("viewer3",  "marie@chu-paris.fr",     "Marie",    "Petit",   False),
    ("op1",      "hugo@amundi.com",        "Hugo",     "Garnier", False),
    ("op2",      "laura@montimage.com",    "Laura",    "Rousseau",False),
    ("auditor",  "audit@anssi.gouv.fr",    "Philippe", "Durand",  True),
]:
    u, created = User.objects.get_or_create(
        username=uname,
        defaults={"email": email, "first_name": first, "last_name": last,
                  "is_staff": staff, "is_active": True}
    )
    if created:
        u.set_password("password123")
        u.save()
    users[uname] = u
print(f"   {User.objects.count()} users")

# ─────────────────────────────────────────────────────────
# 2. SECTORS (NIS2)
# ─────────────────────────────────────────────────────────
print("2/10  Sectors...")
sectors = {}
for code, name, annex in [
    ("energy",           "Energy",                "essential"),
    ("transport",        "Transport",             "essential"),
    ("banking",          "Banking",               "essential"),
    ("health",           "Health",                "essential"),
    ("drinking-water",   "Drinking Water",        "essential"),
    ("wastewater",       "Wastewater",            "essential"),
    ("digital-infra",    "Digital Infrastructure", "essential"),
    ("ict-service",      "ICT Service Management","important"),
    ("public-admin",     "Public Administration",  "important"),
    ("space",            "Space",                  "essential"),
    ("food",             "Food Production",        "important"),
    ("chemical",         "Chemical Industry",      "important"),
    ("waste-mgmt",       "Waste Management",       "important"),
    ("research",         "Research",               "important"),
]:
    s, _ = Sector.objects.get_or_create(code=code, defaults={"name": name, "annex": annex})
    sectors[code] = s
print(f"   {len(sectors)} sectors")

# ─────────────────────────────────────────────────────────
# 3. ORGANIZATIONS
# ─────────────────────────────────────────────────────────
print("3/10  Organizations...")
orgs = {}
org_defs = [
    ("MONT",  "Montimage",            "Cybersecurity research & innovation", "info@montimage.com",              ["digital-infra","ict-service","research"], ["analyst1","analyst2","analyst3","op2","admin"]),
    ("RTE",   "RTE Réseau",           "Electricity transmission operator",    "contact@rte-france.com",         ["energy"],                                ["viewer1","analyst1"]),
    ("SNCF",  "SNCF Connect",         "Railway transport operator",          "security@sncf.fr",               ["transport"],                             ["viewer2","analyst2"]),
    ("CHUP",  "CHU Paris",            "University Hospital Center",          "dsi@chu-paris.fr",               ["health"],                                ["viewer3","op1"]),
    ("AMUN",  "Amundi",               "European asset management",           "soc@amundi.com",                 ["banking"],                               ["op1","analyst1"]),
    ("EDF",   "Électricité de France","Energy production & distribution",     "soc@edf.fr",                     ["energy"],                                ["analyst2","viewer1"]),
    ("ORANGE","Orange Business",      "Telecommunications provider",         "cert@orange.com",                ["digital-infra","ict-service"],           ["analyst3","op2"]),
    ("AIRFR", "Air France",           "Airline operator",                    "security@airfrance.fr",          ["transport","digital-infra"],             ["viewer2"]),
    ("VINCI", "Vinci Airports",       "Airport infrastructure",              "soc@vinci.com",                  ["transport","energy"],                    ["analyst1"]),
    ("SANOFI","Sanofi",               "Pharmaceutical company",              "cyber@sanofi.com",               ["health","chemical"],                     ["op1","analyst3"]),
]
for prefix, name, desc, email, sk, uk in org_defs:
    o, _ = Organization.objects.get_or_create(
        prefix=prefix,
        defaults={"name": name, "description": desc, "email": email, "external_id": f"misp-org-{prefix.lower()}"}
    )
    for s in sk:
        o.sectors.add(sectors[s])
    for u in uk:
        o.users.add(users[u])
    orgs[prefix] = o
print(f"   {Organization.objects.count()} organizations")

# ─────────────────────────────────────────────────────────
# 4. EVENTS (30+ events, all statuses)
# ─────────────────────────────────────────────────────────
print("4/10  Events...")

def create_event(org, data, shared, shared_at=None, arrival=None, timeliness=None,
                 extension_time=None, anon_time=None, sharing_speed=None):
    ev, _ = Event.objects.get_or_create(
        organization=org,
        data=data,
        defaults={
            "shared": shared,
            "shared_at": shared_at,
            "arrival_time": arrival,
            "timeliness": timeliness,
            "extension_time": extension_time,
            "anon_time": anon_time,
            "sharing_speed": sharing_speed,
        }
    )
    return ev

events = []

# ── Category: Ransomware (5 events) ──
events.append(create_event(orgs["MONT"], {
    "type": "incident", "category": "ransomware",
    "title": "LockBit 3.0 ransomware targeting European energy infrastructure",
    "description": "LockBit 3.0 ransomware variant deployed via phishing campaign targeting IT administrators in energy sector. Encryption of backup servers before main payload execution indicates sophisticated attack chain.",
    "severity": "critical",
    "indicators": {
        "ip": ["185.220.101.45", "194.26.29.120", "185.56.83.0/24"],
        "domain": ["lockbit3[.]xyz", "pay-us[.]onion", "leak-news[.]com"],
        "hash": ["e5d88a2cc3237deb70f9d0dc26d1358c", "a1b2c3d4e5f6789012345678deadbeef"],
        "email": ["ransom@[].onion"]
    },
    "mitre_attack": ["T1486", "T1566.001", "T1071.001", "T1490"],
    "source": "Montimage SOC", "timestamp": "2026-07-01T09:15:00Z",
    "tlp": "amber",
    "confidence": 95,
    "related_events": [],
    "affected_sectors": ["energy"],
}, True, shared_at=now-h(72), arrival=now-h(74), timeliness=h(2),
   extension_time=h(1), anon_time=m(45), sharing_speed=m(30)))

events.append(create_event(orgs["EDF"], {
    "type": "incident", "category": "ransomware",
    "title": "BlackCat/ALPHV ransomware on EDF subsidiary network",
    "description": "BlackCat ransomware lateral movement detected on subsidiary OT network. Initial access through compromised VPN credentials from credential stuffing campaign.",
    "severity": "critical",
    "indicators": {
        "ip": ["45.148.10.0/24", "185.212.60.0/24"],
        "domain": ["blackcat[.]onion", "edf-leak[.]xyz"],
        "hash": ["ff00deadbeef1234567890abcdef0123", "cafe0123456789abcdef0123456789a"],
    },
    "mitre_attack": ["T1486", "T1078", "T1133", "T1021.001"],
    "source": "EDF SOC / ANSSI", "timestamp": "2026-06-28T14:00:00Z",
    "tlp": "red", "confidence": 100,
    "affected_sectors": ["energy"],
}, True, shared_at=now-h(120), arrival=now-h(144), timeliness=h(24),
   extension_time=h(6), anon_time=h(2), sharing_speed=h(1)))

events.append(create_event(orgs["CHUP"], {
    "type": "incident", "category": "ransomware",
    "title": "Rhysida ransomware targeting hospital PACS systems",
    "description": "Rhysida ransomware specifically targeting medical imaging (PACS) systems. Patient data including MRI/CT scans encrypted. Emergency services degraded.",
    "severity": "critical",
    "indicators": {
        "ip": ["91.215.85.0/24"],
        "domain": ["rhysida[.]onion", "patient-data-leak[.]xyz"],
        "hash": ["0123456789abcdef0123456789abcde"],
    },
    "mitre_attack": ["T1486", "T1565.001", "T1560"],
    "source": "CHU SOC / ANSSI Health ISAC", "timestamp": "2026-07-03T02:30:00Z",
    "tlp": "red", "confidence": 100,
    "affected_sectors": ["health"],
}, False, arrival=now-h(100), timeliness=None))

events.append(create_event(orgs["SNCF"], {
    "type": "incident", "category": "ransomware",
    "title": "Akira ransomware on ticketing infrastructure",
    "description": "Akira ransomware encrypted ticketing database servers. Attack originated from exposed RDP on maintenance workstation.",
    "severity": "high",
    "indicators": {
        "ip": ["193.142.58.0/24"],
        "domain": ["akira[.]onion"],
        "hash": ["deadbeef0123456789abcdef012345678"],
    },
    "mitre_attack": ["T1486", "T1021.001", "T1133"],
    "source": "SNCF CERT", "timestamp": "2026-06-15T11:00:00Z",
    "tlp": "amber", "confidence": 100,
    "affected_sectors": ["transport"],
}, True, shared_at=now-h(240), arrival=now-h(280), timeliness=h(40),
   extension_time=h(8), anon_time=h(3), sharing_speed=h(2)))

events.append(create_event(orgs["AMUN"], {
    "type": "incident", "category": "ransomware",
    "title": "Clop ransomware via MOVEit zero-day (CVE-2023-34362 variant)",
    "description": "Clop ransomware exploiting MOVEit Transfer vulnerability. Financial documents and customer PII potentially exposed.",
    "severity": "critical",
    "indicators": {
        "ip": ["104.18.0.0/16"],
        "domain": ["clop[.]onion", "amundi-leak[.]xyz"],
        "hash": ["abcdef0123456789abcdef01234567890"],
    },
    "mitre_attack": ["T1190", "T1486", "T1567.002"],
    "source": "Amundi SOC / FS-ISAC", "timestamp": "2026-07-05T16:45:00Z",
    "tlp": "red", "confidence": 100,
    "affected_sectors": ["banking"],
}, True, shared_at=now-h(48), arrival=now-h(50), timeliness=h(2),
   extension_time=m(90), anon_time=m(30), sharing_speed=m(20)))

# ── Category: APT / State-sponsored (5 events) ──
events.append(create_event(orgs["RTE"], {
    "type": "threat-intelligence", "category": "apt",
    "title": "Sandworm Team (UAC-0082) targeting Ukrainian energy grid",
    "description": "Sandworm APT group observed deploying new Industroyer2 variant against Ukrainian power grid SCADA systems. Lateral movement via compromised Siemens S7 PLCs.",
    "severity": "critical",
    "indicators": {
        "ip": ["91.219.236.0/24", "195.54.160.0/24", "91.210.104.0/24"],
        "domain": ["siemens-update[.]com", "plc-config[.]net"],
        "hash": ["44a8f4f34e5c5c5c5c5c5c5c5c5c5c5c", "55b9f5f45f6d6d6d6d6d6d6d6d6d6d6d"],
        "mutex": ["Global\\SIEMENS_S7_MUTEX"],
    },
    "mitre_attack": ["T1190", "T0831", "T0830", "T1571", "T0886"],
    "source": "CERT-UA / ESET", "timestamp": "2026-06-20T08:00:00Z",
    "tlp": "white", "confidence": 95,
    "affected_sectors": ["energy"],
}, True, shared_at=now-h(480), arrival=now-h(490), timeliness=h(10),
   extension_time=h(4), anon_time=h(1), sharing_speed=m(45)))

events.append(create_event(orgs["ORANGE"], {
    "type": "threat-intelligence", "category": "apt",
    "title": "APT41 (Winnti) supply chain attack on telecom infrastructure",
    "description": "APT41 observed compromising telecom equipment firmware through supply chain vectors. Backdoors deployed on core routing infrastructure.",
    "severity": "critical",
    "indicators": {
        "ip": ["23.227.196.0/24", "104.16.0.0/12"],
        "domain": ["firmware-update[.]net", "cdn-syslog[.]com"],
        "hash": ["66c0f6f56a7e7e7e7e7e7e7e7e7e7e7e", "77d1f7f6f8b8f8f8f8f8f8f8f8f8f8f8"],
    },
    "mitre_attack": ["T1195.002", "T1195.001", "T1584.004", "T1090.004"],
    "source": "Orange CERT / ANSSI", "timestamp": "2026-06-25T15:30:00Z",
    "tlp": "amber", "confidence": 85,
    "affected_sectors": ["digital-infra", "ict-service"],
}, True, shared_at=now-h(300), arrival=now-h(310), timeliness=h(10),
   extension_time=h(3), anon_time=m(90), sharing_speed=m(50)))

events.append(create_event(orgs["AIRFR"], {
    "type": "threat-intelligence", "category": "apt",
    "title": "Kinsing cryptominer exploiting Docker API",
    "description": "Kinsing malware group targeting exposed Docker APIs to deploy cryptocurrency miners. Lateral movement to production containers detected.",
    "severity": "high",
    "indicators": {
        "ip": ["104.248.40.0/24"],
        "domain": ["update.kinsing[.]xyz"],
        "hash": ["88e2f8f7f9c9f9f9f9f9f9f9f9f9f9f9"],
    },
    "mitre_attack": ["T1610", "T1611", "T1059.004"],
    "source": "Air France IT / Wiz", "timestamp": "2026-07-02T10:15:00Z",
    "tlp": "green", "confidence": 90,
    "affected_sectors": ["transport", "digital-infra"],
}, True, shared_at=now-h(130), arrival=now-h(135), timeliness=h(5),
   extension_time=m(60), anon_time=m(20), sharing_speed=m(15)))

events.append(create_event(orgs["VINCI"], {
    "type": "threat-intelligence", "category": "apt",
    "title": "Volt Typhoon pre-positioning on airport OT networks",
    "description": "Chinese state-sponsored group Volt Typhoon observed establishing persistent access on airport OT networks. Living-off-the-land techniques used.",
    "severity": "critical",
    "indicators": {
        "ip": ["154.213.0.0/16"],
        "domain": ["edge-cdn[.]com", "update-sys[.]net"],
        "hash": ["99f3f9f8f0d0f0f0f0f0f0f0f0f0f0f0"],
        "named_pipe": ["\\pipe\\msagent_"],
    },
    "mitre_attack": ["T1190", "T1005", "T1082", "T1018"],
    "source": "CISA / Vinci SOC", "timestamp": "2026-06-30T09:00:00Z",
    "tlp": "amber", "confidence": 88,
    "affected_sectors": ["transport", "energy"],
}, False, arrival=now-h(180), timeliness=None))

events.append(create_event(orgs["SANOFI"], {
    "type": "threat-intelligence", "category": "apt",
    "title": "FIN7 targeting pharmaceutical R&D data",
    "description": "FIN7 cybercrime group pivoting to pharmaceutical espionage. Spear-phishing targeting R&D staff with COVID-19 vaccine research lures.",
    "severity": "high",
    "indicators": {
        "ip": ["198.51.100.0/24"],
        "domain": ["research-portal[.]com", "vaccine-update[.]net"],
        "hash": ["aa04fafaf1e1f1f1f1f1f1f1f1f1f1f1"],
    },
    "mitre_attack": ["T1566.002", "T1059.005", "T1027"],
    "source": "Sanofi CERT / FS-ISAC", "timestamp": "2026-07-06T14:20:00Z",
    "tlp": "amber", "confidence": 82,
    "affected_sectors": ["health", "chemical"],
}, True, shared_at=now-h(24), arrival=now-h(30), timeliness=h(6),
   extension_time=h(2), anon_time=m(45), sharing_speed=m(25)))

# ── Category: Phishing (5 events) ──
events.append(create_event(orgs["SNCF"], {
    "type": "incident", "category": "phishing",
    "title": "Credential harvesting campaign targeting French transport operators",
    "description": "Mass phishing campaign impersonating ANSSI to harvest O365 and VPN credentials from transport sector employees. 200+ emails sent, 12 accounts compromised.",
    "severity": "high",
    "indicators": {
        "ip": ["45.77.65.211", "104.238.40.89"],
        "domain": ["anssi-secure[.]fr", "transport-auth[.]com", "vpn-login[.]net"],
        "hash": ["bb15fbfbf2f2f2f2f2f2f2f2f2f2f2f2"],
        "url": ["https://anssi-secure[.]fr/auth/login", "https://transport-auth[.]com/verify"],
    },
    "mitre_attack": ["T1566", "T1539", "T1557", "T1598.003"],
    "source": "ANSSI / PhishTank", "timestamp": "2026-07-03T08:45:00Z",
    "tlp": "amber", "confidence": 92,
    "affected_sectors": ["transport"],
}, True, shared_at=now-h(96), arrival=now-h(98), timeliness=h(2),
   extension_time=m(60), anon_time=m(15), sharing_speed=m(10)))

events.append(create_event(orgs["MONT"], {
    "type": "incident", "category": "phishing",
    "title": "QR code phishing (quishing) campaign targeting cloud providers",
    "description": "Novel phishing technique using malicious QR codes in PDF documents to bypass email security filters. Targets AWS/Azure credentials.",
    "severity": "medium",
    "indicators": {
        "ip": ["162.241.27.0/24"],
        "domain": ["aws-verify[.]com", "azure-auth[.]net"],
        "hash": ["cc260c0c03g3g3g3g3g3g3g3g3g3g3g3"],
    },
    "mitre_attack": ["T1566.003", "T1528", "T1539"],
    "source": "Montimage Threat Intel", "timestamp": "2026-07-04T11:00:00Z",
    "tlp": "green", "confidence": 88,
    "affected_sectors": ["ict-service"],
}, True, shared_at=now-h(72), arrival=now-h(75), timeliness=h(3),
   extension_time=m(45), anon_time=m(10), sharing_speed=m(8)))

events.append(create_event(orgs["EDF"], {
    "type": "incident", "category": "phishing",
    "title": "Business Email Compromise targeting procurement department",
    "description": "BEC attack impersonating CFO to redirect €2.3M payment to fraudulent account. Attack succeeded for €450K before detection.",
    "severity": "critical",
    "indicators": {
        "ip": ["185.174.136.0/24"],
        "domain": ["edf-finance[.]com", "payment-update[.]net"],
        "hash": ["dd371d1d14h4h4h4h4h4h4h4h4h4h4h4"],
        "email": ["cfo@edf-finance[.]com"],
    },
    "mitre_attack": ["T1566.002", "T1534", "T1567.003"],
    "source": "EDF SOC", "timestamp": "2026-06-18T09:30:00Z",
    "tlp": "red", "confidence": 100,
    "affected_sectors": ["energy"],
}, True, shared_at=now-h(500), arrival=now-h(510), timeliness=h(10),
   extension_time=h(3), anon_time=m(30), sharing_speed=m(20)))

events.append(create_event(orgs["CHUP"], {
    "type": "incident", "category": "phishing",
    "title": "Vishing campaign targeting hospital switchboard operators",
    "description": "Voice phishing campaign where attackers impersonate IT support to trick operators into revealing VPN credentials. 8 calls made, 2 credentials obtained.",
    "severity": "high",
    "indicators": {
        "ip": ["+33 1 XX XX XX XX"],
        "domain": ["chup-it-support[.]com"],
        "hash": [],
    },
    "mitre_attack": ["T1566.004", "T1539", "T1078"],
    "source": "CHU Security Team", "timestamp": "2026-07-07T16:00:00Z",
    "tlp": "amber", "confidence": 85,
    "affected_sectors": ["health"],
}, False, arrival=now-h(12)))

events.append(create_event(orgs["ORANGE"], {
    "type": "incident", "category": "phishing",
    "title": "MFA fatigue attack on enterprise SSO accounts",
    "description": "Attackers repeatedly sending MFA push notifications to employees until they approve. 4 accounts compromised through this technique.",
    "severity": "high",
    "indicators": {
        "ip": ["192.0.2.0/24"],
        "domain": [],
        "hash": [],
        "user_agent": ["Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1)"],
    },
    "mitre_attack": ["T1621", "T1539", "T1078.004"],
    "source": "Orange CERT", "timestamp": "2026-07-08T07:15:00Z",
    "tlp": "amber", "confidence": 90,
    "affected_sectors": ["ict-service"],
}, False, arrival=now-h(5)))

# ── Category: Vulnerability / Exploit (5 events) ──
events.append(create_event(orgs["AMUN"], {
    "type": "threat-intelligence", "category": "vulnerability",
    "title": "Critical zero-day in Apache Struts (CVE-2026-13371) actively exploited",
    "description": "Remote code execution vulnerability in Apache Struts 2.x framework. CVSS 9.8. Active exploitation observed in financial services sector since July 5th.",
    "severity": "critical",
    "indicators": {
        "ip": ["185.112.83.0/24"],
        "domain": ["struts-exploit[.]xyz"],
        "hash": ["ee482e2e25i5i5i5i5i5i5i5i5i5i5i5"],
    },
    "mitre_attack": ["T1190", "T1203", "T1059.001"],
    "source": "NVD / CISA KEV / FS-ISAC", "timestamp": "2026-07-05T16:00:00Z",
    "tlp": "white", "confidence": 100,
    "cve_id": "CVE-2026-13371",
    "cvss_score": 9.8,
    "affected_sectors": ["banking", "ict-service"],
}, True, shared_at=now-h(48), arrival=now-h(50), timeliness=h(2),
   extension_time=m(60), anon_time=m(10), sharing_speed=m(5)))

events.append(create_event(orgs["ORANGE"], {
    "type": "threat-intelligence", "category": "vulnerability",
    "title": "Fortinet FortiGate SSL-VPN CVE-2024-21762 exploitation wave",
    "description": "Widespread exploitation of out-of-bounce write vulnerability in FortiOS SSL-VPN. Chinese APT groups actively scanning for vulnerable instances.",
    "severity": "critical",
    "indicators": {
        "ip": ["91.215.85.0/24", "103.131.144.0/24"],
        "domain": ["fortinet-patch[.]com"],
        "hash": ["ff593f3f36j6j6j6j6j6j6j6j6j6j6j6"],
    },
    "mitre_attack": ["T1190", "T1133", "T1059.001"],
    "source": "FortiGuard / CISA", "timestamp": "2026-06-22T12:00:00Z",
    "tlp": "white", "confidence": 100,
    "cve_id": "CVE-2024-21762",
    "cvss_score": 9.8,
    "affected_sectors": ["digital-infra", "ict-service"],
}, True, shared_at=now-h(400), arrival=now-h(420), timeliness=h(20),
   extension_time=h(5), anon_time=h(2), sharing_speed=h(1)))

events.append(create_event(orgs["MONT"], {
    "type": "threat-intelligence", "category": "vulnerability",
    "title": "GitLab CI/管道 injection vulnerability (CVE-2026-9999)",
    "description": "Critical CI/CD pipeline injection allowing arbitrary code execution via crafted .gitlab-ci.yml. Affects self-hosted GitLab instances.",
    "severity": "high",
    "indicators": {
        "ip": [],
        "domain": ["gitlab-pipeline[.]exploit[.]xyz"],
        "hash": ["006a4a4a47k7k7k7k7k7k7k7k7k7k7k7"],
    },
    "mitre_attack": ["T1195.002", "T1059.007", "T1203"],
    "source": "GitLab Security Advisory", "timestamp": "2026-07-01T14:30:00Z",
    "tlp": "green", "confidence": 95,
    "cve_id": "CVE-2026-9999",
    "cvss_score": 8.8,
    "affected_sectors": ["ict-service", "digital-infra"],
}, True, shared_at=now-h(60), arrival=now-h(62), timeliness=h(2),
   extension_time=m(45), anon_time=m(10), sharing_speed=m(8)))

events.append(create_event(orgs["VINCI"], {
    "type": "incident", "category": "vulnerability",
    "title": "Cisco IOS XE zero-day exploitation on airport network infrastructure",
    "description": "Zero-day vulnerability in Cisco IOS XE being exploited to gain root access on network devices. Airport control systems potentially affected.",
    "severity": "critical",
    "indicators": {
        "ip": ["198.18.0.0/15"],
        "domain": ["cisco-xe[.]exploit[.]xyz"],
        "hash": ["117b5b5b58l8l8l8l8l8l8l8l8l8l8l8"],
    },
    "mitre_attack": ["T1190", "T1098", "T1053.002"],
    "source": "Vinci SOC / Cisco PSIRT", "timestamp": "2026-07-04T08:00:00Z",
    "tlp": "red", "confidence": 100,
    "affected_sectors": ["transport", "energy"],
}, True, shared_at=now-h(78), arrival=now-h(80), timeliness=h(2),
   extension_time=m(90), anon_time=m(30), sharing_speed=m(20)))

events.append(create_event(orgs["SANOFI"], {
    "type": "threat-intelligence", "category": "vulnerability",
    "title": "Palo Alto PAN-OS GlobalProtect vulnerability (CVE-2026-4444)",
    "description": "Authentication bypass in GlobalProtect VPN allowing unauthenticated access to internal networks. Active exploitation in healthcare sector.",
    "severity": "high",
    "indicators": {
        "ip": ["203.0.113.0/24"],
        "domain": ["globalprotect-exploit[.]xyz"],
        "hash": ["228c6c6c69m9m9m9m9m9m9m9m9m9m9m9"],
    },
    "mitre_attack": ["T1190", "T1078", "T1133"],
    "source": "Palo Alto / CISA KEV", "timestamp": "2026-07-07T10:00:00Z",
    "tlp": "amber", "confidence": 100,
    "cve_id": "CVE-2026-4444",
    "cvss_score": 9.1,
    "affected_sectors": ["health"],
}, True, shared_at=now-h(14), arrival=now-h(16), timeliness=h(2),
   extension_time=m(40), anon_time=m(10), sharing_speed=m(8)))

# ── Category: Data Breach / Leak (5 events) ──
events.append(create_event(orgs["CHUP"], {
    "type": "incident", "category": "data-breach",
    "title": "Patient data exfiltration via misconfigured S3 bucket",
    "description": "AWS S3 bucket containing 15,000 patient MRI/CT scans exposed for 72 hours. Evidence of unauthorized access from Eastern European IP ranges.",
    "severity": "critical",
    "indicators": {
        "ip": ["52.89.214.238", "34.240.98.157", "185.196.200.0/24"],
        "domain": ["s3-backup-chu[.]amazonaws.com"],
        "hash": ["339d7d7d70n0n0n0n0n0n0n0n0n0n0n0"],
    },
    "mitre_attack": ["T1530", "T1567", "T1537", "T1078.004"],
    "source": "AWS GuardDuty / Internal audit", "timestamp": "2026-07-04T11:20:00Z",
    "tlp": "red", "confidence": 100,
    "affected_sectors": ["health"],
    "data_volume_exposed": "15,000 patient records (~2.3TB)",
}, True, shared_at=now-h(78), arrival=now-h(80), timeliness=h(2),
   extension_time=m(60), anon_time=m(30), sharing_speed=m(25)))

events.append(create_event(orgs["AMUN"], {
    "type": "incident", "category": "data-breach",
    "title": "Customer portfolio data leaked on dark web forum",
    "description": "Customer investment portfolio data appearing on BreachForums. Data includes portfolio values, investment strategies, and personal information for 50,000+ clients.",
    "severity": "critical",
    "indicators": {
        "ip": ["185.220.101.0/24"],
        "domain": ["breachforums[.]st"],
        "hash": [],
        "forum_post_id": "bf-2026-07-06-amundi",
    },
    "mitre_attack": ["T1530", "T1567.002", "T1657"],
    "source": "Dark web monitoring / FS-ISAC", "timestamp": "2026-07-06T09:00:00Z",
    "tlp": "red", "confidence": 100,
    "affected_sectors": ["banking"],
}, False, arrival=now-h(36), timeliness=None))

events.append(create_event(orgs["SNCF"], {
    "type": "incident", "category": "data-breach",
    "title": "Employee PII exposed through misconfigured Elasticsearch",
    "description": "Elasticsearch cluster containing employee records (28,000 employees) publicly accessible without authentication for 3 weeks.",
    "severity": "high",
    "indicators": {
        "ip": ["37.187.12.0/24"],
        "domain": [],
        "hash": [],
        "elastic_index": "employee-records-2026",
    },
    "mitre_attack": ["T1530", "T1046", "T1592"],
    "source": "Security researcher disclosure", "timestamp": "2026-06-28T14:00:00Z",
    "tlp": "amber", "confidence": 100,
    "affected_sectors": ["transport"],
}, True, shared_at=now-h(200), arrival=now-h(210), timeliness=h(10),
   extension_time=h(4), anon_time=h(2), sharing_speed=h(1)))

events.append(create_event(orgs["EDF"], {
    "type": "incident", "category": "data-breach",
    "title": "Insider threat: employee exfiltrating reactor maintenance data",
    "description": "Departing employee downloading sensitive reactor maintenance schedules and safety reports. 847 files accessed in unauthorized manner over 2 weeks.",
    "severity": "high",
    "indicators": {
        "ip": ["10.0.0.147"],
        "domain": [],
        "hash": [],
        "user": "contractor_xxx@edf.fr",
    },
    "mitre_attack": ["T1052.001", "T1074.002", "T1567.002"],
    "source": "EDF DLP / HR Security", "timestamp": "2026-07-02T08:00:00Z",
    "tlp": "red", "confidence": 100,
    "affected_sectors": ["energy"],
}, True, shared_at=now-h(130), arrival=now-h(140), timeliness=h(10),
   extension_time=h(5), anon_time=h(3), sharing_speed=h(2)))

events.append(create_event(orgs["ORANGE"], {
    "type": "incident", "category": "data-breach",
    "title": "Customer metadata exposure via API misconfiguration",
    "description": "REST API endpoint exposing customer metadata (names, emails, phone numbers) without authentication. Affects 120,000 enterprise customers.",
    "severity": "high",
    "indicators": {
        "ip": ["193.251.0.0/16"],
        "domain": ["api-enterprise[.]orange[.]com"],
        "hash": [],
        "api_endpoint": "/api/v2/customers?include=pii",
    },
    "mitre_attack": ["T1530", "T1190", "T1046"],
    "source": "Orange CERT / Bug bounty", "timestamp": "2026-07-07T11:30:00Z",
    "tlp": "amber", "confidence": 100,
    "affected_sectors": ["ict-service", "digital-infra"],
}, True, shared_at=now-h(10), arrival=now-h(12), timeliness=h(2),
   extension_time=m(30), anon_time=m(10), sharing_speed=m(5)))

# ── Category: DDoS (3 events) ──
events.append(create_event(orgs["RTE"], {
    "type": "incident", "category": "ddos",
    "title": "DDoS attack targeting French energy grid monitoring systems",
    "description": "Distributed denial of service targeting real-time monitoring. Peak volume 45 Gbps. Attributed to Killnet-affiliated group.",
    "severity": "high",
    "indicators": {
        "ip": ["103.224.182.0/24", "194.169.0.0/16"],
        "domain": [],
        "hash": [],
    },
    "mitre_attack": ["T1498", "T1498.002"],
    "source": "Cloudflare / RTE SOC", "timestamp": "2026-07-07T03:15:00Z",
    "tlp": "amber", "confidence": 100,
    "affected_sectors": ["energy"],
}, True, shared_at=now-h(12), arrival=now-h(14), timeliness=h(2),
   extension_time=m(30), anon_time=m(5), sharing_speed=m(3)))

events.append(create_event(orgs["AIRFR"], {
    "type": "incident", "category": "ddos",
    "title": "Volumetric DDoS on airline reservation system",
    "description": "DNS amplification attack targeting booking infrastructure. 120 Gbps peak. Service degraded for 45 minutes.",
    "severity": "high",
    "indicators": {
        "ip": ["195.54.160.0/24", "91.215.85.0/24"],
        "domain": [],
        "hash": [],
    },
    "mitre_attack": ["T1498.002", "T1498.001"],
    "source": "Akamai / Air France IT", "timestamp": "2026-06-25T18:30:00Z",
    "tlp": "green", "confidence": 100,
    "affected_sectors": ["transport"],
}, True, shared_at=now-h(330), arrival=now-h(335), timeliness=h(5),
   extension_time=m(45), anon_time=m(10), sharing_speed=m(5)))

events.append(create_event(orgs["CHUP"], {
    "type": "incident", "category": "ddos",
    "title": "Ransom DDoS targeting hospital telemedicine platform",
    "description": "Extortion DDoS targeting telemedicine platform. Attackers demanding €50,000 in Bitcoin. Telemedicine services offline for 6 hours.",
    "severity": "critical",
    "indicators": {
        "ip": ["185.220.101.0/24"],
        "domain": ["telemedicine[.]chu-paris[.]fr"],
        "hash": [],
        "bitcoin_wallet": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
    },
    "mitre_attack": ["T1498", "T1486", "T1499"],
    "source": "CHU IT Security", "timestamp": "2026-07-06T20:00:00Z",
    "tlp": "red", "confidence": 100,
    "affected_sectors": ["health"],
}, False, arrival=now-h(28), timeliness=None))

# ── Category: Supply Chain (4 events) ──
events.append(create_event(orgs["MONT"], {
    "type": "threat-intelligence", "category": "supply-chain",
    "title": "Compromised npm package 'event-stream-pro' exfiltrating env vars",
    "description": "Backdoor in popular npm package (800K weekly downloads) exfiltrating environment variables and API keys to external C2 servers.",
    "severity": "high",
    "indicators": {
        "ip": ["104.18.22.33"],
        "domain": ["npm-analytics[.]com"],
        "hash": ["badc0ffe1234567890abcdef12345678"],
        "package_name": "event-stream-pro",
    },
    "mitre_attack": ["T1195.002", "T1059.007", "T1071.001"],
    "source": "Socket Security / npm audit", "timestamp": "2026-07-06T10:00:00Z",
    "tlp": "green", "confidence": 100,
    "affected_sectors": ["ict-service"],
}, True, shared_at=now-h(36), arrival=now-h(38), timeliness=h(2),
   extension_time=m(45), anon_time=m(10), sharing_speed=m(5)))

events.append(create_event(orgs["SANOFI"], {
    "type": "threat-intelligence", "category": "supply-chain",
    "title": "Malicious PyPI package impersonating 'requests' library",
    "description": "Typosquatting on PyPI: 'requestz' package contains credential-stealing backdoor. Downloaded 12,000 times before removal.",
    "severity": "medium",
    "indicators": {
        "ip": ["185.199.108.0/24"],
        "domain": ["pypi-mirror[.]xyz"],
        "hash": ["cafe0000111122223333444455556666"],
        "package_name": "requestz",
    },
    "mitre_attack": ["T1195.002", "T1059.006"],
    "source": "PyPI Security / Sanofi DevOps", "timestamp": "2026-06-20T11:00:00Z",
    "tlp": "green", "confidence": 98,
    "affected_sectors": ["ict-service", "health"],
}, True, shared_at=now-h(460), arrival=now-h(465), timeliness=h(5),
   extension_time=h(2), anon_time=h(1), sharing_speed=m(30)))

events.append(create_event(orgs["EDF"], {
    "type": "threat-intelligence", "category": "supply-chain",
    "title": "Compromised Siemens TIA Portal update server",
    "description": "Siemens engineering software update server serving trojanized updates. Targets industrial control system configurations.",
    "severity": "critical",
    "indicators": {
        "ip": ["194.39.106.0/24"],
        "domain": ["siemens-automation[.]com"],
        "hash": ["ff0011223344556677889900aabbccdd"],
        "affected_software": "TIA Portal v18",
    },
    "mitre_attack": ["T1195.002", "T1195.001"],
    "source": "Siemens CERT / E-ISAC", "timestamp": "2026-07-03T06:00:00Z",
    "tlp": "red", "confidence": 100,
    "affected_sectors": ["energy"],
}, True, shared_at=now-h(100), arrival=now-h(108), timeliness=h(8),
   extension_time=h(4), anon_time=h(2), sharing_speed=h(1)))

events.append(create_event(orgs["VINCI"], {
    "type": "threat-intelligence", "category": "supply-chain",
    "title": "Trojanized Docker image on Docker Hub for airport monitoring",
    "description": "Malicious Docker image impersonating official Grafana monitoring image. Cryptominer and reverse shell included.",
    "severity": "high",
    "indicators": {
        "ip": ["45.33.32.0/24"],
        "domain": ["grafana-monitor[.]xyz"],
        "hash": ["00112233445566778899aabbccddeeff"],
        "docker_image": "grafana/grafana-monitor:latest",
    },
    "mitre_attack": ["T1195.002", "T1610", "T1059.004"],
    "source": "Vinci DevOps / Snyk", "timestamp": "2026-07-08T09:00:00Z",
    "tlp": "green", "confidence": 95,
    "affected_sectors": ["transport", "ict-service"],
}, False, arrival=now-h(3)))

# ── Category: Insider Threat (3 events) ──
events.append(create_event(orgs["AMUN"], {
    "type": "incident", "category": "insider",
    "title": "Privileged access misuse: database administrator copying client data",
    "description": "Senior DBA caught copying client investment database to personal USB device. 200,000 client records potentially compromised.",
    "severity": "critical",
    "indicators": {
        "ip": ["10.0.0.89"],
        "domain": [],
        "hash": [],
        "device": "USB-EXT-4TB",
    },
    "mitre_attack": ["T1052.001", "T1078.002", "T1041"],
    "source": "Amundi DLP / HR Security", "timestamp": "2026-07-01T16:00:00Z",
    "tlp": "red", "confidence": 100,
    "affected_sectors": ["banking"],
}, True, shared_at=now-h(160), arrival=now-h(170), timeliness=h(10),
   extension_time=h(5), anon_time=h(3), sharing_speed=h(2)))

events.append(create_event(orgs["MONT"], {
    "type": "incident", "category": "insider",
    "title": "Contractor leaking penetration test findings to competitor",
    "description": "External penetration testing contractor sharing vulnerability scan results with competing firm. NDA violation and potential IP theft.",
    "severity": "high",
    "indicators": {
        "ip": ["10.0.0.201"],
        "domain": [" competitor-cloud[.]com"],
        "hash": [],
    },
    "mitre_attack": ["T1048.002", "T1567.002"],
    "source": "Montimage HR / Legal", "timestamp": "2026-06-28T10:00:00Z",
    "tlp": "red", "confidence": 100,
    "affected_sectors": ["ict-service"],
}, True, shared_at=now-h(250), arrival=now-h(260), timeliness=h(10),
   extension_time=h(4), anon_time=h(2), sharing_speed=h(1)))

events.append(create_event(orgs["RTE"], {
    "type": "incident", "category": "insider",
    "title": "IT admin installing unauthorized remote access tool",
    "description": "System administrator installing NetSupport RAT on critical SCADA workstations. Potential nation-state recruitment suspected.",
    "severity": "critical",
    "indicators": {
        "ip": ["10.10.0.55"],
        "domain": ["remote-support[.]xyz"],
        "hash": ["aabb11223344556677889900aabb1122"],
        "process": "netsupport.exe",
    },
    "mitre_attack": ["T1021.001", "T1572", "T1098.001"],
    "source": "RTE SOC / ANSSI", "timestamp": "2026-07-05T14:00:00Z",
    "tlp": "red", "confidence": 100,
    "affected_sectors": ["energy"],
}, True, shared_at=now-h(54), arrival=now-h(58), timeliness=h(4),
   extension_time=h(2), anon_time=h(1), sharing_speed=m(45)))

# ── Category: Misc / Other (5 events) ──
events.append(create_event(orgs["ORANGE"], {
    "type": "incident", "category": "cryptomining",
    "title": "Unauthorized cryptocurrency mining on cloud infrastructure",
    "description": "Cryptominer deployed on 47 cloud instances via exposed Kubernetes API. Running for 2 weeks, consuming ~€15,000 in compute resources.",
    "severity": "medium",
    "indicators": {
        "ip": ["147.75.0.0/16"],
        "domain": ["pool.minexmr[.]com"],
        "hash": ["ccdd11223344556677889900aabb3344"],
        "wallet": "48edfHu7V9Z84YzzMa6fUueoELZ9ZRXq9VetWzYGzKt52XU5x9qZ5Qm6f6t6y6u6",
    },
    "mitre_attack": ["T1496", "T1610", "T1059.004"],
    "source": "Orange Cloud SOC", "timestamp": "2026-06-22T09:00:00Z",
    "tlp": "green", "confidence": 100,
    "affected_sectors": ["ict-service"],
}, True, shared_at=now-h(410), arrival=now-h(420), timeliness=h(10),
   extension_time=h(3), anon_time=h(1), sharing_speed=m(30)))

events.append(create_event(orgs["VINCI"], {
    "type": "incident", "category": "unauthorized-access",
    "title": "Physical security breach: unauthorized access to server room",
    "description": "Individual bypassing badge access controls at Orly airport server room. 45 minutes of unrestricted access before detection. USB devices potentially planted.",
    "severity": "high",
    "indicators": {
        "ip": [],
        "domain": [],
        "hash": [],
        "badge_id": "Vinci-ORLY-0847",
    },
    "mitre_attack": ["T1200", "T1091"],
    "source": "Vinci Physical Security", "timestamp": "2026-07-02T22:00:00Z",
    "tlp": "amber", "confidence": 100,
    "affected_sectors": ["transport"],
}, False, arrival=now-h(144)))

events.append(create_event(orgs["SANOFI"], {
    "type": "threat-intelligence", "category": "malware",
    "title": "Novel fileless malware targeting pharmaceutical R&D workstations",
    "description": "Fileless malware using PowerShell and WMI for persistence. Targeting research data exfiltration. Detected by memory forensics.",
    "severity": "high",
    "indicators": {
        "ip": ["192.0.2.0/24"],
        "domain": [],
        "hash": ["eeff11223344556677889900aabb5566"],
        "process": "powershell.exe -enc [base64]",
        "wmi_event": "__EventFilter{Name='SystemHealthMonitor'}",
    },
    "mitre_attack": ["T1059.001", "T1047", "T1140", "T1027.010"],
    "source": "Sanofi EDR / CrowdStrike", "timestamp": "2026-07-04T15:30:00Z",
    "tlp": "amber", "confidence": 92,
    "affected_sectors": ["health", "chemical"],
}, True, shared_at=now-h(72), arrival=now-h(76), timeliness=h(4),
   extension_time=h(2), anon_time=h(1), sharing_speed=m(40)))

events.append(create_event(orgs["MONT"], {
    "type": "threat-intelligence", "category": "botnet",
    "title": "Mirai variant botnet targeting IoT devices in critical infrastructure",
    "description": "New Mirai variant exploiting zero-day in IP cameras used by energy companies. Botnet size estimated at 50,000 nodes.",
    "severity": "high",
    "indicators": {
        "ip": ["45.77.65.0/24", "104.238.40.0/24", "185.56.83.0/24"],
        "domain": ["c2-mirai[.]xyz"],
        "hash": ["ff0011223344556677889900aabb7788"],
    },
    "mitre_attack": ["T1190", "T1583.005", "T1498"],
    "source": "Netlab 360 / Montimage", "timestamp": "2026-07-05T12:00:00Z",
    "tlp": "green", "confidence": 90,
    "affected_sectors": ["energy", "ict-service"],
}, True, shared_at=now-h(50), arrival=now-h(52), timeliness=h(2),
   extension_time=m(60), anon_time=m(15), sharing_speed=m(10)))

events.append(create_event(orgs["RTE"], {
    "type": "incident", "category": "misconfiguration",
    "title": "Exposed Git repository containing SCADA access credentials",
    "description": "Public GitHub repository containing hardcoded SCADA system credentials and API keys. Repository belonged to former contractor.",
    "severity": "critical",
    "indicators": {
        "ip": [],
        "domain": ["github[.]com/former-contractor/rte-tools"],
        "hash": [],
    },
    "mitre_attack": ["T1213.002", "T1552.001", "T1078"],
    "source": "GitHub Advanced Security / RTE", "timestamp": "2026-07-08T06:00:00Z",
    "tlp": "red", "confidence": 100,
    "affected_sectors": ["energy"],
}, True, shared_at=now-h(4), arrival=now-h(6), timeliness=h(2),
   extension_time=m(30), anon_time=m(5), sharing_speed=m(3)))

print(f"   {Event.objects.count()} events created")

# ─────────────────────────────────────────────────────────
# 5. EVENT SHARE LOGS (varied statuses)
# ─────────────────────────────────────────────────────────
print("5/10  Share logs...")
shared_events = Event.objects.filter(shared=True)
for ev in shared_events:
    share_time = ev.shared_at or now
    EventShareLog.objects.get_or_create(
        event=ev,
        shared_by=users["analyst1"],
        defaults={
            "shared_at": share_time,
            "data": {
                "sharing_results": {
                    "status": "success",
                    "servers_notified": 2,
                    "timestamp": str(share_time),
                    "details": [
                        {"server": "MISP-ANSSI", "status": "success", "message": "Event shared"},
                        {"server": "MISP-EU-ISAC", "status": "success", "message": "Event shared"}
                    ]
                }
            }
        }
    )
print(f"   {EventShareLog.objects.count()} share logs")

# ─────────────────────────────────────────────────────────
# 6. FORMS
# ─────────────────────────────────────────────────────────
print("6/10  Forms...")
forms = {}
form_defs = [
    ("Incident Assessment Form", "Standard form for assessing cybersecurity incidents", [
        {"name": "incident_type", "type": "select", "label": "Incident Type", "required": True, "options": ["Malware","Phishing","DDoS","Data Breach","Insider Threat","Supply Chain","Vulnerability","APT","Other"]},
        {"name": "severity", "type": "select", "label": "Severity", "required": True, "options": ["Critical","High","Medium","Low","Info"]},
        {"name": "affected_systems", "type": "textarea", "label": "Affected Systems", "required": True, "placeholder": "List affected systems..."},
        {"name": "timeline", "type": "textarea", "label": "Attack Timeline", "required": False},
        {"name": "containment_actions", "type": "textarea", "label": "Containment Actions", "required": True},
        {"name": "recommendations", "type": "textarea", "label": "Recommendations", "required": False},
        {"name": "indicators_found", "type": "checkbox", "label": "IOCs Identified", "required": False, "options": ["IP Addresses","Domains","File Hashes","Email Addresses","URLs"]},
        {"name": "attribution_confidence", "type": "radio", "label": "Attribution Confidence", "required": False, "options": ["High","Medium","Low","Unknown"]},
    ], ["MONT","RTE","SNCF","EDF","ORANGE"]),
    ("NIS2 Compliance Report", "NIS2 directive compliance reporting form", [
        {"name": "organization_name", "type": "text", "label": "Organization", "required": True},
        {"name": "sector", "type": "select", "label": "Sector", "required": True, "options": ["Energy","Transport","Banking","Health","Digital Infrastructure","ICT Services","Public Administration","Space"]},
        {"name": "incident_category", "type": "select", "label": "NIS2 Category", "required": True, "options": ["Significant","Critical","Major"]},
        {"name": "impact_assessment", "type": "textarea", "label": "Impact Assessment", "required": True},
        {"name": "notification_authority", "type": "select", "label": "Competent Authority", "required": True, "options": ["Yes","No","In Progress"]},
        {"name": "remediation_status", "type": "select", "label": "Remediation", "required": True, "options": ["Completed","In Progress","Not Started"]},
        {"name": "deadline_met", "type": "radio", "label": "24h Notification Deadline Met", "required": True, "options": ["Yes","No"]},
    ], ["MONT","RTE","CHUP","EDF","SNCF","AIRFR","VINCI"]),
    ("Threat Intelligence Sharing Form", "Form for sharing IOCs with partners", [
        {"name": "threat_type", "type": "select", "label": "Threat Type", "required": True, "options": ["APT","Ransomware","Phishing","Vulnerability","Supply Chain","Insider","DDoS","Malware","Other"]},
        {"name": "confidence_level", "type": "radio", "label": "Confidence", "required": True, "options": ["High","Medium","Low"]},
        {"name": "indicators", "type": "textarea", "label": "IOCs", "required": True},
        {"name": "description", "type": "textarea", "label": "Description", "required": True},
        {"name": "attribution", "type": "text", "label": "Attribution", "required": False},
        {"name": "sharing_scope", "type": "select", "label": "Scope", "required": True, "options": ["Internal","Sector Partners","All Partners","Public"]},
        {"name": "tlp", "type": "select", "label": "TLP", "required": True, "options": ["White","Green","Amber","Red"]},
    ], ["MONT","AMUN","ORANGE","SANOFI"]),
    ("Vulnerability Assessment Form", "Form for documenting vulnerability assessments", [
        {"name": "cve_id", "type": "text", "label": "CVE ID", "required": True, "placeholder": "CVE-YYYY-NNNNN"},
        {"name": "cvss_score", "type": "text", "label": "CVSS Score", "required": True},
        {"name": "affected_product", "type": "text", "label": "Affected Product", "required": True},
        {"name": "exploitation_status", "type": "select", "label": "Exploitation Status", "required": True, "options": ["Active Exploitation","PoC Available","Theoretical","Patch Available"]},
        {"name": "remediation", "type": "textarea", "label": "Remediation Steps", "required": True},
        {"name": "workaround", "type": "textarea", "label": "Workaround", "required": False},
    ], ["MONT","ORANGE","EDF","VINCI"]),
]
for title, desc, fields, org_keys in form_defs:
    f, _ = Form.objects.get_or_create(title=title, defaults={"description": desc, "fields": fields, "created_by": users["admin"], "is_active": True})
    for p in org_keys:
        f.organizations.add(orgs[p])
    forms[title] = f
print(f"   {Form.objects.count()} forms")

# ─────────────────────────────────────────────────────────
# 7. FORM ANSWERS
# ─────────────────────────────────────────────────────────
print("7/10  Form answers...")
events_list = list(Event.objects.all())
fa_data = [
    ("Incident Assessment Form", 0, "analyst1", {
        "incident_type": "Malware", "severity": "Critical",
        "affected_systems": "AD Server, 3 workstations, backup server, firewall",
        "timeline": "08:00 Phishing received → 09:15 Ransomware execution → 09:30 SOC alerted → 10:00 Containment",
        "containment_actions": "Isolated VLAN, blocked C2 IPs, initiated IR plan, preserved forensic images",
        "recommendations": "Deploy EDR, enforce MFA, update email filtering, conduct tabletop exercise",
        "indicators_found": ["IP Addresses","Domains","File Hashes","Email Addresses"],
        "attribution_confidence": "Medium"
    }),
    ("Incident Assessment Form", 3, "analyst2", {
        "incident_type": "Data Breach", "severity": "Critical",
        "affected_systems": "AWS S3 bucket, PACS servers, backup storage",
        "timeline": "Bucket exposed Apr 5 → Access Jul 4 → Discovery Jul 4 → Containment Jul 4",
        "containment_actions": "Revoke credentials, enable bucket encryption, audit access logs, notify DPO",
        "recommendations": "Implement cloud security posture management, automate S3 auditing",
        "indicators_found": ["IP Addresses"],
        "attribution_confidence": "Unknown"
    }),
    ("Incident Assessment Form", 8, "analyst1", {
        "incident_type": "Phishing", "severity": "High",
        "affected_systems": "O365 accounts, VPN gateway, 12 user workstations",
        "timeline": "08:45 Phishing sent → 09:00 Credentials harvested → 09:30 VPN logins detected",
        "containment_actions": "Reset passwords, block domains, deploy conditional access, quarantine emails",
        "recommendations": "Implement FIDO2, conduct phishing training, enhance email authentication",
        "indicators_found": ["IP Addresses","Domains","URLs","Email Addresses"],
        "attribution_confidence": "High"
    }),
    ("NIS2 Compliance Report", 5, "analyst2", {
        "organization_name": "CHU Paris", "sector": "Health",
        "incident_category": "Critical",
        "impact_assessment": "15,000 patient records potentially exposed. Medical imaging data (MRI/CT) in S3 bucket. No evidence of exfiltration but integrity cannot be guaranteed. Business continuity partially impacted.",
        "notification_authority": "Yes", "remediation_status": "In Progress",
        "deadline_met": "Yes"
    }),
    ("NIS2 Compliance Report", 12, "analyst1", {
        "organization_name": "RTE Réseau", "sector": "Energy",
        "incident_category": "Critical",
        "impact_assessment": "SCADA monitoring systems targeted. Grid stability not compromised but potential for future attacks. 3 monitoring stations isolated for investigation.",
        "notification_authority": "Yes", "remediation_status": "Completed",
        "deadline_met": "No"
    }),
    ("Threat Intelligence Sharing Form", 0, "analyst1", {
        "threat_type": "Ransomware", "confidence_level": "High",
        "indicators": "IP: 185.220.101.45, 194.26.29.120\nDomain: lockbit3[.]xyz\nHash: e5d88a2cc3237deb70f9d0dc26d1358c",
        "description": "LockBit 3.0 ransomware targeting energy sector via phishing. Sophisticated attack chain with backup encryption before main payload.",
        "attribution": "LockBit 3.0",
        "sharing_scope": "Sector Partners", "tlp": "Amber"
    }),
    ("Threat Intelligence Sharing Form", 4, "analyst2", {
        "threat_type": "Vulnerability", "confidence_level": "High",
        "indicators": "CVE-2026-13371\nIP: 185.112.83.0/24\nHash: ee482e2e25i5i5i5i5i5i5i5i5i5i5i5",
        "description": "Critical Apache Struts RCE actively exploited in financial sector. CVSS 9.8.",
        "attribution": "Unknown",
        "sharing_scope": "All Partners", "tlp": "Green"
    }),
    ("Vulnerability Assessment Form", 4, "analyst3", {
        "cve_id": "CVE-2026-13371", "cvss_score": "9.8",
        "affected_product": "Apache Struts 2.x",
        "exploitation_status": "Active Exploitation",
        "remediation": "Upgrade to Apache Struts 2.8.1+ or apply vendor patch immediately",
        "workaround": "Implement WAF rules to block OGNL injection patterns"
    }),
]
for form_title, ev_idx, uname, answers in fa_data:
    if ev_idx < len(events_list):
        FormAnswer.objects.get_or_create(
            form=forms[form_title],
            event=events_list[ev_idx],
            filled_by=users[uname],
            defaults={"answers": answers}
        )
print(f"   {FormAnswer.objects.count()} form answers")

# ─────────────────────────────────────────────────────────
# 8. REPORTS
# ─────────────────────────────────────────────────────────
print("8/10  Reports...")
report_defs = [
    ("Weekly Threat Landscape - Energy Sector", "Summarize all threats targeting energy sector this week", [0,1,6,20], "analyst1", "completed",
     "## Executive Summary\n\nThe energy sector faced **4 major threats** this week:\n\n### Critical Findings\n1. **LockBit 3.0 ransomware** targeting European infrastructure (MONT)\n2. **APT29/Sandworm** SCADA reconnaissance (RTE)\n3. **DDoS attacks** on grid monitoring (RTE)\n4. **Siemens supply chain compromise** (EDF)\n\n### Trend Analysis\n- Ransomware remains the #1 threat vector\n- State-sponsored actors increasing activity\n- Supply chain attacks emerging as key risk\n\n### Recommendations\n- Deploy network segmentation for OT/IT\n- Implement zero-trust for remote access\n- Enhance SCADA monitoring\n- Review Siemens software supply chain", 1250, 8.5, "gemini", "gemini-1.5-flash"),
    ("NIS2 Compliance Gap Analysis - Healthcare", "Analyze NIS2 compliance gaps for healthcare", [3,5,18], "admin", "completed",
     "## NIS2 Compliance Assessment\n\n### Healthcare Sector Status\n\n#### Identified Gaps\n1. **Incident Reporting**: Delayed notification (>24h threshold)\n2. **Cloud Security**: S3 misconfiguration\n3. **Access Management**: Insufficient DLP controls\n\n#### Compliance Roadmap\n| Quarter | Action | Priority |\n|---------|--------|----------|\n| Q3 2026 | Automated incident reporting | Critical |\n| Q4 2026 | Cloud security posture management | High |\n| Q1 2027 | Zero-trust implementation | High |", 980, 6.2, "gemini", "gemini-1.5-flash"),
    ("IOC Analysis Report - July 2026", "Analyze all IOCs and provide attribution confidence", [0,1,2,4,6,8,13], "analyst1", "generating",
     "", 0, 0, None, None),
    ("Supply Chain Risk Assessment", "Evaluate supply chain risks across all monitored organizations", [9,15,16,17], "analyst2", "pending",
     "", 0, 0, None, None),
    ("APT Activity Digest - Q2 2026", "Comprehensive review of APT group activity in Q2", [1,4,5,6,14], "analyst3", "completed",
     "## APT Activity Digest Q2 2026\n\n### Active Groups\n| Group | Sector | Technique | Confidence |\n|-------|--------|-----------|------------|\n| Sandworm | Energy | SCADA targeting | 95% |\n| APT41 | Telecom | Supply chain | 85% |\n| Volt Typhoon | Transport | Pre-positioning | 88% |\n| FIN7 | Pharma | Spear-phishing | 82% |\n\n### Key Trends\n- **Living-off-the-land** techniques increasing\n- **Supply chain** as initial access vector\n- **OT/ICS** environments becoming primary targets\n- **Pharmaceutical** sector under sustained espionage pressure", 1800, 12.3, "gemini", "gemini-1.5-flash"),
    ("Data Breach Impact Assessment", "Assess financial and reputational impact of recent data breaches", [3,10,11,12], "admin", "failed",
     "", 0, 0, "gemini", "gemini-1.5-flash"),
]
for title, prompt, ev_indices, uname, status, content, tokens, gen_time, provider, model in report_defs:
    r, _ = Report.objects.get_or_create(
        title=title,
        defaults={"prompt": prompt, "generated_content": content, "user": users[uname], "status": status,
                  "tokens_used": tokens or None, "generation_time": gen_time or None,
                  "llm_provider": provider, "llm_model": model,
                  "error_message": "LLM provider timeout after 120s" if status == "failed" else None}
    )
    for idx in ev_indices:
        if idx < len(events_list):
            r.events.add(events_list[idx])
print(f"   {Report.objects.count()} reports")

# ─────────────────────────────────────────────────────────
# 9. PLAYBOOKS
# ─────────────────────────────────────────────────────────
print("9/10  Playbooks...")
playbook_defs = [
    ("PB-RANSOM-001", "Ransomware Response Playbook", 0, [
        {"phase": "Detection", "actions": ["Isolate affected systems", "Notify SOC team", "Preserve forensic evidence", "Identify ransomware variant"]},
        {"phase": "Containment", "actions": ["Block C2 communication", "Segment network", "Disable compromised accounts", "Snapshot affected VMs"]},
        {"phase": "Eradication", "actions": ["Remove malware artifacts", "Patch vulnerabilities", "Reset all credentials", "Review access logs"]},
        {"phase": "Recovery", "actions": ["Restore from clean backups", "Verify system integrity", "Implement enhanced monitoring", "Gradual service restoration"]},
        {"phase": "Post-Incident", "actions": ["Conduct tabletop exercise", "Update detection rules", "Train staff", "Review insurance coverage"]}
    ]),
    ("PB-PHISH-002", "Phishing Response Playbook", 2, [
        {"phase": "Triage", "actions": ["Analyze email headers", "Check attachment hashes", "Identify affected users", "Check for credential submission"]},
        {"phase": "Containment", "actions": ["Block sender domains", "Reset compromised passwords", "Revoke active sessions", "Quarantine delivered emails"]},
        {"phase": "Investigation", "actions": ["Forensic endpoint analysis", "Check lateral movement", "Review access logs", "Analyze network traffic"]},
        {"phase": "Remediation", "actions": ["Deploy email filtering rules", "Update anti-phishing training", "Enhance email authentication (DMARC/DKIM)"]},
    ]),
    ("PB-DATAEXF-003", "Data Exfiltration Response Playbook", 3, [
        {"phase": "Detection", "actions": ["Identify exfiltration channel", "Determine data scope", "Alert DPO", "Preserve evidence"]},
        {"phase": "Containment", "actions": ["Block exfiltration endpoints", "Isolate affected systems", "Revoke compromised credentials"]},
        {"phase": "Assessment", "actions": ["Classify exposed data", "Determine regulatory obligations", "Assess business impact"]},
        {"phase": "Notification", "actions": ["Notify supervisory authority (24h)", "Prepare data subject notification", "Engage legal counsel"]},
        {"phase": "Remediation", "actions": ["Implement DLP controls", "Audit cloud configurations", "Update security policies"]},
    ]),
    ("PB-DDOS-004", "DDoS Mitigation Playbook", 6, [
        {"phase": "Detection", "actions": ["Identify attack vector", "Determine volume and pattern", "Alert network operations center"]},
        {"phase": "Mitigation", "actions": ["Activate DDoS protection service", "Implement rate limiting", "Enable geographic filtering"]},
        {"phase": "Monitoring", "actions": ["Monitor service availability", "Track attack evolution", "Coordinate with ISP"]},
        {"phase": "Recovery", "actions": ["Restore normal traffic patterns", "Post-mortem analysis", "Update mitigation rules"]},
    ]),
    ("PB-INSIDER-005", "Insider Threat Response Playbook", 10, [
        {"phase": "Detection", "actions": ["Verify suspicion", "Engage HR and Legal", "Preserve digital evidence", "Assess access scope"]},
        {"phase": "Investigation", "actions": ["Review access logs", "Analyze DLP alerts", "Interview witnesses", "Forensic device imaging"]},
        {"phase": "Containment", "actions": ["Revoke access immediately", "Recover assets", "Monitor for data destruction"]},
        {"phase": "Resolution", "actions": ["HR disciplinary action", "Legal proceedings if needed", "Update access controls", "Conduct security review"]},
    ]),
    ("PB-SUPPLY-006", "Supply Chain Compromise Response", 16, [
        {"phase": "Identification", "actions": ["Verify compromise", "Identify affected products", "Determine scope of impact"]},
        {"phase": "Containment", "actions": ["Isolate affected systems", "Block malicious packages", "Rollback to last known good"]},
        {"phase": "Investigation", "actions": ["Analyze malware/payload", "Identify attacker timeline", "Check for lateral movement"]},
        {"phase": "Remediation", "actions": ["Update to patched version", "Audit dependencies", "Implement integrity monitoring"]},
        {"phase": "Communication", "actions": ["Notify affected parties", "Update vendor, coordinate disclosure", "Publish IOCs to partners"]},
    ]),
]
for ext_id, name, ev_idx, steps in playbook_defs:
    Playbook.objects.get_or_create(
        external_id=ext_id,
        defaults={"data": {"name": name, "steps": steps}, "event": events_list[ev_idx] if ev_idx < len(events_list) else None}
    )
print(f"   {Playbook.objects.count()} playbooks")

# ─────────────────────────────────────────────────────────
# 10. MISP SERVERS + STRATEGIES
# ─────────────────────────────────────────────────────────
print("10/10 MISP servers & strategies...")
for name, url, key in [
    ("MISP-ANSSI", "https://misp.anssi.fr", "anssi-key-001-prod"),
    ("MISP-EU-ISAC", "https://misp.eu-isac.org", "euisac-key-002-prod"),
    ("MISP-FBI-IC3", "https://ic3.misp.gov", "fbi-key-003-prod"),
    ("MISP-Private", "https://misp.cti4bc.local", "private-key-004-dev"),
]:
    misp, _ = MISPServer.objects.get_or_create(name=name, defaults={"url": url, "apikey": key})
    for o in orgs.values():
        misp.organizations.add(o)

for name, desc, tmpl in [
    ("Share All Critical", "Auto-share critical events with sector partners", {"auto_share": True, "min_severity": "critical"}),
    ("Anonymize Then Share", "Anonymize sensitive fields before external sharing", {"anonymize": True, "fields_to_anon": ["ip","domain","hash"]}),
    ("Sector Only", "Share only within same NIS2 sector", {"scope": "sector"}),
    ("Full Enrichment Required", "Require full enrichment before sharing", {"enrichment_required": True, "min_iocs": 3}),
    ("Rapid Response", "Immediate sharing for critical incidents", {"auto_share": True, "min_severity": "critical", "skip_enrichment": True}),
]:
    strat, _ = Strategy.objects.get_or_create(name=name, defaults={"description": desc, "template": tmpl})
    for o in orgs.values():
        strat.organizations.add(o)

print(f"   {MISPServer.objects.count()} MISP servers, {Strategy.objects.count()} strategies")

# ─────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────
print("\n" + "="*50)
print("  SEED COMPLETE — SUMMARY")
print("="*50)
print(f"  Users:              {User.objects.count()}")
print(f"  Sectors:            {Sector.objects.count()}")
print(f"  Organizations:      {Organization.objects.count()}")
print(f"  Events:             {Event.objects.count()} (shared: {Event.objects.filter(shared=True).count()}, unshared: {Event.objects.filter(shared=False).count()})")
print(f"  Share Logs:         {EventShareLog.objects.count()}")
print(f"  Forms:              {Form.objects.count()}")
print(f"  Form Answers:       {FormAnswer.objects.count()}")
print(f"  Reports:            {Report.objects.count()} (completed: {Report.objects.filter(status='completed').count()}, pending: {Report.objects.filter(status='pending').count()}, generating: {Report.objects.filter(status='generating').count()}, failed: {Report.objects.filter(status='failed').count()})")
print(f"  Playbooks:          {Playbook.objects.count()}")
print(f"  MISP Servers:       {MISPServer.objects.count()}")
print(f"  Strategies:         {Strategy.objects.count()}")
print("="*50)
print("  All passwords: password123")
print("  Admin login: admin / admin")
print("="*50)
