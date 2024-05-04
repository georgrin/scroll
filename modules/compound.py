from loguru import logger
from config import COMPOUND_FINANCE_CONTRACT, COMPOUND_FINANCE_ABI, SCROLL_TOKENS
from utils.gas_checker import check_gas
from utils.helpers import retry, checkLastIteration
from utils.sleeping import sleep
from .account import Account
from .scroll import Scroll


class CompoundFinance(Account):
    def __init__(self, account_id: int, private_key: str, recipient: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="scroll", recipient=recipient)

        self.contract = self.get_contract(COMPOUND_FINANCE_CONTRACT, COMPOUND_FINANCE_ABI)

    async def get_deposit_amount(self):
        amount = await  self.contract.functions.balanceOf(self.address).call()

        return amount

    @retry
    @check_gas
    async def _wrap_eth(
            self,
            amount_wei: int,
            amount: float,
    ):
        weth_contract = self.get_contract(SCROLL_TOKENS["WETH"], WETH_ABI)

        logger.info(f"[{self.account_id}][{self.address}] Wrap {amount} ETH")

        tx_data = await self.get_tx_data(amount_wei)

        transaction = await weth_contract.functions.deposit().build_transaction(tx_data)

        signed_txn = await self.sign(transaction)

        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())

    @retry
    @check_gas
    async def deposit(
            self,
            min_amount: float,
            max_amount: float,
            decimal: int,
            sleep_from: int,
            sleep_to: int,
            make_withdraw: bool,
            all_amount: bool,
            min_percent: int,
            max_percent: int,
            module_cooldown: int,
            wrap_eth: bool
    ):

        last_iter = await checkLastIteration(
            interval=module_cooldown,
            account=self.account,
            deposit_contract_address=self.contract.address,
            chain='scroll',
            log_prefix='CompoundFinance'
        )
        if not last_iter:
            return False

        amount_wei, amount, balance = await self.get_amount(
            "ETH",
            min_amount,
            max_amount,
            decimal,
            all_amount,
            min_percent,
            max_percent
        )
        
        logger.info(f"[{self.account_id}][{self.address}] Make deposit on CompoundFinance | {amount} {token}")

        await self.approve(amount_wei * 10, SCROLL_TOKENS[token], self.w3.to_checksum_address(COMPOUND_FINANCE_CONTRACT))

        tx_data = await self.get_tx_data()

        transaction = await self.contract.functions.supply(
            self.w3.to_checksum_address(SCROLL_TOKENS["WETH"]),
            amount_wei
        ).build_transaction(tx_data)

        signed_txn = await self.sign(transaction)
        
        txn_hash = await self.send_raw_transaction(signed_txn)
        
        await self.wait_until_tx_finished(txn_hash.hex())
        
        if make_withdraw:
            print("Make withdraw")
            # await sleep(sleep_from, sleep_to)
            #
            # return await self.withdraw()
