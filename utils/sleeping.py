import asyncio
import random

from loguru import logger

from pynput import keyboard

async def sleep(sleep_from: int, sleep_to: int):
    delay = random.randint(sleep_from, sleep_to)
    logger.info(f"💤 Sleep {delay} s.")

    def on_press(key):
        if key == keyboard.Key.space:
            # Stop listener
            return False

    # Start the keyboard listener
    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    try:
        for _ in range(delay):
            await asyncio.sleep(1)
            if not listener.is_alive():
                break  # Прерываем sleep, если слушатель остановлен
    finally:
        listener.stop()  # Останавливаем слушатель в любом случае

"""
async def sleep(sleep_from: int, sleep_to: int):
    delay = random.randint(sleep_from, sleep_to)

    logger.info(f"💤 Sleep {delay} s.")
    for _ in range(delay):
        await asyncio.sleep(1)
"""
