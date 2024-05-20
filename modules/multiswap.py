import random
from typing import Union

from loguru import logger
from config import SCROLL_TOKENS
from modules import *
from utils.sleeping import sleep


class Multiswap(Account):
    def __init__(self, account_id: int, private_key: str, recipient: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="scroll", recipient=recipient)

        self.swap_modules = {
            "syncswap": SyncSwap(self.account_id, self.private_key, self.recipient),
            "skydrome": Skydrome(self.account_id, self.private_key, self.recipient),
            "zebra": Zebra(self.account_id, self.private_key, self.recipient),
            "xyswap": XYSwap(self.account_id, self.private_key, self.recipient),
            "ambient_finance": AmbientFinance(self.account_id, self.private_key, self.recipient),
            "kyberswap": KyberSwap(self.account_id, self.private_key, self.recipient),
            "sushiswap": SushiSwap(self.account_id, self.private_key, self.recipient),
            "openocean": OpenOcean(self.account_id, self.private_key, self.recipient),
        }

    async def get_swap_modules_tx_count(self):
        return {module_name: await self.swap_modules[module_name].get_action_tx_count() for module_name in self.swap_modules}

    async def get_swap_module(self, use_dex: list, max_tx: int = 1):
        modules_tx_count = await self.get_swap_modules_tx_count()

        logger.info(f"[{self.account_id}][{self.address}] MultiSwap DEXs TX count: {modules_tx_count}")

        use_dex = [dex for dex in use_dex if modules_tx_count[dex] < max_tx]
        logger.info(f"[{self.account_id}][{self.address}] MultiSwap DEXs with less than {max_tx}: {use_dex}")

        swap_module = random.choice(use_dex)

        return self.swap_modules[swap_module]

    async def swap(
            self,
            use_dex: list,
            sleep_from: int,
            sleep_to: int,
            min_swap: int,
            max_swap: int,
            slippage: Union[int, float],
            back_swap: bool,
            min_percent: int,
            max_percent: int,
            dex_max_tx: int,
    ):
        quantity_swap = random.randint(min_swap, max_swap)
        usdc_balance = await self.get_balance(SCROLL_TOKENS["USDC"])
        usdc_balance = usdc_balance["balance"]

        first_swap_currency = "USDC" if usdc_balance > 1 else "ETH"
        second_swap_currency = "ETH" if first_swap_currency == "USDC" else "USDC"

        path = [first_swap_currency if _ % 2 == 0 else second_swap_currency for _ in range(quantity_swap)]

        if back_swap and path[-1] == "ETH":
            path.append("USDC")
            path.append("USDC")

        logger.info(f"[{self.account_id}][{self.address}] Start MultiSwap | quantity swaps: {quantity_swap}, start with {path[0]}")

        needToSleep = True
        for _, token in enumerate(path):
            if token == "ETH":
                decimal = 6
                to_token = "USDC"

                balance = await self.w3.eth.get_balance(self.address)

                min_amount = float(self.w3.from_wei(int(balance / 100 * min_percent), "ether"))
                max_amount = float(self.w3.from_wei(int(balance / 100 * max_percent), "ether"))
            else:
                decimal = 18
                to_token = "ETH"

                balance = await self.get_balance(SCROLL_TOKENS["USDC"])

                min_amount = balance["balance"] if balance["balance"] <= 1 or _ + 1 == len(path) \
                    else balance["balance"] / 100 * min_percent
                max_amount = balance["balance"] if balance["balance"] <= 1 or _ + 1 == len(path) \
                    else balance["balance"] / 100 * max_percent

                # костыль на весь баланс usdc
                if balance["balance"] <= 1:
                    logger.info(f"[{self.account_id}][{self.address}] USDC balance <= 1")
                    # needToSleep = False
                    continue
                min_amount = balance["balance"]
                max_amount = min_amount
                

            swap_module = await self.get_swap_module(use_dex, dex_max_tx)
            await swap_module.swap(
                token,
                to_token,
                min_amount,
                max_amount,
                decimal,
                slippage,
                False,
                min_percent,
                max_percent
            )

            if _ + 1 != len(path):
                await sleep(sleep_from, sleep_to)
        
        return needToSleep
