import aiohttp
from .. import risk
import json
import ssl

_URL_ROOT = ''
_URL = ''
_HEADERS = {}
_SSL_CONTEXT = None


def _configure(url_root=None, headers=None, ssl_cert_path=None):
    global _URL_ROOT, _URL, _HEADERS, _SSL_CONTEXT
    _URL_ROOT = url_root
    _URL = _URL_ROOT + '/events'
    _HEADERS = headers
    if ssl_cert_path:
        try:
            _SSL_CONTEXT = ssl.SSLContext()
            _SSL_CONTEXT.load_verify_locations(cafile=ssl_cert_path)
        except Exception as e:
            print(e)
    else:
        _SSL_CONTEXT = False


async def _get(url):
    '''
    Generic GET for any endpoint
    '''
    async with aiohttp.ClientSession(raise_for_status=True, connector=aiohttp.TCPConnector(ssl=_SSL_CONTEXT)) as session:
        async with session.get(url, headers=_HEADERS) as res:
            return await res.json()


async def _post(url, data=None):
    '''
    Generic POST for any endpoint.
    > Note: for debugging, disable `raise_for_status` and read response payload.
    405 error: usually the JSON (the object) is not what expected
    403 error: typically token with limited access to that resource, 
               also when payload is ok but value is similar to existing object
    '''
    async with aiohttp.ClientSession(raise_for_status=True, connector=aiohttp.TCPConnector(ssl=_SSL_CONTEXT)) as session:
        async with session.post(url, headers=_HEADERS, data=json.dumps(data, indent=4)) as resp:
            return await resp.json()


async def list():
    '''
    Return available events
    '''
    return await _get(f'{_URL}')


async def get(event_id):
    return (await _get(f'{_URL}/{event_id}'))['Event']


async def get_attribute(attr_id):
    return (await _get(f'{_URL_ROOT}/attributes/{attr_id}'))['Attribute']


async def set_attribute(event_id, attribute):
    await _post(f'{_URL_ROOT}/attributes/add/{event_id}', data=attribute)


async def list_tags(event_id):
    return (await get(event_id))['Tag']


async def get_tag(event_id, tag_id):
    tags = await list_tags(event_id)
    for tag in tags:
        if tag['id'] == tag_id:
            return tag
    return None


async def set_tag(event_id, tag):
    '''
    Important: this is adding a tag to an event.
    To avoid pollution on creating many tags, use taxonomies or create a custom taxonomy instead.
    Otherwise tags created by one user can be useless for other ones.
    '''
    found = await get_tag(event_id, tag['id'])
    if not found:
        await _post(f'{_URL}/addTag/{event_id}/{tag["id"]}')


async def enrich(id):
    '''
    Add risk info and extra tagging
    - for risk, see attribute
    - for tags, see taxonomy examples in event #1
    '''
    event = await get(id)
    attributes = event['Attribute']
    is_enriched = False
    for attr in attributes:
        if attr['comment'].startswith('RISK'):
            is_enriched = True
            break
    # TODO: detect the damaged target from the caller of this function
    target = 'HES'

    if is_enriched is False:
        id = event['id']
        attr = risk.to_misp_attribute(id, target)
        await set_attribute(id, attr)

async def add(event, dist=0, published=False):
   
   """
   Post a new event to url events/add

   Params:
   - event (Dict): Dictionary to be sent in json, format {"Event": {...}}
   - dist (int): who can see the event, default=0 (0=this organization, 1=this community, 2=connected communities, 3=All communities, 4= Sharing group, 5= inherit event)
   - published (Boolean): Publish this event
   """
   if not "distribution" in event["Event"]:
       event['Event']['distribution'] = dist
   if not "published" in event['Event']:
       event['Event']['published'] = published
    
   return await _post(f"{_URL}/add", event)