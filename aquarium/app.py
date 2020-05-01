import asyncio
import asyncpg

import json

import websockets

from aquarium.models import Measurement


def require_auth(f):
    async def __inner(self, *a, **kw):
        assert self.device_id is not None
        return await f(self, *a, **kw)
    return __inner


class DbRepo:
    def __init__(self, conn):
        self.conn = conn

    async def create_table(self):
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS users(
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

class Device:
    def __init__(self, websocket, repo):
        self.websocket = websocket
        self.device_id = None
        self.repo = repo

        self.cmds = {
            'auth': self._auth,
            'm': self._measurement
        }

    async def _auth(self, data):
        assert data['key'] == 'auth'
        self.device_id = data['id']

    @require_auth
    async def _measurement(self, data):
        measurement = Measurement.from_dict(data)
        print(f"< {measurement} {self.device_id}")  

    async def run(self):
        while True:
            msg = json.loads(await self.websocket.recv())
            
            cmd = msg['cmd']
            cmd_f = self.cmds[cmd]

            await cmd_f(msg['data'])


class Server:
    def __init__(self):
        self.conn = None
        self.repo = None
    
    async def connect(self):
        self.conn = await asyncpg.connect(
            user='postgres', password='postgres', database='postgres',
            host='postgres')
        self.repo = DbRepo(self.conn)
        await self.repo.create_table()

    async def hello(self, websocket, path):

        d = Device(websocket, self.repo)
        try:
            await d.run()
        except Exception as e:
            print(type(e), e)

serv = Server()
asyncio.get_event_loop().run_until_complete(serv.connect())
start_server = websockets.serve(serv.hello, "0.0.0.0", 8000)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()

