import random
from datetime import datetime

import aiohttp

from loguru import logger
from eth_account.messages import encode_defunct
from aiohttp_socks import ProxyType, ProxyConnector, ChainProxyConnector
from web3 import Web3

from settings import USE_PROXIES
from utils.gas_checker import check_gas
from utils.helpers import retry, checkLastIteration
from utils.sleeping import sleep
from .account import Account

from config import (
    BRIDGE_CONTRACTS,
    DEPOSIT_ABI,
    DEPOSIT_ECONOMY_ABI,
    WITHDRAW_ABI,
    ORACLE_ABI,
    SCROLL_CANVAS_ABI,
    SCROLL_CANVAS_CONTRACT,
    SCROLL_TOKENS,
    WETH_ABI,
    PROXIES,
)


def get_random_proxy():
    if USE_PROXIES and (PROXIES is None or len(PROXIES) == 0):
        return None
    else:
        return random.choice(PROXIES)


class Scroll(Account):
    def __init__(self, account_id: int, private_key: str, chain: str, recipient) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain=chain, recipient=recipient)
        self.connector = None

    @retry
    @check_gas
    async def deposit(
            self,
            min_amount: float,
            max_amount: float,
            decimal: int,
            all_amount: bool,
            min_percent: int,
            max_percent: int
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

        logger.info(f"[{self.account_id}][{self.address}] Bridge to Scroll | {amount} ETH")

        contract = self.get_contract(BRIDGE_CONTRACTS["deposit"], DEPOSIT_ABI)
        contract_oracle = self.get_contract(BRIDGE_CONTRACTS["oracle"], ORACLE_ABI)

        fee = await contract_oracle.functions.estimateCrossDomainMessageFee(168000).call()

        tx_data = await self.get_tx_data(amount_wei + fee, False)

        transaction = await contract.functions.sendMessage(
            self.address,
            amount_wei,
            "0x",
            168000,
        ).build_transaction(tx_data)

        signed_txn = await self.sign(transaction)

        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())

    @retry
    @check_gas
    async def deposit_economy(
            self,
            min_amount: float,
            max_amount: float,
            decimal: int,
            all_amount: bool,
            min_percent: int,
            max_percent: int
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

        logger.info(f"[{self.account_id}][{self.address}] Bridge to Scroll | {amount} ETH")

        # TODO: добавить проверку, что мы отправляем не меньше, чем 0.01 ETH

        # You can only use "Economy" for deposit more than 0.01 ETH
        if amount_wei < 10000000000000000:
            raise ValueError(f"You can only use 'Economy' for deposit more than 0.01 ETH, try to send: {amount}")

        contract = self.get_contract(BRIDGE_CONTRACTS["deposit_economy"], DEPOSIT_ECONOMY_ABI)
        contract_oracle = self.get_contract(BRIDGE_CONTRACTS["oracle"], ORACLE_ABI)

        # Тут скорее всего неправильно считается комса для экономного депозита
        fee = await contract_oracle.functions.estimateCrossDomainMessageFee(168000).call()

        tx_data = await self.get_tx_data(amount_wei + fee, False)

        transaction = await contract.functions.depositETH().build_transaction(tx_data)

        signed_txn = await self.sign(transaction)

        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())

    @retry
    @check_gas
    async def withdraw(
            self,
            min_amount: float,
            max_amount: float,
            decimal: int,
            all_amount: bool,
            min_percent: int,
            max_percent: int
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

        logger.info(f"[{self.account_id}][{self.address}] Bridge from Scroll | {amount} ETH")

        contract = self.get_contract(BRIDGE_CONTRACTS["withdraw"], WITHDRAW_ABI)

        tx_data = await self.get_tx_data(amount_wei)

        transaction = await contract.functions.withdrawETH(
            amount_wei,
            0
        ).build_transaction(tx_data)

        signed_txn = await self.sign(transaction)

        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())

    @retry
    @check_gas
    async def wrap_eth(
            self,
            min_amount: float,
            max_amount: float,
            decimal: int,
            all_amount: bool,
            min_percent: int,
            max_percent: int
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

        weth_contract = self.get_contract(SCROLL_TOKENS["WETH"], WETH_ABI)

        logger.info(f"[{self.account_id}][{self.address}] Wrap {amount} ETH")

        tx_data = await self.get_tx_data(amount_wei)

        transaction = await weth_contract.functions.deposit().build_transaction(tx_data)

        signed_txn = await self.sign(transaction)

        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())

    @retry
    @check_gas
    async def unwrap_eth(
            self,
            min_amount: float,
            max_amount: float,
            decimal: int,
            all_amount: bool,
            min_percent: int,
            max_percent: int
    ):
        amount_wei, amount, balance = await self.get_amount(
            "WETH",
            min_amount,
            max_amount,
            decimal,
            all_amount,
            min_percent,
            max_percent
        )

        weth_contract = self.get_contract(SCROLL_TOKENS["WETH"], WETH_ABI)

        logger.info(f"[{self.account_id}][{self.address}] Unwrap {amount} ETH")

        tx_data = await self.get_tx_data()

        transaction = await weth_contract.functions.withdraw(amount_wei).build_transaction(tx_data)

        signed_txn = await self.sign(transaction)

        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())

    async def _check_signed_terms_of_use(self, proxy) -> bool:
        url = "https://venus.scroll.io/v1/signature/address"

        params = {
            "address": self.address,
        }

        async with aiohttp.ClientSession(connector=ProxyConnector.from_url(proxy) if proxy else None) as session:
            response = await session.get(url=url, params=params)

            if response.status == 200:
                status = await response.json()

                if status["data"] and int(status["errcode"]) == 0:
                    return True
                else:
                    return False
            else:
                logger.error(f"[{self.account_id}][{self.address}][{self.chain}] Bad Scroll request")

                raise Exception(f"Bad Scroll request: {response.status}")

    async def _sign_terms_of_use(self, proxy) -> bool:
        url = "https://venus.scroll.io/v1/signature/sign"

        message = "By signing this message, you acknowledge that you have read and understood the Scroll Sessions Terms of Use, Scroll Terms of Service and Privacy Policy, and agree to abide by all of the terms and conditions contained therein."

        message = encode_defunct(text=message)
        signed_message = self.w3.eth.account.sign_message(message, private_key=self.private_key)

        body = {
            "address": self.address,
            "signature": signed_message.signature.hex(),
            "timestamp": int(datetime.now().timestamp() * 1000)
        }

        async with aiohttp.ClientSession(connector=ProxyConnector.from_url(proxy) if proxy else None) as session:
            response = await session.post(url=url, json=body)

            if response.status == 200:
                status = await response.json()

                if int(status["errcode"]) == 0:
                    logger.info(
                        f"[{self.account_id}][{self.address}][{self.chain}] Scroll Terms of Use successfully signed: {status}")

                    return True
                else:
                    return False
            else:
                logger.error(f"[{self.account_id}][{self.address}][{self.chain}] Bad Scroll sign terms of use request")

                raise Exception(f"Bad Scroll sign terms of use request: {response.status}")

    @retry
    async def sign_terms_of_use(self):
        proxy = get_random_proxy()

        logger.info(f"[{self.account_id}][{self.address}][{self.chain}] use proxy: {proxy}")

        signed = await self._check_signed_terms_of_use(proxy)

        if signed:
            logger.info(f"[{self.account_id}][{self.address}][{self.chain}] Scroll Terms of Use already signed")
            return False

        logger.info(f"[{self.account_id}][{self.address}][{self.chain}] Scroll Terms of Use haven't signed yet")

        return await self._sign_terms_of_use(proxy)

    @retry
    async def is_profile_minted(self):
        # return await canvas_contract.functions.isProfileMinted(self.address).call()

        return not (await checkLastIteration(
            interval=99999999999999999999999,
            account=self.account,
            deposit_contract_address=SCROLL_CANVAS_CONTRACT,
            chain='scroll',
            log_prefix='Scroll Canvas'
        ))

    async def create_random_names(self, proxy=None):
        url = "https://plarium.com/services/api/nicknames/new/create"

        body = {
            "group": 2,
            "gender": 2,
        }

        async with aiohttp.ClientSession(connector=ProxyConnector.from_url(proxy) if proxy else None) as session:
            response = await session.post(url=url, params=body)

            if response.status == 200:
                nicknames = await response.json()

                if type(nicknames) is list:
                    return nicknames
                else:
                    raise Exception(f"Random nicknames bad response: {response.status}:{nicknames}")
            else:
                raise Exception(f"Random nicknames request failed: {response.status}:{response}")

    @retry
    async def get_random_name(self, canvas_contract):
        random_names = await self.create_random_names()

        for name in random_names:
            is_name_used = await canvas_contract.functions.isUsernameUsed(name).call()
            if not is_name_used:
                return name
        raise Exception(f"All random nicknames are already used: {random_names}")

    @retry
    async def get_wallet_canvas_referral_code(self, address: str, proxy=None):
        url = f"https://canvas.scroll.cat/acc/{address}/code"

        async with aiohttp.ClientSession(connector=ProxyConnector.from_url(proxy) if proxy else None) as session:
            response = await session.get(url=url)

            if response.status == 200:
                data = await response.json()

                if "code" in data:
                    return data["code"]
                else:
                    raise Exception(f"Bad get Scroll canvas referral code response: {response.status}:{data}")
            else:
                raise Exception(f"Failed to get Scroll Canvas referral code: {response.status}")

    async def get_random_referral_code(self):
        with open("scroll_canvas_referral_accounts.txt") as file:
            wallets = [row.strip().lower() for row in file]

            while self.address.lower() in wallets:
                wallets.remove(self.address.lower())

            if len(wallets) > 0:
                wallet = random.choice(wallets)

                logger.info(f"Try to get {wallet} referral code")

                return await self.get_wallet_canvas_referral_code(wallet), wallet

            logger.info(f"No accounts to referral")

            return None, None

    @retry
    async def referral_code_sign(self, referral_code: str, proxy=None):
        url = f"https://canvas.scroll.cat/code/{referral_code}/sig/{self.address}"

        async with aiohttp.ClientSession(connector=ProxyConnector.from_url(proxy) if proxy else None) as session:
            response = await session.get(url=url)

            if response.status == 200:
                data = await response.json()

                if "signature" in data:
                    return data["signature"]
                else:
                    raise Exception(f"Bad get Scroll referral code signature: {response.status}:{data}")
            else:
                raise Exception(f"Failed to get Scroll Canvas referral code signature: {response.status}")

    async def add_account_to_referral_file(self):
        logger.info(
            f"[{self.account_id}][{self.address}][{self.chain}] Try to add account to file with accounts with referral code")

        with open("scroll_canvas_referral_accounts.txt", 'r+') as file:
            wallets = [row.strip().lower() for row in file]

            if self.address.lower() not in wallets:
                file.write(f"{self.address}\n")
            else:
                logger.info(f"[{self.account_id}][{self.address}][{self.chain}] Account already in file")

    async def mint_canvas(self):
        canvas_contract = self.get_contract(SCROLL_CANVAS_CONTRACT, SCROLL_CANVAS_ABI)
        is_minted = await self.is_profile_minted()

        if is_minted:
            logger.info(f"[{self.account_id}][{self.address}][{self.chain}] Account already minted canvas")
            await self.add_account_to_referral_file()
            return False

        name = await self.get_random_name(canvas_contract)

        logger.info(f"[{self.account_id}][{self.address}][{self.chain}] Mint Scroll Canvas with random name: {name}")

        mint_fee = await canvas_contract.functions.MINT_FEE().call()

        referral_code, referral_code_wallet = await self.get_random_referral_code()
        referral_code_sign = await self.referral_code_sign(referral_code) if referral_code else ""

        logger.info(
            f"[{self.account_id}][{self.address}][{self.chain}] Mint Scroll Canvas with referral code: {referral_code} ({referral_code_wallet})")

        tx_data = await self.get_tx_data(int(mint_fee * 0.5) if len(referral_code_sign) > 0 else mint_fee)

        transaction = await canvas_contract.functions.mint(
            name,
            Web3.to_bytes(hexstr=referral_code_sign)
        ).build_transaction(tx_data)

        signed_txn = await self.sign(transaction)
        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())

        await sleep(20)

        is_minted = await self.is_profile_minted()

        if is_minted:
            await self.add_account_to_referral_file()
