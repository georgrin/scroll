import time

from loguru import logger
from web3 import Web3
from config import SUSHISWAP_ROUTER_ABI, SUSHISWAP_CONTRACTS, SCROLL_TOKENS
from utils.gas_checker import check_gas
from utils.helpers import retry
from .account import Account


class SushiSwap(Account):
    def __init__(self, account_id: int, private_key: str, recipient: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="scroll", recipient=recipient)

        self.swap_contract = self.get_contract(SUSHISWAP_CONTRACTS["router"], SUSHISWAP_ROUTER_ABI)

    async def _swap(self, from_token: str, to_token: str, amount: int, slippage: int):
        tx_data = await self.get_tx_data(amount)

        pass

    @retry
    @check_gas
    async def swap(
            self,
            from_token: str,
            to_token: str,
            min_amount: float,
            max_amount: float,
            decimal: int,
            slippage: int,
            all_amount: bool,
            min_percent: int,
            max_percent: int
    ):
        amount_wei, amount, balance = await self.get_amount(
            from_token,
            min_amount,
            max_amount,
            decimal,
            all_amount,
            min_percent,
            max_percent
        )

        logger.info(
            f"[{self.account_id}][{self.address}] Swap on SushiSwap – {from_token} -> {to_token} | {amount} {from_token}"
        )

        from_token = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE" if from_token == "ETH" else SCROLL_TOKENS[from_token]
        to_token = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE" if to_token == "ETH" else SCROLL_TOKENS[to_token]

        pass
