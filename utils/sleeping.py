import asyncio
import random

from getch import getch

async def sleep(sleep_from, sleep_to, key='q'):
    delay = random.randint(sleep_from, sleep_to)
    print(f"💤 Sleep {delay} s. Press '{key}' to interrupt.")

    async def wait_for_key():
        while True:
            key_pressed = await asyncio.to_thread(getch)
            if key_pressed == key:
                return True  # Прерываем sleep, если нажата нужная клавиша

    async def sleep_task():
        try:
            for _ in range(delay):
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            print("Sleep interrupted!")

    # Создаём задачи
    sleep_task = asyncio.create_task(sleep_task())
    wait_for_key_task = asyncio.create_task(wait_for_key())

    # Запускаем задачи одновременно и ожидаем завершения любой из них
    done, pending = await asyncio.wait(
        [sleep_task, wait_for_key_task],
        return_when=asyncio.FIRST_COMPLETED
    )

    # Прерываем sleep_task, если она еще не завершена
    for task in pending:
        task.cancel()
    # Прерываем sleep_task, если она еще не завершена
    for task in pending:
        task.cancel()

