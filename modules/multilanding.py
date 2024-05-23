import random
from typing import Union

from loguru import logger
from config import SCROLL_TOKENS
from modules import *
from utils.sleeping import sleep


class Multilanding(Account):
    def __init__(self, account_id: int, private_key: str, recipient: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="scroll", recipient=recipient)

        self.landing_modules = {
            "layerbank": LayerBank(self.account_id, self.private_key, self.recipient),
            "aave": Aave(self.account_id, self.private_key, self.recipient),
            "compoundfinance": CompoundFinance(self.account_id, self.private_key, self.recipient),
        }

    async def get_last_iter(self, module_cooldown):
        return {module_name: await self.landing_modules[module_name].check_last_iteration(module_cooldown) for module_name in self.landing_modules}

    async def get_landing_module(self, use_dex: list, module_cooldown):
        modules_last_iter = await self.get_last_iter(module_cooldown)

        logger.info(f"[{self.account_id}][{self.address}] MultiLanding DEXs can run statuses: {modules_last_iter}")

        use_dex = [dex for dex in use_dex if modules_last_iter[dex] is not False]
        logger.info(f"[{self.account_id}][{self.address}] MultiLanding DEXs with can run: {use_dex}")

        if len(use_dex) == 0:
            return None

        landing_module = random.choice(use_dex)

        return self.landing_modules[landing_module]

    async def deposit(
            self,
            use_dex,
            min_amount: float,
            max_amount: float,
            decimal: int,
            sleep_from: int,
            sleep_to: int,
            all_amount: bool,
            min_percent: int,
            max_percent: int,
            module_cooldown: int,
    ):
        landing_module = await self.get_landing_module(use_dex, module_cooldown)

        if not landing_module:
            logger.info(f"[{self.account_id}][{self.address}] No module to run in MultiLanding")

            return False

        logger.info(f"[{self.account_id}][{self.address}] Start MultiLanding | choose {landing_module.get_name()}")

        needToSleep = True

        await landing_module.deposit(
            min_amount, max_amount, decimal, sleep_from, sleep_to, False, all_amount, min_percent, max_percent,
            module_cooldown
        )

        await sleep(sleep_from, sleep_to)
        
        return needToSleep
