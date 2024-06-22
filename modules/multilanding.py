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
            "rhomarkets": Rhomarkets(self.account_id, self.private_key, self.recipient)
        }

    async def get_last_iter(self, module_cooldown):
        return {module_name: await self.landing_modules[module_name].check_last_iteration(module_cooldown) for module_name in self.landing_modules}

    async def get_can_withdraw_status(self, module_cooldown):
        return {module_name: await self.landing_modules[module_name].check_last_iteration(module_cooldown) for module_name in self.landing_modules}

    async def get_landing_module(self, use_dex: list, module_cooldown):
        modules_last_iter = await self.get_last_iter(module_cooldown)

        logger.info(f"[{self.account_id}][{self.address}] MultiLanding DEXs can deposit statuses: {modules_last_iter}")

        use_dex = [dex for dex in use_dex if modules_last_iter[dex] is not False]
        logger.info(f"[{self.account_id}][{self.address}] MultiLanding DEXs with can deposit: {use_dex}")

        if len(use_dex) == 0:
            return None

        landing_module = random.choice(use_dex)

        return self.landing_modules[landing_module]

    async def get_module_to_withdrawal(self, use_dex: list, module_cooldown):
        modules_last_iter = await self.get_last_iter(module_cooldown)

        logger.info(f"[{self.account_id}][{self.address}] MultiLanding DEXs last tx less than {module_cooldown} sec ago: {modules_last_iter}")
        modules_can_withdraw_statuses = {dex: await self.landing_modules[dex].can_withdraw() for dex in use_dex}

        logger.info(f"[{self.account_id}][{self.address}] MultiLanding DEXs can withdraw statuses: {modules_can_withdraw_statuses}")
        use_dex = [dex for dex in use_dex if modules_last_iter[dex] is not False and modules_can_withdraw_statuses[dex] is True]

        logger.info(f"[{self.account_id}][{self.address}] MultiLanding DEXs to withdraw: {use_dex}")

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
            make_withdraw: bool,
            withdrawal_cooldown_min,
            withdrawal_cooldown_max,
            all_amount: bool,
            min_percent: int,
            max_percent: int,
            module_cooldown: int,
    ):
        needToSleep = False
        if make_withdraw:
            withdrawal_cooldown = random.randint(withdrawal_cooldown_min, withdrawal_cooldown_max)
            withdrawal_module = await self.get_module_to_withdrawal(use_dex, withdrawal_cooldown)

            if withdrawal_module:
                needToSleep = True
                await withdrawal_module.withdraw()
                await sleep(sleep_from, sleep_to)

        landing_module = await self.get_landing_module(use_dex, module_cooldown)

        if not landing_module:
            logger.info(f"[{self.account_id}][{self.address}] No module to run in MultiLanding")
            return needToSleep

        logger.info(f"[{self.account_id}][{self.address}] Start MultiLanding | choose {landing_module.get_name()}")

        needToSleep = True

        await landing_module.deposit(
            min_amount, max_amount, decimal, sleep_from, sleep_to, False, all_amount, min_percent, max_percent,
            module_cooldown
        )

        await sleep(sleep_from, sleep_to)
        return needToSleep
