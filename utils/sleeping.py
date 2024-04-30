import random

from loguru import logger

import asyncio
import aioconsole

import curses

async def sleep(sleep_from, sleep_to):
    delay = random.randint(sleep_from, sleep_to)
    print(f"💤 Sleep {delay} s. Press Enter to interrupt.")

    def handle_input(stdscr):
        curses.noecho()  # Отключаем отображение вводимых символов
        curses.cbreak()  # Режим немедленного чтения ввода
        stdscr.keypad(True)  # Включаем поддержку специальных клавиш

        while True:
            key = stdscr.getch()
            if key == 10:  # Код клавиши Enter
                return True

    async def sleep_task():
        try:
            for _ in range(delay):
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            print("Sleep interrupted!")

    # Запускаем задачи одновременно
    loop = asyncio.get_event_loop()
    with curses.initscr() as stdscr:  # Инициализация ncurses
        done, pending = await asyncio.wait(
            [sleep_task(), loop.run_in_executor(None, handle_input, stdscr)],
            return_when=asyncio.FIRST_COMPLETED
        )

    # Прерываем sleep_task, если она еще не завершена
    for task in pending:
        task.cancel()

"""
async def sleep(sleep_from, sleep_to, key='q'):
    delay = random.randint(sleep_from, sleep_to)
    print(f"💤 Sleep {delay} s. Press '{key}' to interrupt.")

    async def wait_for_key():
        while True:
            key_pressed = await aioconsole.ainput()
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
