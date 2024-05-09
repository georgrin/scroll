from loguru import logger
from config import LAYERBANK_CONTRACT, LAYERBANK_WETH_CONTRACT, LAYERBANK_ABI
from utils.gas_checker import check_gas
from utils.helpers import retry, checkLastIteration
from utils.sleeping import sleep
from .account import Account


class LayerBank(Account):
    def __init__(self, account_id: int, private_key: str, recipient: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="scroll", recipient=recipient)

        self.contract = self.get_contract(LAYERBANK_CONTRACT, LAYERBANK_ABI)

    async def get_deposit_amount(self):
        weth_contract = self.get_contract(LAYERBANK_WETH_CONTRACT)

        amount = await weth_contract.functions.balanceOf(self.address).call()

        return amount

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
            module_cooldown: int
    ):
        amount_wei, amount, balance = await self.get_amount(
            "ETH",
            min_amount,
            max_amount,
            decimal,
            all_amount,
            min_percent,
            max_percent
        )
        last_iter = await checkLastIteration(
            interval=module_cooldown,
            account=self.account,
            deposit_contract_address=self.contract.address,
            chain='scroll',
            log_prefix='Layerbank'
        )
        if not last_iter:
            return False
            
        logger.info(f"[{self.account_id}][{self.address}] Make deposit on LayerBank | {amount} ETH")

        tx_data = await self.get_tx_data(amount_wei)

        transaction = await self.contract.functions.supply(
            self.w3.to_checksum_address(LAYERBANK_WETH_CONTRACT),
            amount_wei,
        ).build_transaction(tx_data)

        signed_txn = await self.sign(transaction)

        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())

        if make_withdraw:
            await sleep(sleep_from, sleep_to)

            return await self.withdraw()
            
    @retry
    @check_gas
    async def withdraw(self):
        amount = await self.get_deposit_amount()

        if amount > 50000000000000: # 0,00005 ETH
            logger.info(
                f"[{self.account_id}][{self.address}] Make withdraw from LayerBank | " +
                f"{self.w3.from_wei(amount, 'ether')} ETH"
            )

            await self.approve(amount, LAYERBANK_WETH_CONTRACT, LAYERBANK_CONTRACT)

            tx_data = await self.get_tx_data()

            transaction = await self.contract.functions.redeemUnderlying(
                self.w3.to_checksum_address(LAYERBANK_WETH_CONTRACT),
                amount,
            ).build_transaction(tx_data)

            signed_txn = await self.sign(transaction)

            txn_hash = await self.send_raw_transaction(signed_txn)

            await self.wait_until_tx_finished(txn_hash.hex())
        else:
            logger.error(f"[{self.account_id}][{self.address}] Deposit not found or deposited amount too small: {amount} WEI")
            return False
