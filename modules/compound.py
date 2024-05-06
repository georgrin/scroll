from loguru import logger
from config import COMPOUND_FINANCE_USDC_CONTRACT, COMPOUND_FINANCE_BULKER_CONTRACT, COMPOUND_FINANCE_USDC_ABI, COMPOUND_FINANCE_BULKER_ABI, SCROLL_TOKENS
from utils.gas_checker import check_gas
from utils.helpers import retry, checkLastIteration
from utils.sleeping import sleep
from .account import Account
from .scroll import Scroll
from eth_abi import encode
from hexbytes import HexBytes
from web3 import Web3

class CompoundFinance(Account):
    def __init__(self, account_id: int, private_key: str, recipient: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="scroll", recipient=recipient)

        self.contract_usdc = self.get_contract(COMPOUND_FINANCE_USDC_CONTRACT, COMPOUND_FINANCE_USDC_ABI)
        self.contract = self.get_contract(COMPOUND_FINANCE_BULKER_CONTRACT, COMPOUND_FINANCE_BULKER_ABI)

    async def get_deposit_amount(self):
        amount = await self.contract.functions.balanceOf(self.address).call()

        return amount

    async def is_allow(self):
        return await self.contract_usdc.functions.isAllowed(self.w3.to_checksum_address(self.address), self.w3.to_checksum_address(self.contract.address)).call()

    async def allow(self, contract_address):
        logger.info(f"Allow {contract_address} for {self.address}")

        # await self.approve(amount_wei * 10, self.w3.to_checksum_address(COMPOUND_FINANCE_BULKER_CONTRACT), self.w3.to_checksum_address(COMPOUND_FINANCE_USDC_CONTRACT))

        # tx_data = await self.get_tx_data()
        #
        # transaction = await self.contract_usdc.functions.allow(
        #     self.w3.to_checksum_address(COMPOUND_FINANCE_BULKER_CONTRACT),
        #     True
        # ).build_transaction(tx_data)
        #
        # signed_txn = await self.sign(transaction)
        #
        # txn_hash = await self.send_raw_transaction(signed_txn)
        #
        # await self.wait_until_tx_finished(txn_hash.hex())


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
    ):
        token = "ETH"

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
            token,
            min_amount,
            max_amount,
            decimal,
            all_amount,
            min_percent,
            max_percent
        )

        logger.info(f"[{self.account_id}][{self.address}] Make deposit on CompoundFinance | {amount} {token}")

        if not await self.is_allow():
            logger.info(f"Not allow to deposit")
            await self.allow(COMPOUND_FINANCE_BULKER_CONTRACT)

        tx_data = await self.get_tx_data(amount_wei)

        comet_address = self.contract_usdc.address.lower()
        from_address = self.address.lower()

        amount_hex = format(amount_wei, 'x').zfill(64)

        data_hex = "0x" + comet_address[2:].zfill(64) + from_address[2:].zfill(64) + amount_hex

        transaction = await self.contract.functions.invoke(
            [Web3.to_bytes(text='ACTION_SUPPLY_NATIVE_TOKEN').zfill(32)],
            [Web3.to_bytes(text=data_hex)]
        ).build_transaction(tx_data)

        signed_txn = await self.sign(transaction)

        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())

        if make_withdraw:
            logger.info("Sleep before withdraw")
            await sleep(sleep_from, sleep_to)

            return await self.withdraw()

    @retry
    @check_gas
    async def withdraw(self):
        amount = await self.get_deposit_amount()
        token = "ETH"

        if amount > 0:
            logger.info(
                f"[{self.account_id}][{self.address}] Make withdraw from CompoundFinance | " +
                f"{(amount / 10 ** 18)} {token}"
            )

            tx_data = await self.get_tx_data()

            transaction = await self.contract.functions.withdraw(
                self.w3.to_checksum_address(SCROLL_TOKENS[token]),
                amount,
            ).build_transaction(tx_data)

            signed_txn = await self.sign(transaction)

            txn_hash = await self.send_raw_transaction(signed_txn)

            await self.wait_until_tx_finished(txn_hash.hex())
        else:
            logger.error(f"[{self.account_id}][{self.address}] Deposit not found")
            return False
