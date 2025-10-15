'''
Simple web server

Use only when starting CTI as standalone is required.
Otherwise, keep using this repo as a library.
'''
from aiohttp import web
import json
from cti4bc import risk

PORT = 8001


async def handle_get(request):
    return web.Response(text='CTI4BC (temporary) standalone server')


async def handle_post(request):
    obj = json.loads(await request.text())
    if 'Event' in obj:
        event = obj.get('Event')
        print(f'Sending incident with event id = {event["id"]} to Risk')
        obj = await risk.notify_risk(event)
        return web.json_response(obj)
    return web.Response(text="OK")


app = web.Application()
app.router.add_get('/', handle_get)
app.router.add_post('/', handle_post)
web.run_app(app, port=PORT)
