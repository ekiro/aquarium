import asyncio
import json
import os
from typing import Optional, List

import aiohttp
import asyncpg
from aiohttp import web

from aquarium.models import Measurement, Config


def require_auth(f):
    async def __inner(self, *a, **kw):
        assert self.device_id is not None
        return await f(self, *a, **kw)

    return __inner


class DbRepo:
    def __init__(self, conn):
        self.conn = conn

    async def create_tables(self):
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS measurements(
                id serial PRIMARY KEY,
                device_id INTEGER,
                time TIMESTAMP WITH TIME ZONE,
                temp REAL,
                heater BOOLEAN,
                light BOOLEAN,
                pump BOOLEAN,
                uptime REAL
            )
        ''')
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS config(
                device_id INTEGER PRIMARY KEY,
                temp REAL DEFAULT 25.0,
                temp_tolerance REAL DEFAULT 0.5,
                light_start TIME WITHOUT TIME ZONE DEFAULT '09:00',               
                light_end TIME WITHOUT TIME ZONE DEFAULT '21:00',
                pump_start TIME WITHOUT TIME ZONE DEFAULT '00:00',               
                pump_end TIME WITHOUT TIME ZONE DEFAULT '23:59'              
            )
        ''')

    async def add_measurement(self, device_id: int, measurement: Measurement):
        await self.conn.execute(
            '''
            INSERT INTO measurements (
                device_id, time, temp, heater, light, pump, uptime
            ) VALUES (
                ($1), ($2), ($3), ($4), ($5), ($6), ($7)
            )
            ''', int(device_id), measurement.time_iso, measurement.temp,
            measurement.heater, measurement.light, measurement.pump,
            measurement.uptime)

    async def get_config(self, device_id: int) -> Optional[Config]:
        rows = await self.conn.fetch(
            "SELECT * FROM config WHERE device_id = $1 LIMIT 1", device_id)
        if not rows:
            return None
        r = rows[0]
        return Config(
            device_id=r['device_id'],
            temp=r['temp'],
            temp_tolerance=r['temp_tolerance'],
            light_start=r['light_start'].isoformat(),
            light_end=r['light_end'].isoformat(),
            pump_start=r['pump_start'].isoformat(),
            pump_end=r['pump_end'].isoformat()
        )

    async def get_measurements(
            self, device_id: int, count: int) -> List[Measurement]:
        count = min(count, 50)
        rows = await self.conn.fetch(
            '''SELECT * FROM measurements WHERE device_id = $1
            ORDER BY time LIMIT $2''', device_id, count
        )
        return [Measurement(
            time=r['time'].isoformat(),
            temp=r['temp'],
            heater=r['heater'],
            pump=r['pump'],
            light=r['light'],
            uptime=r['uptime']
        ) for r in rows]


class Device:
    def __init__(self, websocket, repo: DbRepo):
        self.websocket = websocket
        self.device_id = 123
        # self.device_id = None
        self.repo = repo

        self.cmds = {
            'auth': self._auth,
            'm': self._measurement
        }

    async def _auth(self, data: dict):
        assert data['key'] == os.environ['DEVICE_AUTH']
        self.device_id = data['id']

    @require_auth
    async def _measurement(self, data: dict):
        measurement = Measurement.from_dict(data)
        print(f"< {measurement} {self.device_id}")
        await self.repo.add_measurement(self.device_id, measurement)

    async def run(self):
        async for raw in self.websocket:
            if raw.type == aiohttp.WSMsgType.TEXT:
                msg = json.loads(raw.data)
                cmd = msg['cmd']
                cmd_f = self.cmds[cmd]
                await cmd_f(msg['data'])
            elif raw.type == aiohttp.WSMsgType.ERROR:
                print('ws connection closed with exception %s' %
                      self.websocket.exception())


class Server:
    def __init__(self):
        self.conn = None
        self.repo = None

    async def connect(self):
        self.conn = await asyncpg.connect(
            user='postgres', password='postgres', database='postgres',
            host='postgres')
        self.repo = DbRepo(self.conn)
        await self.repo.create_tables()

    async def hello(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        d = Device(ws, self.repo)
        try:
            await d.run()
        except Exception as e:
            print(type(e), e)

        print('websocket connection closed')

        return ws

    async def config(self, request):
        cfg = await self.repo.get_config(int(request.match_info['device_id']))
        if cfg is None:
            raise web.HTTPNotFound
        return web.json_response(cfg.to_dict())

    async def history(self, request):
        res = await self.repo.get_measurements(
            int(request.match_info['device_id']),
            int(request.query.get('n', 30))
        )
        return web.json_response({
            'measurements': [m.to_dict() for m in res]
        })


srv = Server()
app = web.Application()

asyncio.get_event_loop().run_until_complete(srv.connect())
app.router.add_get('/ws', srv.hello)
app.router.add_get(r'/config/{device_id:\d+}', srv.config)
app.router.add_get(r'/history/{device_id:\d+}', srv.history)
web.run_app(app, port=8000)
