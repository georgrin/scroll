import time
import aiohttp

from loguru import logger
from web3 import Web3
from config import SUSHISWAP_ROUTER_ABI, SUSHISWAP_CONTRACTS, SCROLL_TOKENS
from utils.gas_checker import check_gas
from utils.helpers import retry, checkLastIteration, get_action_tx_count
from .account import Account


class SushiSwap(Account):
    def __init__(self, account_id: int, private_key: str, recipient: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="scroll", recipient=recipient)

        self.swap_contract = self.get_contract(SUSHISWAP_CONTRACTS["router"], SUSHISWAP_ROUTER_ABI)
        self.native_token_address = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"

    async def get_action_tx_count(self):
        return await get_action_tx_count(
            self.account.address,
            self.swap_contract.address,
            'scroll')

    async def check_last_iteration(self, module_cooldown):
        return await checkLastIteration(
            interval=module_cooldown,
            account=self.account,
            deposit_contract_address=self.swap_contract.address,
            chain='scroll',
            log_prefix='SushiSwap'
        )

    async def build_swap(self, from_token: str, to_token: str, amount: int) -> dict:
        url = "https://api.sushi.com/swap/v4/534352"

        params = {
            "tokenIn": from_token,
            "tokenOut": to_token,
            "amount": amount,
            "gasInclude": "true",
            "preferSushi": "true",
            "to": self.address,
            "maxPriceImpact": 0.05
        }

        async with aiohttp.ClientSession() as session:
            response = await session.get(url=url, params=params)

            if response.status == 200:
                res_json = await response.json()

                if "routeProcessorArgs" in res_json and res_json["routeProcessorArgs"]:
                    return res_json
                else:
                    logger.error(f"SushiSwap did not return swap data: {res_json}")

                    return None
            else:
                logger.error(f"Bad SushiSwap request: {response}")

                return None

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
            max_percent: int,
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
        if amount < 10 ** -6:
            logger.info(f"Cannot swap {amount} {from_token}, amount too small")

            return False

        if from_token != "ETH":
            logger.info(f"Check if {from_token} is allow to swap")
            await self.approve(int(amount_wei * 100), SCROLL_TOKENS[from_token], SUSHISWAP_CONTRACTS["router"])

        from_token = self.native_token_address if from_token == "ETH" else SCROLL_TOKENS[from_token]
        to_token = self.native_token_address if to_token == "ETH" else SCROLL_TOKENS[to_token]

        swap = await self.build_swap(from_token, to_token, amount_wei)

        if swap is None:
            return False

        tx_data = await self.get_tx_data(amount_wei if from_token == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE" else 0)

        tx_swap = await self.swap_contract.functions.processRoute(
            Web3.to_checksum_address(from_token),
            amount_wei,
            Web3.to_checksum_address(to_token),
            int(swap["routeProcessorArgs"]["amountOutMin"]),
            Web3.to_checksum_address(self.address),
            Web3.to_bytes(hexstr=swap["routeProcessorArgs"]["routeCode"]),
        ).build_transaction(tx_data)

        signed_txn = await self.sign(tx_swap)
        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())
