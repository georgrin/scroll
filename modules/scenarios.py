from loguru import logger

from config import SCROLL_TOKENS
from . import AmbientFinance, Kelp
from .account import Account

wrsETH = "WRSETH"


class Scenarios(Account):
    def __init__(self, account_id: int, private_key: str, recipient: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="scroll", recipient=recipient)

    async def get_wrseth_balance(self) -> int:
        return (await self.get_balance(SCROLL_TOKENS[wrsETH]))["balance_wei"]

    async def stake_eth_and_deposit_wrseth(self, min_eth_balance: float = 0.003, module_cooldown: int = 0):
        logger.info(f"[{self.account_id}][{self.address}] Start stake ETH and deposit {wrsETH}")

        balance_wrseth = await self.get_wrseth_balance()
        balance_eth = await self.w3.eth.get_balance(self.address)

        if balance_eth < self.w3.to_wei(min_eth_balance, "ether"):
            logger.info(f"[{self.account_id}][{self.address}] Cannot stake ETH and deposit {wrsETH} due to low EHT balance: {self.w3.eth.balance_eth / 10 ** 18} < {min_eth_balance}")

            return False

        min_amount = 0.0001
        max_amount = 0.0002
        decimal = 5
        all_amount = True

        # если баланс wrsETH меньше 60% от баланса ETH
        if int(0.6 * balance_eth) > balance_wrseth:
            """
            Make deposit on Kelp
            """

            min_percent = 35
            max_percent = 40

            kelp = Kelp(self.account_id, self.private_key, self.recipient)
            kelp_result = await kelp.deposit(
                min_amount, max_amount, decimal, all_amount, min_percent, max_percent,
                module_cooldown
            )

            if kelp_result is False:
                logger.error(f"Failed to stake wrsETH, result: {kelp_result}, skip deposit to pool")
                return True

        min_percent = 100
        max_percent = 100

        # Percentage width of the range around current pool price (1 = 1%, 0.5 = 0.5%)
        # Tighter ranges accumulate rewards at faster rates, but are more likely to suffer divergence losses.
        range_width = 1  # 0.25, 0.5, 1, 5, 10

        ambient_finance = AmbientFinance(self.account_id, self.private_key, self.recipient)
        deposit_result = await ambient_finance.deposit(
            min_amount, max_amount, decimal, all_amount, min_percent, max_percent, range_width
        )

        if deposit_result is False:
            logger.error(f"Failed to deposit to wrsETH/ETH pool, result: {deposit_result}")
        return True
