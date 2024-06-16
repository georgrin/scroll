from typing import Dict

import aiohttp
from aiohttp_socks import ProxyType, ProxyConnector, ChainProxyConnector
from loguru import logger
from config import SCROLL_TOKENS, ZERO_ADDRESS, ODOS_SWAP_CONTRACTS, ODOS_ROUTER_ABI
from settings import PROXY
from utils.gas_checker import check_gas
from utils.helpers import retry, get_action_tx_count
from .account import Account


def get_connector():
    return None if PROXY is None or PROXY.strip() == "" else ProxyConnector.from_url(PROXY)


class Odos(Account):
    def __init__(self, account_id: int, private_key: str, recipient: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="scroll", recipient=recipient)

        self.headers = {"Content-Type": "application/json"}
        self.swap_contract = self.get_contract(ODOS_SWAP_CONTRACTS["router"], ODOS_ROUTER_ABI)

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
            log_prefix='Odos'
        )

    async def get_quote(self, from_token: str, to_token: str, amount: int, slippage: float):
        url = "https://api.odos.xyz/sor/quote/v2"

        body = {
            "chainId": await self.w3.eth.chain_id,
            "inputTokens": [
                {
                    "tokenAddress": self.w3.to_checksum_address(from_token),  # checksummed input token address
                    "amount": str(amount),  # input amount as a string in fixed integer precision
                }
            ],
            "outputTokens": [
                {
                    "tokenAddress": self.w3.to_checksum_address(to_token),  # checksummed output token address
                    "proportion": 1
                }
            ],
            "slippageLimitPercent": slippage,  # set your slippage limit percentage (1 = 1%)
            "userAddr": self.address,  # checksummed user address
            "referralCode": 0,  # referral code (recommended)
            "disableRFQs": True,
            "compact": True,
        }

        async with aiohttp.ClientSession(connector=get_connector()) as session:
            response = await session.post(url=url, json=body, headers=self.headers)

            quote = await response.json()

            print(quote)

            return quote

    async def assemble_transaction(self, path_id: str):
        url = "https://api.odos.xyz/sor/assemble"

        body = {
            "userAddr": self.address,  # the checksummed address used to generate the quote
            "pathId": path_id,  # pathId from quote response
            "simulate": False, # this can be set to true if the user isn't doing their own estimate gas call for the transaction
        }

        async with aiohttp.ClientSession(connector=get_connector()) as session:
            response = await session.post(url=url, json=body, headers=self.headers)

            transaction_data = await response.json()

            return transaction_data

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
            f"[{self.account_id}][{self.address}] Swap on Odos – {from_token} -> {to_token} | {amount} {from_token}"
        )

        from_token = ZERO_ADDRESS if from_token == "ETH" else SCROLL_TOKENS[from_token]
        to_token = ZERO_ADDRESS if to_token == "ETH" else SCROLL_TOKENS[to_token]

        quote = await self.get_quote(from_token, to_token, amount_wei, slippage)

        transaction_data = await self.assemble_transaction(
            quote["pathId"]
        )

        transaction = transaction_data["transaction"]
        transaction["value"] = int(transaction["value"])  # web3py requires the value to be an integer

        print(transaction)

        signed_txn = await self.sign(transaction)

        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())
