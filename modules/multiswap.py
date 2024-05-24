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
        logger.info(f"[{self.account_id}][{self.address}] MultiSwap DEXs with TX count less than {max_tx}: {use_dex}")

        if len(use_dex) == 0:
            raise Exception(f"No dex with tx count less than {max_tx}")

        swap_module = random.choice(use_dex)

        return self.swap_modules[swap_module]

    async def choose_swap_modules(self, use_dex: list, max_tx: int = 1):
        modules_tx_count = await self.get_swap_modules_tx_count()
        modules_tx_count_inv = {}
        for k, v in modules_tx_count.items():
            modules_tx_count_inv[v] = modules_tx_count_inv.get(v, []) + [k]
            random.shuffle(modules_tx_count_inv[v])

        logger.info(f"[{self.account_id}][{self.address}] MultiSwap DEXs TX count: {modules_tx_count_inv}")

        kes_sorted = sorted(modules_tx_count_inv.keys(), key=lambda x: x)
        keys_eligible = filter(lambda tx_count: tx_count < max_tx, kes_sorted)
        modules_eligible = sum([modules_tx_count_inv[k] for k in keys_eligible], [])
        logger.info(f"[{self.account_id}][{self.address}] MultiSwap DEXs sorted and with TX count less than {max_tx}: {modules_eligible}")

        if len(modules_eligible) == 0:
            raise Exception(f"No DEX with tx count less than {max_tx}")

        return [self.swap_modules[module_name] for module_name in modules_eligible]

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
        USDC = "USDC"
        ETH = "ETH"

        quantity_swap = random.randint(min_swap, max_swap)
        usdc_balance = await self.get_balance(SCROLL_TOKENS[USDC])
        usdc_balance = usdc_balance["balance"]

        first_swap_currency = USDC if usdc_balance > 1 else ETH
        second_swap_currency = ETH if first_swap_currency == USDC else USDC

        path = [first_swap_currency if _ % 2 == 0 else second_swap_currency for _ in range(quantity_swap)]

        if back_swap and path[-1] == ETH:
            path.append(USDC)
            path.append(USDC)
            path.append(USDC)

        swap_modules = await self.choose_swap_modules(use_dex, dex_max_tx)

        start_swap = f"{path[0]}->{USDC if path[0] == ETH else ETH}"
        end_swap = f"{path[-1]}->{USDC if path[-1] == ETH else ETH}"

        logger.info(f"[{self.account_id}][{self.address}] Start MultiSwap | quantity swaps: {quantity_swap}, start with {start_swap}, end with {end_swap}")

        needToSleep = True
        for index, token in enumerate(path):
            if token == ETH:
                decimal = 6
                to_token = USDC

                balance = await self.w3.eth.get_balance(self.address)
                min_amount = float(self.w3.from_wei(int(balance / 100 * min_percent), "ether"))
                max_amount = float(self.w3.from_wei(int(balance / 100 * max_percent), "ether"))
            else:
                decimal = 18
                to_token = ETH

                balance = await self.get_balance(SCROLL_TOKENS[USDC])
                min_amount = balance["balance"] if balance["balance"] <= 1 or index + 1 == len(path) \
                    else balance["balance"] / 100 * min_percent
                max_amount = balance["balance"] if balance["balance"] <= 1 or index + 1 == len(path) \
                    else balance["balance"] / 100 * max_percent

                # костыль на весь баланс usdc
                if balance["balance"] <= 1:
                    logger.info(f"[{self.account_id}][{self.address}] USDC balance <= 1")
                    # needToSleep = False
                    continue
                min_amount = balance["balance"]
                max_amount = min_amount

            if index + 1 <= len(swap_modules):
                swap_module = swap_modules[index]
            else:
                logger.info(
                    f"[{self.account_id}][{self.address}] Start MultiSwap | DEXes ended, not enough to ")

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

            if index + 1 != len(path):
                await sleep(sleep_from, sleep_to)
        
        return needToSleep
