import time
import aiohttp

from aiohttp_socks import ProxyType, ProxyConnector, ChainProxyConnector
from loguru import logger
from web3 import Web3

from config import KYBERSWAP_ROUTER_ABI, KYBERSWAP_CONTRACTS, SCROLL_TOKENS
from utils.gas_checker import check_gas
from utils.helpers import retry
from .account import Account


class KyberSwapAPI:
    def __init__(self):
        connector = ProxyConnector.from_url(f"socks5://127.0.0.1:1080")
        self._session = aiohttp.ClientSession(connector=connector)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        if not self._session.closed:
            await self._session.close()

    async def get_route(self, from_token: str, to_token: str, amount) -> dict:
        url = "https://aggregator-api.kyberswap.com/534352/api/v1/routes"

        params = {
            "tokenIn": from_token,
            "tokenOut": to_token,
            "amountIn": amount,
        }

        async with self._session as session:
            response = await session.get(url=url, params=params)

            if response.status == 200:
                res_json = await response.json()

                if res_json["data"]:
                    return res_json["data"]
                else:
                    logger.error("Kyberswap did not return the best route")

                    return None
            else:
                print(response)
                logger.error("Bad Kyberswap request")

                return None

    async def build_swap(self, route: dict, sender: str, recipient: str, slippage: int) -> dict:
        url = "https://aggregator-api.kyberswap.com/534352/api/v1/route/build"

        body = {
            "routeSummary": route,
            "slippageTolerance": slippage,
            "sender": sender,
            "recipient": recipient,
        }

        async with self._session as session:
            response = await session.post(url=url, body=body)

            if response.status == 200:
                res_json = await response.json()

                if res_json["data"]:
                    return res_json["data"]
                else:
                    logger.error("Kyberswap did not return swap data")

                    return None
            else:
                logger.error("Bad Kyberswap request")

                return None

class KyberSwap(Account):
    def __init__(self, account_id: int, private_key: str, recipient: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="scroll", recipient=recipient)

        self.swap_contract = self.get_contract(KYBERSWAP_CONTRACTS["router"], KYBERSWAP_ROUTER_ABI)
        self.api = KyberSwapAPI()

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
            f"[{self.account_id}][{self.address}] Swap on KyberSwap – {from_token} -> {to_token} | {amount} {from_token}"
        )

        last_iter = await checkLastIteration(
            interval=module_cooldown,
            account=self.account,
            deposit_contract_address=KYBERSWAP_CONTRACTS["router"],
            chain=from_chain,
            log_prefix='KyberSwap'
        )
        if not last_iter:
            return False

        from_token = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE" if from_token == "ETH" else SCROLL_TOKENS[from_token]
        to_token = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE" if to_token == "ETH" else SCROLL_TOKENS[to_token]

        async with self.api as api:
            route = await api.get_route(from_token, to_token, amount_wei)

            print(route)

            if route is None:
                return False

            swap = await api.build_swap(route, self.address, self.address, slippage)

            encoded_swap_data = swap["data"]
            tx_data = await self.get_tx_data(amount_wei if from_token == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE" else 0)
            contract_txn = await self.swap_contract.functions.swap(
                encoded_swap_data
            ).build_transaction(tx_data)

            signed_txn = await self.sign(contract_txn)
            txn_hash = await self.send_raw_transaction(signed_txn)

            await self.wait_until_tx_finished(txn_hash.hex())
