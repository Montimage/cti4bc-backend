from . import event
from . import feed

import os

_URL = 'http://replace_with_your_misp_instance.com'
_HEADERS = {'Accept': 'application/json',
            'Content-Type': 'application/json', 'Authorization': 'YOUR_API_KEY'}
_IS_CONFIGURED = False
_SSL_CERTIFICATE_PATH = ''


def configure(url=None, api_key=None):
    '''
    Configure the URL and API key for the MISP instance.
    Call this function ONLY when no ENV variables set or when calling an external MISP.

    url: [OPTIONAL] string
        The address of the MISP instance
        If not provided it will be read from environment variable `MISP_URL`.
    api_key: [OPTIONAL] string
        The API token authorized to use MISP services.
        If not provided it will be read from environment variable `MISP_TOKEN`.
    '''
    global _URL, _HEADERS, _IS_CONFIGURED
    try:
        _URL = url if url != None else os.environ['MISP_URL']
        _token = api_key if api_key != None else os.environ['MISP_TOKEN']
        _HEADERS = {'Accept': 'application/json',
                    'Content-Type': 'application/json', 'Authorization': _token}
        event._configure(_URL, _HEADERS)
        feed._configure(_URL, _HEADERS)
        _IS_CONFIGURED = True
    except Exception as e:
        print('Error configuring MISP:', e)
        print('MISP_URL and MISP_TOKEN must be set in env variables, or use configure(url,token)')


# On module loading, try to configure defaults only if environment variables exist
try:
    if 'MISP_URL' in os.environ and 'MISP_TOKEN' in os.environ:
        configure()
except:
    pass  # Don't configure automatically if env vars are not set
