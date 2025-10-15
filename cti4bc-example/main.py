###################################################
# Example of using MISP and RISK
###################################################

import asyncio
# import cti4bc.misp as misp
from cti4bc import misp


async def main():
    try:
        # Optional
        # misp.configure(url,api_key)
        events = await misp.event.list()
        id = events[0]['id']
        event = await misp.event.get(id)
        print(event)
    except Exception as e:
        # handle e.code, e.status
        print(e)

if __name__ == "__main__":
    asyncio.run(main())
