import time
import aiohttp

from aiohttp_socks import ProxyType, ProxyConnector, ChainProxyConnector
from loguru import logger
from web3 import Web3

from config import KYBERSWAP_ROUTER_ABI, KYBERSWAP_CONTRACTS, SCROLL_TOKENS, PROXY
from utils.gas_checker import check_gas
from utils.helpers import retry, checkLastIteration, get_action_tx_count
from .account import Account


class KyberSwapAPI:
    def __init__(self):
        self.connector = None if PROXY is None or PROXY.strip() == "" else ProxyConnector.from_url(PROXY)

    async def get_route(self, from_token: str, to_token: str, amount) -> dict:
        url = "https://aggregator-api.kyberswap.com/scroll/api/v1/routes"

        params = {
            "tokenIn": from_token,
            "tokenOut": to_token,
            "amountIn": amount,
            "gasInclude": "True"
        }

        async with aiohttp.ClientSession(connector=self.connector) as session:
            response = await session.get(url=url, params=params)

            if response.status == 200:
                res_json = await response.json()

                if res_json["data"]:
                    return res_json["data"]
                else:
                    logger.error("Kyberswap did not return the best route")

                    return None
            else:
                logger.error(f"Bad Kyberswap request: {response}")

                return None

    async def build_swap(self, route: dict, sender: str, recipient: str, slippage: int) -> dict:
        url = "https://aggregator-api.kyberswap.com/scroll/api/v1/route/build"

        body = {
            "routeSummary": route["routeSummary"],
            "slippageTolerance": slippage,
            "sender": sender,
            "recipient": recipient,
        }

        async with aiohttp.ClientSession(connector=self.connector) as session:
            response = await session.post(url=url, json=body)

            if response.status == 200:
                res_json = await response.json()

                if res_json["data"]:
                    return res_json["data"]
                else:
                    logger.error("Kyberswap did not return swap data")

                    return None
            else:
                logger.error(f"Bad Kyberswap request: {response}")

                return None

class KyberSwap(Account):
    def __init__(self, account_id: int, private_key: str, recipient: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="scroll", recipient=recipient)

        self.swap_contract = self.get_contract(KYBERSWAP_CONTRACTS["router"], KYBERSWAP_ROUTER_ABI)
        self.api = KyberSwapAPI()
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
            log_prefix='KyberSwap'
        )

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
            f"[{self.account_id}][{self.address}] Swap on KyberSwap – {from_token} -> {to_token} | {amount} {from_token}"
        )
        if amount < 10 ** -6:
            logger.info(f"Cannot swap {amount} {from_token}, amount too small")

            return False

        if from_token != "ETH":
            logger.info(f"Check if {from_token} is allow to swap")
            await self.approve(int(amount_wei * 100), SCROLL_TOKENS[from_token], self.swap_contract.address)

        from_token = self.native_token_address if from_token == "ETH" else SCROLL_TOKENS[from_token]
        to_token = self.native_token_address if to_token == "ETH" else SCROLL_TOKENS[to_token]

        route = await self.api.get_route(from_token, to_token, amount_wei)

        if route is None:
            return False

        swap = await self.api.build_swap(route, self.address, self.address, slippage)

        if swap is None:
            return False

        tx_data = await self.get_tx_data(amount_wei if from_token == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE" else 0)
        tx_swap = { "data": Web3.to_bytes(hexstr=swap["data"]), "gas": swap["gas"], "to": swap["routerAddress"], **tx_data }

        signed_txn = await self.sign(tx_swap)
        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())
