import asyncio
import os
from typing import Optional, List

import asyncpg
from aiohttp import web
from aiohttp.web_exceptions import HTTPForbidden

from aquarium.models import Measurement, Config, TempMeasurement

DEVICE_AUTH = os.environ['DEVICE_AUTH']
DB_HOST = os.getenv('DB_HOST', 'postgres')


class DbRepo:
    def __init__(self, db_pool):
        self.db_pool = db_pool

    async def create_tables(self):
        async with self.db_pool.acquire() as conn:
            await conn.execute('''
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
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS config(
                    device_id INTEGER PRIMARY KEY,
                    temp REAL DEFAULT 25.0,
                    temp_tolerance REAL DEFAULT 0.5,
                    light_start TIME WITH TIME ZONE DEFAULT '09:00',               
                    light_end TIME WITH TIME ZONE DEFAULT '21:00',
                    pump_start TIME WITH TIME ZONE DEFAULT '00:00',               
                    pump_end TIME WITH TIME ZONE DEFAULT '23:59'              
                )
            ''')

    async def add_measurement(self, device_id: int, measurement: Measurement):
        async with self.db_pool.acquire() as conn:
            await conn.execute(
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
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
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
            self, device_id: int, count: int) -> List[TempMeasurement]:
        count = min(count, 200)
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                '''SELECT DISTINCT
                       date_trunc('minute', "time") AS time
                     , avg(temp) OVER (PARTITION BY date_trunc('minute', "time")) AS temp
                FROM   measurements
                WHERE device_id = $1 ORDER BY time DESC LIMIT $2''',
                device_id, count
            )
        return [TempMeasurement(
            time=r['time'].isoformat(),
            temp=r['temp']
        ) for r in rows]

    async def get_last_measurement(
            self, device_id: int) -> Optional[Measurement]:
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                '''SELECT * FROM measurements WHERE device_id = $1
                ORDER BY time DESC LIMIT 1''', device_id
            )
        if not rows:
            return None
        r = rows[0]
        return Measurement(
            time=r['time'].isoformat(),
            temp=r['temp'],
            heater=r['heater'],
            pump=r['pump'],
            light=r['light'],
            uptime=r['uptime']
        )


class Server:
    def __init__(self):
        self.db_pool = None
        self.repo = None

    async def connect(self):
        self.db_pool = await asyncpg.create_pool(
            user='postgres', password='postgres', database='postgres',
            host=DB_HOST)
        self.repo = DbRepo(self.db_pool)
        await self.repo.create_tables()

    async def config(self, request):
        cfg = await self.repo.get_config(int(request.match_info['device_id']))
        if cfg is None:
            raise web.HTTPNotFound
        return web.json_response(cfg.to_dict())

    async def measurement(self, request):
        if request.headers.get('AUTHORIZATION') != DEVICE_AUTH:
            raise HTTPForbidden()

        device_id = int(request.match_info['device_id'])
        measurement = Measurement.from_dict(await request.json())
        await self.repo.add_measurement(device_id, measurement)
        return web.json_response(
            (await self.repo.get_config(device_id)).to_dict())

    async def history(self, request):
        res = await self.repo.get_measurements(
            int(request.match_info['device_id']),
            int(request.query.get('n', 200))
        )
        return web.json_response({
            'measurements': [m.to_dict() for m in res]
        })

    async def last_measurement(self, request):
        res = await self.repo.get_last_measurement(
            int(request.match_info['device_id'])
        )
        return web.json_response(res.to_dict())

    async def index(self, request):
        return web.FileResponse('html/index.html')


srv = Server()
app = web.Application()

asyncio.get_event_loop().run_until_complete(srv.connect())
app.router.add_get(r'/config/{device_id:\d+}', srv.config)
app.router.add_post(r'/measurement/{device_id:\d+}', srv.measurement)
app.router.add_get(r'/measurement/{device_id:\d+}', srv.last_measurement)
app.router.add_get(r'/history/{device_id:\d+}', srv.history)
app.router.add_get(r'/', srv.index)
web.run_app(app, port=8000)
