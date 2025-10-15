_URL_ROOT = ''
_URL = ''
_HEADERS = {}


def _configure(url_root=None, headers=None):
    global _URL_ROOT, _URL, _HEADERS
    _URL_ROOT = url_root
    _URL = _URL_ROOT + '/feeds'
    _HEADERS = headers
