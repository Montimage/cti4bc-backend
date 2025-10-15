'''
Use default type structures only for the required datatypes.

Not all MISP data models are required, and most of them should be 
similar on each minor MISP update. Therefore we do not need to re-import
or refactor. We want some level of MISP integration, but not full.

Also Python is an non-strict-type language. Therefore we will use/provide data
as JSON or as Object types, so the appropriate receipt (either a module in this library
or externally) will know what to do with the objects. For the rest modules, 
it is like a black box with id and type properties.
'''

import copy
from uuid import uuid4
from time import time

_SKELETONS = {
    'misp': {
        "attribute": {
            # "id": "157", # ID should be created by the service
            "type": "url",
            "category": "External analysis",
            "to_ids": False,
            "uuid": "bf2a8c5c-e873-4fb1-a90e-c7ba7e8acc71",
            "event_id": "1",
            "distribution": "0",
            "timestamp": "1690897826",
            "comment": "RISK EVALUATION",
            "sharing_group_id": "0",
            "deleted": False,
            "disable_correlation": False,
            "object_id": "0",
            "object_relation": None,
            "first_seen": None,
            "last_seen": None,
            "value": "http://risk.dynabic.eu",
            "Galaxy": [],
            "ShadowAttribute": []
        },
        "tag": {
            "id": "21",
            "name": "nis2:impact-outlook=\"worsening\"",
            "colour": "#CC0033",
            "exportable": True,
            "user_id": "0",
            "hide_tag": False,
            "numerical_value": None,
            "is_galaxy": False,
            "is_custom_galaxy": False,
            "local_only": False,
            "local": 0,
            "relationship_type": None
        }
    }
}


def get(key):
    '''
    Clone and return a data type with default values

    key: string
    Identifier of the skeleton (e.g.: 'misp.attribute')
    '''
    data = key.split('.')
    skeleton = _SKELETONS[data[0]]
    for r in range(1, len(data)):
        skeleton = skeleton[data[r]]
    obj = copy.deepcopy(skeleton)
    if 'uuid' in obj:
        obj['uuid'] = str(uuid4())
    if 'timestamp' in skeleton:
        obj['timestamp'] = str(int(time()))
    return obj
