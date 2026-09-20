"""Thread-hosted local WebSocket broadcaster."""

import asyncio
import json
import threading


class WebSocketBridge:
    def __init__(self, host="127.0.0.1", port=8765):
        self.host, self.port = host, port
        self._loop, self._queue = None, None
        self._clients = set()
        self._thread = threading.Thread(target=self._run, name="echohands-websocket", daemon=True)

    def start(self):
        self._thread.start()

    def publish(self, tokens):
        if self._loop and self._queue:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, list(tokens))

    async def _handler(self, websocket):
        self._clients.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            self._clients.discard(websocket)

    async def _broadcast(self):
        while True:
            tokens = await self._queue.get()
            message = json.dumps({"action": "play_sequence", "tokens": tokens})
            clients = tuple(self._clients)
            results = await asyncio.gather(*(client.send(message) for client in clients), return_exceptions=True)
            for client, result in zip(clients, results):
                if isinstance(result, Exception):
                    self._clients.discard(client)

    async def _serve(self):
        import websockets
        self._queue = asyncio.Queue()
        async with websockets.serve(self._handler, self.host, self.port):
            await self._broadcast()

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except Exception as error:
            print(f"WebSocket bridge stopped: {error}")
        finally:
            self._loop.close()