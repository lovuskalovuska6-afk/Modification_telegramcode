"""Один поток + свой asyncio loop для всех клиентов Telethon.

Uvicorn и Telethon нельзя раскидывать по разным воркерам: клиент живёт
в памяти процесса и привязан к event loop, в котором его создали.
Иначе список чатов пустой или падает с 'event loop must not change'.
"""

import asyncio
import threading
from functools import wraps


class TgLoop:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, name="telethon-loop", daemon=True)
        self.thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()


tg_loop = TgLoop()


def on_tg_loop(fn):
    @wraps(fn)
    async def wrapper(self, *args, **kwargs):
        running = asyncio.get_running_loop()
        if running is tg_loop.loop:
            return await fn(self, *args, **kwargs)
        fut = asyncio.run_coroutine_threadsafe(fn(self, *args, **kwargs), tg_loop.loop)
        return await asyncio.wrap_future(fut)

    return wrapper
