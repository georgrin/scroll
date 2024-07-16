import random
from datetime import datetime
from onecache import AsyncCacheDecorator

import aiohttp

from loguru import logger
from eth_account.messages import encode_defunct
from aiohttp_socks import ProxyType, ProxyConnector, ChainProxyConnector
from web3 import Web3

from settings import USE_PROXIES, EXPLORER_CACHE_S
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
    SCROLL_CANVAS_ETHEREUM_YEAR_BADGE_CONTRACT,
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

    async def create_random_names_spinxo(self, proxy=None):
        url = "https://www.spinxo.com/services/NameService.asmx/GetNames"
        payload = '{"snr":{"category":0,"UserName":"","Hobbies":"","ThingsILike":"","Numbers":"","WhatAreYouLike":"","Words":"","Stub":"nicknames","LanguageCode":"en","NamesLanguageID":"45","Rhyming":false,"OneWord":false,"UseExactWords":false,"ScreenNameStyleString":"Any","GenderAny":false,"GenderMale":false,"GenderFemale":false}}'
        headers = {
            "Content-Type": "application/json; charset=UTF-8"
        }

        async with aiohttp.ClientSession(connector=ProxyConnector.from_url(proxy) if proxy else None) as session:
            response = await session.post(url=url, data=payload, headers=headers)

            if response.status == 200:
                response_data = await response.json()
                if "d" in response_data and "Names" in response_data["d"]:
                    nicknames = response_data["d"]["Names"]
                    if type(nicknames) is list:
                        return nicknames
                    else:
                        raise Exception(f"Unexpected format for 'Names': {nicknames}")
                else:
                    raise Exception(f"Missing 'd' or 'Names' in response: {response_data}")
            else:
                raise Exception(f"Random nicknames request failed: {response.status}:{response}")


    @retry
    async def get_random_name(self, canvas_contract):
        random_names = await self.create_random_names_spinxo()

        for name in random_names:
            is_name_used = await canvas_contract.functions.isUsernameUsed(name).call()
            if not is_name_used:
                return name
        raise Exception(f"All random nicknames are already used: {random_names}")

    @retry
    @AsyncCacheDecorator(ttl=1000)
    async def get_wallet_canvas_referral_code(self, address: str, proxy=None):
        if not proxy:
            proxy = get_random_proxy()

        logger.info(f"[{self.account_id}][{self.address}][{self.chain}] use proxy: {proxy}")

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
    @AsyncCacheDecorator(ttl=15)
    async def referral_code_sign(self, referral_code: str, proxy=None):
        if not proxy:
            proxy = get_random_proxy()

        logger.info(f"[{self.account_id}][{self.address}][{self.chain}] use proxy: {proxy}")

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
            wallets = [row.strip().lower() for row in file if row.strip() != ""]

            if self.address.lower() not in wallets:
                file.write(f"{self.address}\n")
            else:
                logger.info(f"[{self.account_id}][{self.address}][{self.chain}] Account already in file")

    @retry
    async def create_and_send_mint_tx(self, name, canvas_contract, mint_fee, referral_code_sign):
        tx_data = await self.get_tx_data(mint_fee, False)

        transaction = await canvas_contract.functions.mint(
            name,
            Web3.to_bytes(hexstr=referral_code_sign)
        ).build_transaction(tx_data)

        signed_txn = await self.sign(transaction)
        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())

    @retry
    async def mint_canvas(self, min_left_eth_balance: float = 0.0014):
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

        mint_fee = int(mint_fee * 0.5) if len(referral_code_sign) > 0 else mint_fee

        # мы проверяем что после транзакции на аккаунте останется минимальный баланс из настроек
        balance_eth = await self.w3.eth.get_balance(self.address)
        if min_left_eth_balance > 0 and balance_eth - mint_fee < self.w3.to_wei(min_left_eth_balance, "ether"):
            logger.info(
                f"[{self.account_id}][{self.address}] Cannot mint Scroll canvas, " +
                f"because left balance would be less than {min_left_eth_balance} ETH, mint cost is {mint_fee / 10 ** 18} ETH, balance {balance_eth / 10 ** 18} ETH"
            )
            return False

        await self.create_and_send_mint_tx(name, canvas_contract, mint_fee, referral_code_sign)

        # await sleep(EXPLORER_CACHE_S)
        await sleep(30)

        is_minted = await self.is_profile_minted()

        if is_minted:
            await self.add_account_to_referral_file()

    @retry
    @AsyncCacheDecorator(ttl=15)
    async def get_mint_badge_tx_data(self, badge_address: str, proxy=None):
        if not proxy:
            proxy = get_random_proxy()

        logger.info(f"[{self.account_id}][{self.address}][{self.chain}] use proxy: {proxy}")

        url = "https://canvas.scroll.cat/badge/claim"
        params = {
            "badge": badge_address,
            "recipient": self.address
        }

        async with aiohttp.ClientSession(connector=ProxyConnector.from_url(proxy) if proxy else None) as session:
            response = await session.get(url=url, params=params)

            if response.status == 200:
                data = await response.json()

                # {
                #     "code": 1,
                #     "message": "success",
                #     "tx" : {
                #         "to": "0x39fb5e85c7713657c2d9e869e974ff1e0b06f20c",
                #         "data": "0x3c0427150000000000000000000000000000000000000000000000000000000000000020d57de4f41c3d3cc855eadef68f98c0d4edd22d57161d96b7c06d2f4336cc3b4900000000000000000000000000000000000000000000000000000000000000e0000000000000000000000000000000000000000000000000000000000000001babbbec56de19e2d02db1119f3a8413b3c822c52ce5b0cbf4461a01184d02347d66bd701ab0ce3c526fc194dfd4572a8d111268cc0b6f2bdcba1d7591b6623a1a00000000000000000000000069c352b8a1d62eed22ee3cd81ee91f00dcd90f9600000000000000000000000000000000000000000000000000000000669594a9000000000000000000000000762b6ed8df8aba7ea400f3a84189eb8525384ef600000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000c0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000800000000000000000000000003dacad961e5e2de850f5e027c70b56b5afa5dfed0000000000000000000000000000000000000000000000000000000000000040000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000007e8"
                #     }
                # }

                if "message" in data and data["message"] == "success" and "tx" in data:
                    return data["tx"]
                else:
                    raise Exception(f"Bad get Scroll mint badge sign signature: {response.status}:{data}")
            else:
                raise Exception(f"Failed to get Scroll mint badge sign signature: {response.status}")

    @retry
    async def mint_ethereum_year_badge(self, min_eth_balance: float = 0.0005):
        is_minted = await self.is_profile_minted()
        if not is_minted:
            logger.info(f"[{self.account_id}][{self.address}][{self.chain}] Account have to minted canvas before mint badges")
            return False

        # мы проверяем что на аккаунте есть минимальный баланс нативки
        balance_eth = await self.w3.eth.get_balance(self.address)
        if min_eth_balance > 0 and balance_eth < self.w3.to_wei(min_eth_balance, "ether"):
            logger.info(
                f"[{self.account_id}][{self.address}] Cannot mint Scroll Ethereum Year Badge, " +
                f"due to small ETH balance {balance_eth / 10 ** 18} ETH, min balance should be {min_eth_balance} ETH"
            )
            return False

        mint_ethereum_year_badge_tx_data = await self.get_mint_badge_tx_data(SCROLL_CANVAS_ETHEREUM_YEAR_BADGE_CONTRACT)

        tx_data = await self.get_tx_data(0, False)

        tx_data["to"] = self.w3.to_checksum_address(mint_ethereum_year_badge_tx_data["to"])
        tx_data["data"] = mint_ethereum_year_badge_tx_data["data"]

        signed_txn = await self.sign(tx_data)
        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())
