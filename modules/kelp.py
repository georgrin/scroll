from loguru import logger
from config import KELP_CONTRACT, KELP_WRSETH_CONTRACT, KELP_ABI
from utils.gas_checker import check_gas
from utils.helpers import retry, checkLastIteration, get_action_tx_count
from utils.sleeping import sleep
from .account import Account


class Kelp(Account):
    def __init__(self, account_id: int, private_key: str, recipient: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="scroll", recipient=recipient)

        self.contract = self.get_contract(KELP_CONTRACT, KELP_ABI)

    async def can_withdraw(self):
        amount = await self.get_deposit_amount()
        return amount > 500000000000000  # 0,0005 ETH

    async def get_last_deposit(self):
        return await get_action_tx_count(
            self.account.address,
            self.contract.address,
            'scroll')

    async def check_last_iteration(self, module_cooldown):
        return await checkLastIteration(
            interval=module_cooldown,
            account=self.account,
            deposit_contract_address=self.contract.address,
            chain='scroll',
            log_prefix='Kelp'
        )

    async def get_deposit_amount(self):
        kelp_weth_contract = self.get_contract(KELP_WRSETH_CONTRACT)

        amount = await kelp_weth_contract.functions.balanceOf(self.address).call()

        return amount

    @retry
    @check_gas
    async def deposit(
            self,
            min_amount: float,
            max_amount: float,
            decimal: int,
            all_amount: bool,
            min_percent: int,
            max_percent: int,
            module_cooldown: int
    ):
        last_iter = await self.check_last_iteration(
            module_cooldown,
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

        logger.info(f"[{self.account_id}][{self.address}] Make deposit on Kelp | {amount} ETH")

        tx_data = await self.get_tx_data(amount_wei, gas_price = False)

        transaction = await self.contract.functions.deposit(
            "0xd05723c7b17b4e4c722ca4fb95e64ffc54a70131c75e2b2548a456c51ed7cdaf").build_transaction(tx_data)

        signed_txn = await self.sign(transaction)

        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())
