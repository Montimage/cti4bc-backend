import os
import aiohttp
from . import skeletons

_URL = None
_HEADERS = {}
_IS_CONFIGURED = False


def configure(url=None, token=None):
    global _URL, _HEADERS, _IS_CONFIGURED
    if _IS_CONFIGURED and url and token:
        return
    try:
        _URL = url if url else os.environ['RISK_URL']
        _token = token if token else os.environ['RISK_TOKEN']
        _HEADERS = {'Authorization': os.environ['RISK_TOKEN'], 'Content-Type': 'application/json'}
        _IS_CONFIGURED = True
    except:
        print('RISK_URL and RISK_TOKEN must be set in env variables, or use configure(url,token)')


# On module loading, configure defaults
configure()


async def get(id):
    '''
    Return the address access/display the risk perspective window.
    TODO ARF: we can also send the url of a snapshot, so it can be inserted into a MISP event.
    '''
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{_URL}/{id}', headers=_HEADERS) as resp:
            return (await resp.json())['url']


def to_misp_attribute(event_id, target_name):
    '''
    Return risk information as a MISP event attribute
    TODO ARF: input params depends on trigger.
    - If risk triggers, the name is known, CTI4BC should listen and create the event
    - if other tool triggers, CTI4BC calls this method when creating the event
    - For now risk is a link, so bullets above is one. Later when requiring risk info, this will be split.
    '''
    # Temporary disabled: get info from RISK management tool
    # risk_info=get(id)

    attr = skeletons.get('misp.attribute')
    attr['event_id'] = event_id
    return attr


async def notify_risk(info):
    '''
    Direct notification to RISK (another option is to populate via Kafka).
    This notification is usually an evidence of disruption in one of the assets.
    '''
    async with aiohttp.ClientSession() as session:
        async with session.post(f'{_URL}/advanced', headers=_HEADERS, json=info) as resp:
            return (await resp.json())
