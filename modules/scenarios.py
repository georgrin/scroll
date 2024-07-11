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

    async def stake_eth_and_deposit_wrseth(self,
                                           decimal: int,
                                           kelp_min_amount: float,
                                           kelp_max_amount: float,
                                           kelp_all_amount: bool,
                                           kelp_min_percent: int,
                                           kelp_max_percent: int,
                                           ambient_min_amount: float,
                                           ambient_max_amount: float,
                                           ambient_all_amount: bool,
                                           ambient_min_percent: int,
                                           ambient_max_percent: int,
                                           ambient_range_width: float,
                                           min_eth_balance: float = 0.003):
        logger.info(f"[{self.account_id}][{self.address}] Start stake ETH and deposit {wrsETH}")

        balance_wrseth = await self.get_wrseth_balance()
        balance_eth = await self.w3.eth.get_balance(self.address)

        logger.info(
            f"[{self.account_id}][{self.address}] balance: {balance_eth / 10 ** 18} ETH, {balance_wrseth / 10 ** 18} {wrsETH}")

        if balance_eth < self.w3.to_wei(min_eth_balance, "ether"):
            logger.info(f"[{self.account_id}][{self.address}] Cannot stake ETH and deposit {wrsETH} due to low EHT balance: {balance_eth / 10 ** 18} < {min_eth_balance}")
            return False

        # если баланс wrsETH меньше 60% от баланса ETH
        if int(0.6 * balance_eth) > balance_wrseth:
            """
            Make deposit on Kelp
            """

            kelp = Kelp(self.account_id, self.private_key, self.recipient)
            kelp_result = await kelp.deposit(
                kelp_min_amount, kelp_max_amount, decimal, kelp_all_amount, kelp_min_percent, kelp_max_percent,
                0
            )

            if kelp_result is False:
                logger.error(f"Failed to stake wrsETH, result: {kelp_result}, skip deposit to pool")
                return True

        ambient_finance = AmbientFinance(self.account_id, self.private_key, self.recipient)
        deposit_result = await ambient_finance.deposit(
            ambient_min_amount, ambient_max_amount, decimal, ambient_all_amount, ambient_min_percent, ambient_max_percent, ambient_range_width
        )

        if deposit_result is False:
            logger.error(f"Failed to deposit to wrsETH/ETH pool, result: {deposit_result}")
        return True
