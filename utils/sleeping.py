import asyncio
import random

from getch import getch

async def sleep(sleep_from, sleep_to, key='q'):
    delay = random.randint(sleep_from, sleep_to)
    print(f"💤 Sleep {delay} s. Press '{key}' to interrupt.")

    async def wait_for_key():
        try:
            # Ожидаем нажатия клавиши с таймаутом
            key_pressed = await asyncio.wait_for(asyncio.to_thread(getch), timeout=delay)  
            # Проверяем, нажата ли нужная клавиша
            if key_pressed == key:
                return True  # Прерываем sleep
            else:
                return False  # Игнорируем другие клавиши
        except asyncio.TimeoutError:
            return False  # Таймаут, клавиша не нажата

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
