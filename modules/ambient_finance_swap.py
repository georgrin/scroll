import time

from loguru import logger
from web3 import Web3
from eth_abi import encode
from config import AMBIENT_FINANCE_ROUTER_ABI, AMBIENT_FINANCE_CROC_ABI, AMBIENT_FINANCE_CONTRACTS, SCROLL_TOKENS
from utils.gas_checker import check_gas
from utils.helpers import retry, checkLastIteration
from .account import Account
from decimal import Decimal


class AmbientFinance(Account):
    def __init__(self, account_id: int, private_key: str, recipient: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="scroll", recipient=recipient)

        self.swap_contract = self.get_contract(AMBIENT_FINANCE_CONTRACTS["router"], AMBIENT_FINANCE_ROUTER_ABI)
        self.croc_contract = self.get_contract(AMBIENT_FINANCE_CONTRACTS["croc_query"], AMBIENT_FINANCE_CROC_ABI)
        self.pool_ids = { "ETH/USDC": 420 }
        self.eth_address = "0x0000000000000000000000000000000000000000"

    async def check_last_iteration(self, module_cooldown):
        return await checkLastIteration(
            interval=module_cooldown,
            account=self.account,
            deposit_contract_address=self.swap_contract.address,
            chain='scroll',
            log_prefix='AmbientFinance'
        )

    async def _swap(
            self,
            base: str,
            quote: str,
            pool_id: int,
            amount: int,
            is_buy: bool,
            in_base_amount: bool,
            min_out: int,
            limit_price: int,
            settle_flags: int = 0,
            tip: int = 0
    ):
        tx_data = await self.get_tx_data(amount if base == self.eth_address and is_buy is True else 0)

        # ('0x0000000000000000000000000000000000000000', '0x06efdbff2a14a7c8e15944d1f4a48f9f95f663a4', 420, True, True,
        #  700000000000000, 0, 21267430153580247136652501917186561137, 2059128, 0)

        callpath_code = 1
        cmd = encode(
            ["address","address","uint256","bool","bool","uint128","uint16","uint128","uint128","uint8"],
            [base,quote,pool_id,is_buy,in_base_amount,amount,tip,limit_price,min_out,settle_flags]
        )

        transaction = await self.swap_contract.functions.userCmd(
            callpath_code,
            cmd
        ).build_transaction(tx_data)

        return transaction

    async def get_price(
            self,
            base: str,
            quote: str,
            pool_id: int,
            is_buy: bool
    ):
        price = int((await self.croc_contract.functions.queryPrice(
            Web3.to_checksum_address(base),
            Web3.to_checksum_address(quote),
            pool_id
        ).call() / (2 ** 64)) ** 2)

        return 1 / price if is_buy else price

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
            f"[{self.account_id}][{self.address}] Swap on AmbientFinance – {from_token} -> {to_token} | {amount} {from_token}"
        )

        if amount < 10 ** -6:
            logger.info(f"Cannot swap {amount} {from_token}, amount too small")

            return False

        is_buy = from_token == "ETH"
        is_base_amount = from_token == "ETH"  # TODO: fix it
        base = self.eth_address
        quote = SCROLL_TOKENS[to_token] if from_token == "ETH" else SCROLL_TOKENS[from_token]
        pool_id = 420

        # return price
        price = await self.get_price(base, quote, pool_id, is_buy)

        min_amount_out_wei = int(float(price) * float(amount_wei))
        min_amount_out_wei =  int(min_amount_out_wei * (1 - slippage / 100))

        logger.info(f"Get pool price: {price}, set min amount out wei")

        # Using a meaningful value here is not necessary if the caller is uninterested in partial fills and slippage is set with minOut parameter value
        # In this case this value can be set to "max values" below based on the direction of the swap:
        limit_price = 21267430153580247136652501917186561137 if is_buy else 65537

        if from_token != "ETH":
            logger.info(f"Check if {from_token} is allow to swap")
            await self.approve(int(amount_wei * 100), SCROLL_TOKENS[from_token], self.swap_contract.address)

        contract_txn = await self._swap(base,
                                        quote,
                                        pool_id,
                                        amount_wei,
                                        is_buy,
                                        is_base_amount,
                                        min_amount_out_wei,
                                        limit_price)

        signed_txn = await self.sign(contract_txn)
        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())
