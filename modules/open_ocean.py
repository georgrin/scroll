import time
import aiohttp

from loguru import logger
from web3 import Web3
from config import OPENOCEAN_ROUTER_ABI, OPENOCEAN_CONTRACTS, SCROLL_TOKENS
from utils.gas_checker import check_gas
from utils.helpers import retry
from .account import Account


class OpenOcean(Account):
    def __init__(self, account_id: int, private_key: str, recipient: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="scroll", recipient=recipient)

        self.swap_contract = self.get_contract(OPENOCEAN_CONTRACTS["router"], OPENOCEAN_ROUTER_ABI)
        self.native_token_address = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"

    async def build_swap(self,
                         from_token: str,
                         from_token_address: str,
                         to_token: str,
                         to_token_address: str,
                         amount: int,
                         slippage: int) -> dict:
        url = "https://ethapi.openocean.finance/v2/534352/swap"

        params = {
            "inTokenSymbol": from_token,
            "inTokenAddress":  from_token_address,
            "outTokenSymbol": to_token,
            "outTokenAddress": to_token_address,
            "amount": amount,
            "gasPrice": 200000000,
            "slippage": int(100 * slippage),
            "account": self.account.address,
            "referrer": "0x3487ef9f9b36547e43268b8f0e2349a226c70b53",
            "flags": 0,
        }

        async with aiohttp.ClientSession() as session:
            response = await session.get(url=url, params=params)

            if response.status == 200:
                res_json = await response.json()

                if "data" in res_json and res_json["data"]:
                    return res_json
                else:
                    logger.error(f"OpenOceanSwap did not return swap data: {res_json}")

                    return None
            else:
                logger.error(f"Bad OpenOceanSwap request: {response}")

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
            f"[{self.account_id}][{self.address}] Swap on KyberSwap – {from_token} -> {to_token} | {amount} {from_token}"
        )
        if amount < 10 ** -6:
            logger.info(f"Cannot swap {amount} {from_token}, amount too small")

            return False

        if from_token != "ETH":
            logger.info(f"Check if {from_token} is allow to swap")
            await self.approve(int(amount_wei * 100), SCROLL_TOKENS[from_token], OPENOCEAN_CONTRACTS["router"])

        from_token_address = self.native_token_address if from_token == "ETH" else SCROLL_TOKENS[from_token]
        to_token_address = self.native_token_address if to_token == "ETH" else SCROLL_TOKENS[to_token]

        swap = await self.build_swap(from_token, from_token_address , to_token, to_token_address, amount_wei, slippage)

        if swap is None:
            return False

        tx_data = await self.get_tx_data(amount_wei if from_token == "ETH" else 0)

        tx_swap = {"data": Web3.to_bytes(hexstr=swap["data"]), "gas": swap["estimatedGas"], "to": self.swap_contract.address,
                   **tx_data}

        signed_txn = await self.sign(tx_swap)
        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())
