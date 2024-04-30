import asyncio
import random

from getch import getch

async def sleep(sleep_from, sleep_to, key='q'):
    delay = random.randint(sleep_from, sleep_to)
    print(f"💤 Sleep {delay} s. Press '{key}' to interrupt or any other key to exit.")

async def wait_for_key():
    while True:
        try:
            key_pressed = await asyncio.to_thread(getch)
            if key_pressed == key:
                return True
        except KeyboardInterrupt:
            print("Interrupted by keyboard!")
            return False

    async def sleep_task():
        try:
            for _ in range(delay):
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            print("Sleep interrupted!")

    done, pending = await asyncio.wait(
        [sleep_task(), wait_for_key()],
        return_when=asyncio.FIRST_COMPLETED
    )

    for task in pending:
        task.cancel()
        
"""
async def sleep(sleep_from, sleep_to, key='q'):
    delay = random.randint(sleep_from, sleep_to)
    print(f"💤 Sleep {delay} s. Press '{key} and Enter' to interrupt.")

    async def wait_for_key():
        while True:
            key_pressed = await asyncio.to_thread(getch)
            if key_pressed == key:
                return True

    async def sleep_task():
        try:
            for _ in range(delay):
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            print("Sleep interrupted!")

    # Запускаем задачи одновременно
    done, pending = await asyncio.wait(
        [sleep_task(), wait_for_key()],
        return_when=asyncio.FIRST_COMPLETED
    )

    # Прерываем sleep_task, если она еще не завершена
    for task in pending:
        task.cancel()
"""
