import os
import random
import traceback

from loguru import logger
from eth_account import Account as EthereumAccount
from onecache import CacheDecorator

from config import (SCROLL_TOKENS,
                    OKEX_API_KEY,
                    OKEX_SECRET_KEY,
                    OKEX_PASSPHRASE,
                    OKEX_PROXY,
                    DEPOSITS_ADDRESSES,
                    ACCOUNTS)
from settings import RANDOM_WALLET, RETRY_COUNT
from utils.helpers import get_eth_usd_price, timeout
from utils.sleeping import sleep
from . import AmbientFinance, Kelp, Scroll
from .account import Account
from .okex import Okex

wrsETH = "WRSETH"
AMBIENT_BADGE_CURRENT_ACCOUNTS_FILE = "temp/ambient_badge_current_accounts.txt"
AMBIENT_BADGE_SCENARIO_FINISHED_ACCOUNTS_FILE = "temp/ambient_badge_scenario_finished_accounts.txt"
USD_1000 = 1000


def retry(func, sleep_from: int = 10, sleep_to: int = 20, return_false=True):
    async def wrapper(*args, **kwargs):
        retries = 0
        while retries <= RETRY_COUNT:
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                trace = traceback.format_exc()
                logger.error(f"Error | {e}\n{trace}")
                await sleep(sleep_from, sleep_to)
                retries += 1

                if retries == RETRY_COUNT and return_false is True:
                    return False

    return wrapper


def get_random_account():
    wallets = [
        {
            "id": _id,
            "key": key,
        } for _id, key in enumerate(ACCOUNTS, start=1)
    ]

    if os.path.exists('wl.txt'):
        wallet_addresses = {EthereumAccount.from_key(wallet['key']).address.lower(): wallet for wallet in wallets}

        with open('wl.txt', 'r') as file:
            logger.info(f"wl.txt is specified, filter current accounts")
            existing_addresses = {line.strip().lower() for line in file.readlines()}

        filtered_wallets = [wallet for address, wallet in wallet_addresses.items() if address in existing_addresses]
        wallets = filtered_wallets

    with open(AMBIENT_BADGE_SCENARIO_FINISHED_ACCOUNTS_FILE, 'r') as file:
        wallets_already_finished_scenario = [row.strip().lower() for row in file if row.strip() != ""]
        logger.debug(
            f"There are {len(wallets_already_finished_scenario)} accounts what already finished ambient badge scenario (file: {AMBIENT_BADGE_SCENARIO_FINISHED_ACCOUNTS_FILE})")

    with open(AMBIENT_BADGE_CURRENT_ACCOUNTS_FILE, 'r') as file:
        wallets_to_continue = [row.strip().lower() for row in file if row.strip() != ""]
        logger.debug(
            f"There are {len(wallets_to_continue)} accounts to continue (file: {AMBIENT_BADGE_CURRENT_ACCOUNTS_FILE})")

    wallet_addresses = {EthereumAccount.from_key(wallet['key']).address.lower(): wallet for wallet in wallets}
    filtered_wallets = [wallet for address, wallet in wallet_addresses.items() if
                        address not in wallets_already_finished_scenario and address not in wallets_to_continue]
    wallets = filtered_wallets

    if len(wallets) == 0:
        logger.info(f"There are no new eligible wallets to run script")
        return None

    if RANDOM_WALLET:
        random.shuffle(wallets)

    return wallets[0]


def get_current_accounts():
    wallets = [
        {
            "id": _id,
            "key": key,
        } for _id, key in enumerate(ACCOUNTS, start=1)
    ]

    wallet_addresses = {EthereumAccount.from_key(wallet['key']).address.lower(): wallet for wallet in wallets}
    with open(AMBIENT_BADGE_CURRENT_ACCOUNTS_FILE, 'r') as file:
        current_addresses = [row.strip().lower() for row in file if row.strip() != ""]
        logger.debug(
            f"There are {len(current_addresses)} accounts to continue ambient badge scenario (file: {AMBIENT_BADGE_CURRENT_ACCOUNTS_FILE})")

    filtered_wallets = [wallet for address, wallet in wallet_addresses.items() if address in current_addresses]
    wallets = filtered_wallets

    filtered_addresses = [address for address, wallet in wallet_addresses.items() if address in current_addresses]
    current_addresses_no_private_key = [address for address in current_addresses if address not in filtered_addresses]

    if len(current_addresses_no_private_key) > 0:
        logger.error(
            f"Some addresses in {AMBIENT_BADGE_CURRENT_ACCOUNTS_FILE} have no a private key: {current_addresses_no_private_key}")

    return wallets


def get_acc_address(acc):
    return EthereumAccount.from_key(acc['key']).address.lower()


class Scenarios(Account):
    def __init__(self, account_id: int, private_key: str, recipient: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="scroll", recipient=recipient)
        self.ambient_finance = AmbientFinance(account_id, private_key, recipient)
        self.scroll = Scroll(account_id, private_key, "scroll", recipient)
        self.scroll_ethereum = Scroll(account_id, private_key, "ethereum", recipient)
        self.okex = None

        # используется для текущих аккаунтов для минта значка амбиент за 1000 депозит
        self.current_accounts = []
        self.current_account_index = 0

    def load_account(self, account_id: int, private_key: str):
        if account_id == self.account_id:
            return
        self.account_id = account_id
        self.private_key = private_key

        self.account = EthereumAccount.from_key(private_key)
        self.address = self.account.address
        self.log_prefix = f"[{self.account_id}][{self.address}]"

        self.ambient_finance = AmbientFinance(account_id, private_key, self.recipient)
        self.scroll = Scroll(account_id, private_key, "scroll", self.recipient)
        self.scroll_ethereum = Scroll(account_id, private_key, "ethereum", self.recipient)

    async def get_wrseth_balance(self) -> int:
        return (await self.get_balance(SCROLL_TOKENS[wrsETH]))["balance_wei"]

    async def stake_eth_and_deposit_wrseth(self,
                                           decimal: int,
                                           kelp_min_amount: float,
                                           kelp_max_amount: float,
                                           kelp_all_amount: bool,
                                           kelp_min_percent: int,
                                           kelp_max_percent: int,
                                           ambient_min_amount: float,
                                           ambient_max_amount: float,
                                           ambient_all_amount: bool,
                                           ambient_min_percent: int,
                                           ambient_max_percent: int,
                                           ambient_range_width: float,
                                           min_left_eth_balance: float,
                                           max_left_eth_balance: float,
                                           max_deposit_amount: float,
                                           kelp_module_cooldown: int,
                                           min_eth_balance: float = 0.003):
        logger.info(f"[{self.account_id}][{self.address}] Start stake ETH and deposit {wrsETH}")
        ambient_finance = AmbientFinance(self.account_id, self.private_key, self.recipient)

        current_deposit = await ambient_finance.get_total_deposit_amount()

        logger.info(
            f"[{self.account_id}][{self.address}] Current estimated ETH amount deposited to wrsETH/ETH pool: {current_deposit}")

        if current_deposit > max_deposit_amount:
            logger.info(
                f"[{self.account_id}][{self.address}] Current deposit is greater than max deposit amount: {current_deposit} > {max_deposit_amount}")
            return False

        balance_wrseth = await self.get_wrseth_balance()
        balance_eth = await self.w3.eth.get_balance(self.address)

        logger.info(
            f"[{self.account_id}][{self.address}] balance: {balance_eth / 10 ** 18} ETH, {balance_wrseth / 10 ** 18} {wrsETH}")

        if balance_eth < self.w3.to_wei(min_eth_balance, "ether"):
            logger.info(
                f"[{self.account_id}][{self.address}] Cannot stake ETH and deposit {wrsETH} due to low EHT balance: {balance_eth / 10 ** 18} < {min_eth_balance}")
            return False

        wrseth_current_percent = int(balance_wrseth / (balance_eth + balance_wrseth) * 100)

        # если баланс wrsETH меньше kelp_min_percent от баланса ETH делаем депозит
        if kelp_min_percent > wrseth_current_percent:
            """
            Make deposit on Kelp
            """

            new_kelp_min_percent = kelp_min_percent - wrseth_current_percent if wrseth_current_percent > 5 else kelp_min_percent
            new_kelp_max_percent = kelp_max_percent - wrseth_current_percent if wrseth_current_percent > 5 else kelp_max_percent
            old_kelp_min_percent = kelp_min_percent
            old_kelp_max_percent = kelp_max_percent

            # если нам не хватает менее 5%, то считаем, что депозит не нужно делать
            if new_kelp_min_percent > 5:
                kelp_min_percent = new_kelp_min_percent
                kelp_max_percent = new_kelp_max_percent

                logger.info(
                    f"Current wrsETH balance: {wrseth_current_percent}%, need to deposit range: {kelp_min_percent}-{kelp_max_percent}% (was {old_kelp_min_percent}-{old_kelp_max_percent}%)")

                if old_kelp_min_percent != new_kelp_min_percent:
                    kelp_min_amount = (balance_wrseth + balance_eth) * new_kelp_min_percent / 100 / 10 ** 18
                    kelp_max_amount = (balance_wrseth + balance_eth) * new_kelp_max_percent / 100 / 10 ** 18
                    logger.info(f"Need to deposit {kelp_min_amount}-{kelp_max_amount} ETH to get additionally wsrETH")

                kelp = Kelp(self.account_id, self.private_key, self.recipient)
                kelp_result = await kelp.deposit(
                    kelp_min_amount,
                    kelp_max_amount,
                    decimal,
                    old_kelp_min_percent == new_kelp_min_percent,
                    kelp_min_percent,
                    kelp_max_percent,
                    module_cooldown=kelp_module_cooldown
                )

                if kelp_result is False:
                    logger.error(f"Failed to stake wrsETH, result: {kelp_result}, skip deposit to pool")
                    return True
            else:
                logger.info(
                    f"Current wrsETH balance: {wrseth_current_percent}%, need to additionally deposit {new_kelp_min_percent}%, it less than 5%, skipping deposit")
        else:
            logger.info(
                f"Current wrsETH balance: {wrseth_current_percent}%, Kelp deposit settings: {kelp_min_percent}-{kelp_max_percent}%, enough wrsETH")

        deposit_result = await ambient_finance.deposit(
            ambient_min_amount,
            ambient_max_amount,
            decimal,
            ambient_all_amount,
            ambient_min_percent,
            ambient_max_percent,
            ambient_range_width,
            min_left_eth_balance,
            max_left_eth_balance,
        )

        if deposit_result is False:
            logger.error(f"Failed to deposit to wrsETH/ETH pool, result: {deposit_result}")
        return True

    async def _sell_wrseth(self, amount: float = None):
        from_token = "WRSETH"
        to_token = "ETH"

        min_amount = amount if amount else 0.0007
        max_amount = amount if amount else 0.001
        decimal = 6
        slippage = 2

        all_amount = amount is None

        min_percent = 100
        max_percent = 100
        ambient_finance = AmbientFinance(self.account_id, self.private_key, self.recipient)

        await ambient_finance.swap(
            from_token, to_token, min_amount, max_amount, decimal, slippage, all_amount, min_percent, max_percent)

        balance_wrseth_wei = await self.get_wrseth_balance()
        balance_wrseth = balance_wrseth_wei / 10 ** 18
        balance_eth_wei = await self.w3.eth.get_balance(self.address)
        balance_eth = balance_eth_wei / 10 ** 18

        logger.info(
            f"[{self.account_id}][{self.address}] balance after sell wrsETH: {balance_wrseth} wrsETH, {balance_eth} ETH")

    async def _buy_wrseth(self, amount):
        from_token = "ETH"
        to_token = "WRSETH"

        min_amount = amount
        max_amount = amount
        decimal = 6
        slippage = 2

        all_amount = False

        min_percent = 100
        max_percent = 100
        ambient_finance = AmbientFinance(self.account_id, self.private_key, self.recipient)

        await ambient_finance.swap(
            from_token, to_token, min_amount, max_amount, decimal, slippage, all_amount, min_percent, max_percent)

        balance_wrseth_wei = await self.get_wrseth_balance()
        balance_wrseth = balance_wrseth_wei / 10 ** 18
        balance_eth_wei = await self.w3.eth.get_balance(self.address)
        balance_eth = balance_eth_wei / 10 ** 18

        logger.info(
            f"[{self.account_id}][{self.address}] balance after buy wrsETH: {balance_wrseth} wrsETH, {balance_eth} ETH")

    async def adjust_ambient_wrseth_eth_position(self,
                                                 decimal: int,
                                                 ambient_min_amount: float,
                                                 ambient_max_amount: float,
                                                 ambient_all_amount: bool,
                                                 ambient_min_percent: int,
                                                 ambient_max_percent: int,
                                                 ambient_range_width: float,
                                                 min_left_eth_balance: float,
                                                 max_left_eth_balance: float,
                                                 min_deposit_percent: int,
                                                 max_deposit_percent: int,
                                                 ambient_max_deposit_attempts: int = 1):
        logger.info(f"[{self.account_id}][{self.address}] Start adjust Ambient wrsETH/ETH position")
        ambient_finance = AmbientFinance(self.account_id, self.private_key, self.recipient)

        min_left_eth_balance_wei = int(self.w3.to_wei(min_left_eth_balance, "ether"))
        total_deposit_amount = await ambient_finance.get_total_deposit_amount()
        balance_wrseth_wei = await self.get_wrseth_balance()
        balance_wrseth = balance_wrseth_wei / 10 ** 18
        balance_eth_wei = await self.w3.eth.get_balance(self.address)
        balance_eth = balance_eth_wei / 10 ** 18

        # минимальный размер ордера продажи покупки wrseth
        min_trade_amount_wrseth_wei = 5000000000000000
        # разрешенное отклонение депозита от желаемого объёма в процентах
        deposit_percent_allowed_error = 8

        logger.info(
            f"[{self.account_id}][{self.address}] account have {balance_wrseth} wrsETH, {balance_eth} ETH and {total_deposit_amount} total deposit amount")

        # if balance_eth_wei < self.w3.to_wei(min_eth_balance, "ether"):
        #     logger.info(
        #         f"[{self.account_id}][{self.address}] Cannot run script due to low EHT balance: {balance_eth / 10 ** 18} < {min_eth_balance}")
        #     return False

        total_wrseth_eth_balance_wei = balance_wrseth_wei + balance_eth_wei
        total_deposit_and_balance_wei = self.w3.to_wei(total_deposit_amount, "ether") + total_wrseth_eth_balance_wei
        # мы считаем процент от общего объёма все активов - min_left_eth_balance
        deposit_current_percent = int(self.w3.to_wei(total_deposit_amount, "ether") / (
                total_deposit_and_balance_wei - min_left_eth_balance_wei) * 100)

        # TODO: ДОБАВИТЬБ СЮДА УЧЁТ баланс wrsETH
        if deposit_current_percent > min_deposit_percent - deposit_percent_allowed_error:
            logger.info(
                f"[{self.account_id}][{self.address}] current deposit is {deposit_current_percent}% of total ETH and wrsETH balances, that is enough")

            out_range_positions = await ambient_finance.get_outrange_positions(ambient_finance.eth_address,
                                                                               SCROLL_TOKENS["WRSETH"])
            if len(out_range_positions) == 0:
                logger.info(f"[{self.account_id}][{self.address}] there are no out range positions")

                # Если текущий баланс wrsETH достаточно не маленький, то продаём его
                if balance_wrseth_wei > min_trade_amount_wrseth_wei:  # 0.005 ETH
                    logger.info(f"[{self.account_id}][{self.address}] try to sell redundant {balance_wrseth} wrsETH")
                    await self._sell_wrseth()
                    return True
                logger.info(
                    f"[{self.account_id}][{self.address}] redundant {balance_wrseth} wrsETH is too small to sell, skipping")

                return False
            else:
                logger.info(
                    f"[{self.account_id}][{self.address}] there are {len(out_range_positions)} out range positions, need to withdrawal and make new deposit")

        logger.info(
            f"[{self.account_id}][{self.address}] current deposit is {deposit_current_percent}% of total ETH balance, should be minimum {min_deposit_percent - deposit_percent_allowed_error}%")

        new_deposit = total_deposit_amount * (
                min_deposit_percent / deposit_current_percent) if deposit_current_percent > 0 else total_deposit_amount * min_deposit_percent
        # считаем сколько нужно добавить в позицию, чтобы депозит был нужного объёма
        need_deposit = new_deposit - total_deposit_amount - balance_wrseth
        need_deposit_wei = int(self.w3.to_wei(need_deposit, "ether")) if need_deposit > 0 else 0

        if need_deposit_wei > 0:
            logger.info(
                f"[{self.account_id}][{self.address}] will spend {need_deposit} ETH to increase current deposit")
        else:
            logger.info(f"[{self.account_id}][{self.address}] no need to spend ETH balance to increase current deposit")

        # вычитаем min_left_eth_balance_wei из общего баланса для которого считаем процент необходимого депозита
        total_wrseth_eth_amount_wei = balance_wrseth_wei + balance_eth_wei - min_left_eth_balance_wei
        if total_wrseth_eth_amount_wei <= 0:
            total_wrseth_eth_amount = total_wrseth_eth_amount_wei / 10 ** 18
            logger.error(
                f"[{self.account_id}][{self.address}] something wrong with calculations, {total_wrseth_eth_amount} total wrseth and eth amount < {min_left_eth_balance} min left eth balance")
            return False

        should_be_wrseth_wei = int(
            0.5 * (total_wrseth_eth_amount_wei * random.randint(max_deposit_percent, max_deposit_percent) / 100))
        need_to_sell_wrseth_wei = balance_wrseth_wei - should_be_wrseth_wei if balance_wrseth_wei > should_be_wrseth_wei else 0

        # так как мы продадим лишний wrsETH, то оставш
        # считаем новый баланс после депозита, он не должен быть слишком маленьким
        balance_eth_after_deposit_wei = balance_eth_wei - need_deposit_wei + need_to_sell_wrseth_wei
        balance_eth_after_deposit = balance_eth_after_deposit_wei / 10 ** 18
        logger.info(f"[{self.account_id}][{self.address}] balance after deposit: {balance_eth_after_deposit} ETH")

        # если после депозита осталоось баланса меньше чем минимум необходимо
        if balance_eth_after_deposit_wei < min_left_eth_balance_wei:
            need_deposit_wei = need_deposit_wei - min_left_eth_balance_wei
            need_deposit = need_deposit_wei / 10 ** 18
            logger.info(
                f"[{self.account_id}][{self.address}] cannot deposit {new_deposit} ETH because after deposit ETH balance would be less than {min_left_eth_balance}, new deposit amount {need_deposit} ETH")

            # Если текущий депозит совсем немного меньше чем нужно, то депозит не делаем
            if need_deposit_wei < 500000000000000:  # 0.0005 ETH
                logger.info(f"[{self.account_id}][{self.address}] new deposit amount {need_deposit} ETH is too small")

                # Если текущий баланс wrsETH достаточно не маленький, то продаём его
                if balance_wrseth > min_trade_amount_wrseth_wei:  # 0.005 ETH
                    logger.info(f"[{self.account_id}][{self.address}] try to sell redundant {balance_wrseth} wrsETH")
                    await self._sell_wrseth()
                    await sleep(30, 60)

                return True

        i = 0
        while True:
            if i == 0:
                logger.info(f"[{self.account_id}][{self.address}] Start to withdraw all positions")
            await ambient_finance.withdrawal()
            i += 1

            total_deposit_amount = await ambient_finance.get_total_deposit_amount()
            if total_deposit_amount == 0:
                logger.info(f"[{self.account_id}][{self.address}] Withdrew all positions successfully")
                break

            # делаем попытку вывести максимум 3 раза
            if i > 3:
                logger.error(f"[{self.account_id}][{self.address}] Failed to withdraw all positions, leave")
                raise Exception("Failed to withdraw all positions")
            else:
                logger.error(f"[{self.account_id}][{self.address}] Failed to withdraw all positions, try again")
            await sleep(40, 80)

        # получаем все балансы после операций изменивших его
        balance_wrseth_wei = await self.get_wrseth_balance()
        balance_wrseth = balance_wrseth_wei / 10 ** 18
        balance_eth_wei = await self.w3.eth.get_balance(self.address)
        balance_eth = balance_eth_wei / 10 ** 18

        logger.info(
            f"[{self.account_id}][{self.address}] balance after withdrawal: {balance_wrseth} wrsETH, {balance_eth} ETH")

        # вычитаем min_left_eth_balance_wei из общего баланса для которого считаем процент необходимого депозита
        total_wrseth_eth_amount_wei = balance_wrseth_wei + balance_eth_wei - min_left_eth_balance_wei
        if total_wrseth_eth_amount_wei <= 0:
            total_wrseth_eth_amount = total_wrseth_eth_amount_wei / 10 ** 18
            logger.error(
                f"[{self.account_id}][{self.address}] something wrong with calculations, {total_wrseth_eth_amount} total wrseth and eth amount < {min_left_eth_balance} min left eth balance")
            return False
        should_be_wrseth_wei = int(
            0.5 * (total_wrseth_eth_amount_wei * random.randint(max_deposit_percent, max_deposit_percent) / 100))

        # TODO: проверяем что после покупки останется минимальный баланс
        need_to_buy_wrseth_wei = should_be_wrseth_wei - balance_wrseth_wei
        need_to_buy_wrseth = need_to_buy_wrseth_wei / 10 ** 18

        if need_to_buy_wrseth_wei > 500000000000000:  # 0.0005 ETH
            logger.info(
                f"[{self.account_id}][{self.address}] need to buy {need_to_buy_wrseth} wrsETH to make deposit")
            await self._buy_wrseth(need_to_buy_wrseth)
            await sleep(30, 60)
        else:
            logger.info(f"[{self.account_id}][{self.address}] no need to buy wrsETH to make deposit")

        need_to_sell_wrseth_wei = balance_wrseth_wei - should_be_wrseth_wei
        need_to_sell_wrseth = need_to_sell_wrseth_wei / 10 ** 18

        if need_to_sell_wrseth_wei > 500000000000000:  # 0.0005 ETH
            logger.info(
                f"[{self.account_id}][{self.address}] need to sell {need_to_sell_wrseth} wrsETH to make deposit")

            await self._sell_wrseth(need_to_sell_wrseth)
            await sleep(30, 60)
        else:
            logger.info(f"[{self.account_id}][{self.address}] no need to sell wrsETH to make deposit")

        logger.info(f"Start new deposit to wrsETH/ETH pool")

        deposit_result = await ambient_finance.deposit(
            ambient_min_amount,
            ambient_max_amount,
            decimal,
            ambient_all_amount,
            ambient_min_percent,
            ambient_max_percent,
            ambient_range_width,
            min_left_eth_balance,
            max_left_eth_balance,
            ambient_max_deposit_attempts
        )

        if deposit_result is False:
            logger.error(f"Failed to deposit to wrsETH/ETH pool, result: {deposit_result}")
            return False

        await sleep(30, 60)

        balance_wrseth_wei = await self.get_wrseth_balance()
        balance_wrseth = balance_wrseth_wei / 10 ** 18
        balance_eth_wei = await self.w3.eth.get_balance(self.address)
        balance_eth = balance_eth_wei / 10 ** 18

        logger.info(
            f"[{self.account_id}][{self.address}] balance after deposit: {balance_wrseth} wrsETH, {balance_eth} ETH")

        if balance_wrseth_wei > min_trade_amount_wrseth_wei:  # 0.005 ETH
            logger.info(f"[{self.account_id}][{self.address}] try to sell redundant {balance_wrseth} wrsETH")
            await self._sell_wrseth()

        try:
            total_deposit_amount = await ambient_finance.get_total_deposit_amount()
            balance_wrseth_wei = await self.get_wrseth_balance()
            balance_eth_wei = await self.w3.eth.get_balance(self.address)
            total_wrseth_eth_balance_wei = balance_wrseth_wei + balance_eth_wei
            total_deposit_and_balance_wei = self.w3.to_wei(total_deposit_amount, "ether") + total_wrseth_eth_balance_wei
            # мы считаем процент от общего объёма все активов - min_left_eth_balance
            deposit_current_percent = int(self.w3.to_wei(total_deposit_amount, "ether") / (
                    total_deposit_and_balance_wei - min_left_eth_balance_wei) * 100)

            logger.info(
                f"[{self.account_id}][{self.address}] current deposit is {deposit_current_percent}% of total ETH balance, should be minimum {min_deposit_percent - deposit_percent_allowed_error}%")
        except Exception as ex:
            logger.error(f"Failed to get deposit proportion after deposit: {ex}")

    async def _sell_all_wrsETH(self):
        from_token = "WRSETH"
        to_token = "ETH"

        min_amount = 0.001
        max_amount = 0.002
        decimal = 6
        slippage = 2

        all_amount = True

        min_percent = 100
        max_percent = 100

        return await self.ambient_finance.swap(
            from_token, to_token, min_amount, max_amount, decimal, slippage, all_amount, min_percent, max_percent
        )

    async def _withdraw_to_okex(self, min_eth_balance_after_script, max_eth_balance_after_script,
                                adjust_ambient_wrseth_eth_position_scenario):
        withdraw_cooldown = 60 * 25
        last_iter_withdraw = await self.scroll.check_last_withdraw_iteration(
            withdraw_cooldown
        )
        if not last_iter_withdraw:
            # вывод был слишком недавно, нужно время, чтобы информация в апи обновилась
            logger.info(f"{self.log_prefix} withdraw from Scroll was pretty recently, have to wait before continue")
            return False

        claim_withdraw_cooldown = 60 * 2
        last_iter_claim_withdraw = await self.scroll_ethereum.check_last_claim_withdraw_iteration(
            claim_withdraw_cooldown
        )
        if not last_iter_claim_withdraw:
            # депозит был слишком недавно, нужно время, чтобы информация в апи обновилась
            logger.info(
                f"{self.log_prefix} Claim Withdrawal from Scroll was pretty recently, have to wait before continue")
            return False

        bridge_tx_pending = await self._get_pending_bridge_tx()
        if bridge_tx_pending:
            # мы не можем действовать пока есть пендинг транзакции
            if bridge_tx_pending["message_type"] == 2:  # вывод
                logger.info(f"{self.log_prefix} there is PENDING withdrawal TX: {bridge_tx_pending}")
                claim_result = await self.scroll_ethereum.withdraw_claim(bridge_tx_pending)
                return claim_result is not False
            else:  # депозит
                # мы не можем действовать пока есть пендинг транзакции, поэтому лучше переключиться на другие аккаунты
                logger.info(
                    f"{self.log_prefix} there is PENDING bridge TX, wait it for complete before take any actions: {bridge_tx_pending}")
            return False

        # на балансе более чем нужно, то делаем вывод на биржу через майннет
        min_bridge_amount_eth = 0.01
        eth_price_in_usd = await get_eth_usd_price("scroll")
        current_deposit = await self.ambient_finance.get_total_deposit_amount()
        est_current_deposit_in_usd = current_deposit * eth_price_in_usd

        balance_eth_wei = await self.w3.eth.get_balance(self.address)
        balance_eth = balance_eth_wei / 10 ** 18
        balance_wrseth_wei = await self.get_wrseth_balance()
        balance_wrseth = balance_wrseth_wei / 10 ** 18

        logger.info(
            f"{self.log_prefix} current Ambient deposit {current_deposit} ETH/wrsETH, ~{est_current_deposit_in_usd} USD")
        logger.info(f"{self.log_prefix} current Scroll balance: {balance_eth} ETH and {balance_wrseth} wrsETH")

        if balance_wrseth + balance_eth + current_deposit > 1.5 * (
                max_eth_balance_after_script + min_bridge_amount_eth):
            logger.info(f"{self.log_prefix} Scroll account balance is too big, have to withdraw to Ethereum")

            if current_deposit > 0:
                logger.info(f"{self.log_prefix} Try to withdraw all position before withdraw to Ethereum")
                await self.ambient_finance.withdrawal()
                return True

            if balance_wrseth_wei > 500000000000000:  # 0.0005 ETH
                # надо продать весь wsrETH, чтобы вывести средства в ETH обратно на биржу
                logger.info(f"{self.log_prefix} Try to sell all wrsETH before withdraw to Ethereum")
                await self._sell_all_wrsETH()
                return True

            min_amount = balance_eth - max_eth_balance_after_script
            max_amount = balance_eth - min_eth_balance_after_script
            decimal = 4
            all_amount = False
            min_percent = 10
            max_percent = 10

            logger.info(
                f"{self.log_prefix} Try to withdraw {round(min_amount, decimal)}-{round(max_amount)} ETH to Ethereum from Scroll")

            await self.scroll.withdraw(min_amount, max_amount, decimal, all_amount, min_percent, max_percent)
            return True

        logger.info(f"{self.log_prefix} Scroll account balance is good, no need to withdraw to Ethereum")

        if current_deposit == 0:
            logger.info(
                f"{self.log_prefix} There are no active Ambient position after withdrawal from Scroll to Ethereum, try to make some")

            await adjust_ambient_wrseth_eth_position_scenario(self.account_id, self.private_key, self.recipient)
            return True

        # теперь мы должно проверить, что в майннете есть баланс для обратного вывода на биржу
        balance_eth_wei_ethereum = await self.scroll_ethereum.w3.eth.get_balance(self.address)
        balance_eth_ethereum = balance_eth_wei_ethereum / 10 ** 18
        balance_eth_ethereum_in_usd = eth_price_in_usd * balance_eth_ethereum
        logger.info(
            f"{self.log_prefix} current Ethereum balance: {balance_eth_ethereum} ETH, ~{balance_eth_ethereum_in_usd} USD")

        # если баланс меньше  0.001 ETH, то не имеет даже смысла делать запрос к окексу
        if balance_eth_wei_ethereum > 1000000000000000:  # 0.001 ETH
            # получаем минимальный депозит
            deposit_info = self.okex.get_deposit_info("ETH", "ethereum")
            min_deposit = deposit_info.min_amount
            logger.debug(f"Min deposit for ethereum.ETH: {min_deposit}")

            if balance_eth_ethereum > 2 * min_deposit:
                deposit_addresses = DEPOSITS_ADDRESSES.get(self.address, None)
                logger.info(f"{self.log_prefix} deposit address: {deposit_addresses}")
                if not deposit_addresses:
                    raise Exception(f"{self.log_prefix} Unknown deposit address")

                logger.debug(f"Deposit {balance_eth_wei_ethereum / 10 ** 18} ETH")

                tx = await self.get_tx_data(balance_eth_wei_ethereum, False)
                tx.update({
                    "to": self.w3.to_checksum_address(deposit_addresses),
                    "chainId": await self.scroll_ethereum.w3.eth.chain_id,
                    "from": self.address,
                    "nonce": await self.scroll_ethereum.w3.eth.get_transaction_count(self.address)
                })

                signed_txn = await self.scroll_ethereum.sign(tx, gas=21000, sub_fee_from_value=True)
                txn_hash = await self.scroll_ethereum.send_raw_transaction(signed_txn)
                await self.scroll_ethereum.wait_until_tx_finished(txn_hash.hex())

                return True

        logger.info(f"No enough balance to deposit to Okex")

        return None

    async def _make_1000_usd_deposit_ambient(self):
        min_left_eth_balance = 0.003
        max_left_eth_balance = 0.0035

        decimal = 5

        ambient_min_amount = 0.0001
        ambient_max_amount = 0.0002
        # all_amount - deposit from min_percent to max_percent of wrsETH
        ambient_all_amount = True
        ambient_min_percent = 100
        ambient_max_percent = 100
        # Percentage width of the range around current pool price (1 = 1%, 0.5 = 0.5%)
        # Tighter ranges accumulate rewards at faster rates, but are more likely to suffer divergence losses.
        ambient_range_width = 1

        # сколько процентов депозит должен составлять от баланса ETH - min_left_eth_balance
        min_deposit_percent = 100
        max_deposit_percent = 100

        # сколько раз повторяем депозит с уменьшением кол-ва баланса
        ambient_max_deposit_attempts = 100
        await self.adjust_ambient_wrseth_eth_position(
            decimal,
            ambient_min_amount,
            ambient_max_amount,
            ambient_all_amount,
            ambient_min_percent,
            ambient_max_percent,
            ambient_range_width,
            min_left_eth_balance,
            max_left_eth_balance,
            min_deposit_percent,
            max_deposit_percent,
            ambient_max_deposit_attempts
        )

    async def _deposit_economy_to_scroll(self, eth_left_balance_min_after_deposit):
        min_amount = 0.01
        max_amount = 0.02
        decimal = 4

        all_amount = True

        min_percent = 100
        max_percent = 100

        sub_fee_from_value = True

        await self.scroll_ethereum.deposit_economy(min_amount, max_amount, decimal, all_amount, min_percent,
                                                   max_percent, sub_fee_from_value, eth_left_balance_min_after_deposit)

    async def _get_pending_bridge_tx(self):
        proxy = self.scroll.get_random_proxy()
        tx_list = await self.scroll.get_bridge_tx_list(3, proxy)

        for tx in tx_list:
            # статус если tx reverted
            if tx["tx_status"] == 1:
                continue
            # tx["message_type"] == 3 это экономный депозит
            if tx["tx_status"] != 8 and tx["message_type"] == 3:
                return tx
            # tx["message_type"] == 2 это вывод
            elif tx["tx_status"] != 2 and tx["message_type"] == 2:
                return tx
            # tx["message_type"] == 3 это депозит
            elif tx["tx_status"] != 2 and tx["message_type"] == 1:
                return tx
            # какой то другой тип
            if tx["tx_status"] != 8 and tx["message_type"] not in [1, 2, 3]:
                return tx
        return None

    def _get_okex_eth_price(self):
        return float(self.okex.get_price("ETH"))

    @CacheDecorator(ttl=1000 * 10)
    def _get_okex_total_balance(self, symbol) -> float:
        funding_balance = self.okex.get_funding_balance(symbol)
        trading_balance = self.okex.get_trading_balance(symbol)
        total_balance = funding_balance + trading_balance

        logger.debug(
            f"{symbol} funding balance: {funding_balance}; trading balance: {trading_balance}; total: {total_balance}")

        return float(total_balance)

    async def _buy_and_withdraw_eth(self, amount: float, wait_withdrawal=False):
        return self.okex.buy_token_and_withdraw(
            "ETH",
            "Ethereum",
            self.address,
            amount,
            include_fee=False,
            wait_withdrawal=wait_withdrawal
        )

    @retry
    @timeout(60 * 5, RuntimeError, "Iteration timeout reached (5 minutes), skipping the iteration and try again")
    async def _mint_ambient_providoor_badge_iteration(
            self,
            min_deposit_amount_usd: int,
            max_deposit_amount_usd: int,
            min_eth_balance_after_script,
            max_eth_balance_after_script,
            ethereum_eth_left_balance_min_after_deposit,
            adjust_ambient_wrseth_eth_position_scenario
    ):
        logger.info(f"{self.log_prefix} Start check conditions to mint Ambient Providoor badge")

        is_minted_badge = await self.scroll.is_ambient_providoor_badge_minted()

        # TODO: проверяем что нет pending transaction у аккаунта
        if is_minted_badge:
            # если у нас уже есть значок, то нам нужно вывести деньги назад на окекс
            logger.info(f"{self.log_prefix} Ambient Providoor Badge minted")

            # так же мы можем попробовать сминтить значок за обмен на $500
            is_swapoor_minted_badge = await self.scroll.is_ambient_swapooor_badge_minted()
            if not is_swapoor_minted_badge:
                logger.info(f"{self.log_prefix} Ambient Swapooor Badge is not minted")

                is_swapoor_badge_eligible = await self.scroll.is_ambient_swapoor_badge_eligible()
                if is_swapoor_badge_eligible:
                    logger.info(f"{self.log_prefix} Try to mint Ambient Swapooor Badge")
                    await self.scroll.mint_ambient_swapooor_badge()
                    return True
                logger.error(f"{self.log_prefix} Ambient Swapooor Badge is not eligible to mint!")

                return False
            else:
                logger.info(f"{self.log_prefix} Ambient Swapooor Badge is minted")

            # выводим на окекс
            result = await self._withdraw_to_okex(min_eth_balance_after_script, max_eth_balance_after_script,
                                                  adjust_ambient_wrseth_eth_position_scenario)
            return result

        logger.info(f"{self.log_prefix} Ambient Providoor Badge is not minted")

        # если у нас нет значка, то нужно его сминтить
        is_badge_eligible = await self.scroll.is_ambient_providoor_badge_eligible()
        if is_badge_eligible:
            # если у нас нет значка, но мы можем его сминтить, то запускаем минт
            logger.info(f"{self.log_prefix} Badge is eligible to mint")

            is_minted = await self.scroll.is_profile_minted()
            if not is_minted:
                logger.info(f"{self.log_prefix} Account have to minted canvas before mint badges")

                await self.scroll.mint_canvas()
                return True

            await self.scroll.mint_ambient_providoor_badge()
            return True

        logger.info(f"{self.log_prefix} Badge is not eligible to mint")

        # eth_price_in_usd = await get_eth_usd_price("scroll")
        eth_price_in_usd = self._get_okex_eth_price()

        logger.debug(f"{self.log_prefix} ETH price is {eth_price_in_usd} USD")

        current_deposit = await self.ambient_finance.get_total_deposit_amount()
        est_current_deposit_in_usd = current_deposit * eth_price_in_usd

        logger.info(
            f"{self.log_prefix} current deposit {current_deposit} ETH/wrsETH, ~{est_current_deposit_in_usd} USD")

        if est_current_deposit_in_usd > USD_1000 or est_current_deposit_in_usd > 0.9 * min_deposit_amount_usd:
            # если текущий депозит уже больше необходимого, но значок ещё не доступен, то нужно просто ждать
            logger.info(
                f"{self.log_prefix} current deposit is enough, but the badge is still not eligible to mint, need to wait some time")
            return False

        balance_eth_wei = await self.w3.eth.get_balance(self.address)
        balance_eth = balance_eth_wei / 10 ** 18
        balance_wrseth_wei = await self.get_wrseth_balance()
        balance_wrseth = balance_wrseth_wei / 10 ** 18

        logger.info(f"{self.log_prefix} current Scroll balance: {balance_eth} ETH and {balance_wrseth} wrsETH")

        total_scroll_assets = eth_price_in_usd * (balance_eth + balance_wrseth) + est_current_deposit_in_usd

        logger.info(
            f"{self.log_prefix} total cost of Scroll balance and current Ambient deposit is {total_scroll_assets} USD, min deposit amount is {min_deposit_amount_usd} USD")

        if total_scroll_assets > min_deposit_amount_usd or total_scroll_assets > USD_1000 * 1.05:
            logger.info(
                f"{self.log_prefix} current Scroll balance is enough to make deposit")
            # если на аккаунте достаточно средств, чтобы сделать новый депозит, то делаем его
            await self._make_1000_usd_deposit_ambient()
            return True

        # если на аккаунте недостаточно средств, то проверяем не делали ли недавно вывод (чтобы дать обновиться информации в апи)
        deposit_economy_cooldown = 60 * 20
        last_iter_deposit_economy = await self.scroll_ethereum.check_last_deposit_economy_iteration(
            deposit_economy_cooldown
        )
        if not last_iter_deposit_economy:
            # депозит был слишком недавно, нужно время, чтобы информация в апи обновилась
            logger.info(
                f"{self.log_prefix} Economy Deposit to Scroll was pretty recently, have to wait before continue")
            return False

        bridge_tx_pending = await self._get_pending_bridge_tx()
        if bridge_tx_pending:
            # мы не можем действовать пока есть пендинг бридж транзакции
            logger.info(
                f"{self.log_prefix} there PENDING bridge TX, wait it for complete before take any actions: {bridge_tx_pending}")
            return False

        logger.info(f"{self.log_prefix} there no PENDING bridge TXs, continue")

        # теперь мы должно проверить, что в майннете нет нужного баланса, чтобы сделать депозит
        balance_eth_wei_ethereum = await self.scroll_ethereum.w3.eth.get_balance(self.address)
        balance_eth_ethereum = balance_eth_wei_ethereum / 10 ** 18
        balance_eth_ethereum_in_usd = eth_price_in_usd * balance_eth_ethereum

        logger.info(
            f"{self.log_prefix} current Ethereum balance: {balance_eth_ethereum} ETH (~{balance_eth_ethereum_in_usd} USD)")

        if balance_eth_ethereum_in_usd > min_deposit_amount_usd or balance_eth_ethereum_in_usd > USD_1000 * 1.1:
            # если на аккаунте в майннете достаточно средств, чтобы сделать новый депозит, то делаем бридж
            logger.info(
                f"{self.log_prefix} current Ethereum balance is enough to make deposit, try to make bridge to Scroll")
            await self._deposit_economy_to_scroll(ethereum_eth_left_balance_min_after_deposit)
            return True

        # если на аккаунте в майннете недостаточно средств, чтобы сделать новый депозит, то делаем вывод с биржи
        # но для начала проверяем что нет сейчас пендинг выводов
        pending_withdrawals = self.okex.get_pending_withdrawals(self.address)

        if len(pending_withdrawals) > 0:
            logger.info(f"There are pending withdrawals, have to wait them before continue: {pending_withdrawals}")
            return False

        logger.info(f"There are no pending withdrawals")

        # делаем вывод ETH
        okex_balance_usdt = self._get_okex_total_balance("USDT")
        okex_balance_eth = self._get_okex_total_balance("ETH")
        okex_balance_usdt_in_eth = okex_balance_usdt * (1 / eth_price_in_usd)
        can_withdraw_eth_estimated = okex_balance_usdt_in_eth + okex_balance_eth
        can_withdraw_usd_estimated = can_withdraw_eth_estimated * eth_price_in_usd

        logger.info(
            f"Can withdraw from Okex approximately {can_withdraw_eth_estimated} ETH (~{can_withdraw_usd_estimated} USD)")

        if balance_eth_ethereum_in_usd > 20:
            # оставляем дополнительно 10 долларов оплату комсы, деньги на claim и т.д.
            min_deposit_amount_usd = min_deposit_amount_usd - int(balance_eth_ethereum_in_usd) + 10
            max_deposit_amount_usd = max_deposit_amount_usd - int(balance_eth_ethereum_in_usd) + 10

        if max_deposit_amount_usd > can_withdraw_usd_estimated > min_deposit_amount_usd:
            max_deposit_amount_usd = int(can_withdraw_usd_estimated)

        deposit_amount_usd = random.randint(min_deposit_amount_usd, max_deposit_amount_usd)
        amount_to_withdraw = deposit_amount_usd * (1 / eth_price_in_usd)
        logger.info(
            f"Try to buy and withdraw {amount_to_withdraw} ETH (~{deposit_amount_usd} USD, range: {min_deposit_amount_usd}-{max_deposit_amount_usd} USD)")

        if can_withdraw_eth_estimated < amount_to_withdraw:
            logger.error(f"""
                !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                !!                                                                                                                          !!
                     NOT ENOUGH MONEY ON OKEX TO CONTINUE, need: {amount_to_withdraw} ETH, but can only ~{can_withdraw_eth_estimated} ETH
                !!                                                                                                                          !!
                !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            """)
            return False

        await self._buy_and_withdraw_eth(amount_to_withdraw)

        logger.info(f"Done this iteration, return")

        return True

    def append_address_to_file(self, file_name: str, address=None):
        if not address:
            address = self.address
        logger.debug(f"Try to add {address} to {file_name}")

        with open(file_name, 'r+') as file:
            wallets = [row.strip().lower() for row in file if row.strip() != ""]
            if address.lower() not in wallets:
                file.write(f"{address}\n")
            else:
                logger.debug(f"Account {address} already in file {file_name}")

    def remove_address_from_file(self, file_name: str, address=None):
        if not address:
            address = self.address
        logger.info(f"Try to remove {self.address} from {file_name}")

        with open(file_name, "r") as file_input:
            with open(file_name, "w") as output:
                for line in file_input:
                    if line.strip("\n").lower() != address.lower():
                        output.write(line.lower())
                    else:
                        logger.info(f" Account {address} removed from {file_name}")

    def handle_next_account(self, max_current_accounts):
        self.current_accounts = get_current_accounts()

        # текущие аккаунты закончили выполнение скрипта, нужно получить новые
        if len(self.current_accounts) == 0:
            acc = get_random_account()
            if acc:
                # добавляем случайный аккаунт
                self.append_address_to_file(AMBIENT_BADGE_CURRENT_ACCOUNTS_FILE, get_acc_address(acc))
                self.current_accounts.append(acc)
                self.current_account_index = 0
                logger.info(
                    f"(1) Add new address {get_acc_address(acc)} to current accounts, now there are {len(self.current_accounts) + 1} accounts")
                return True
            else:
                logger.debug(f"(2) No more accounts to process")
                # аккаунты закончились
                self.current_account_index = None

                return False

        # последний аккаунт успешно выполнил сценарий и мы начинаем заново прогонять аккаунты
        if self.current_account_index > len(self.current_accounts) - 1:
            self.current_account_index = 0
            logger.info(f"(3) Start handle accounts from the start")

            return True

        # если аккаунт послдений, то пытаемся добавить ещё аккаунт если можем
        if self.current_account_index == len(self.current_accounts) - 1:
            # если аккаунтов уже слишком много, то снова возвращаемся к первому
            if len(self.current_accounts) >= max_current_accounts:
                self.current_account_index = 0
                logger.info(
                    f"(4) Cannot add new accounts to current accounts because reach the limit, return to the first")
                return True

            # если лимит аккаунтов ещё не превышен, то добавляем новый аккаунт
            acc = get_random_account()
            if acc:
                self.append_address_to_file(AMBIENT_BADGE_CURRENT_ACCOUNTS_FILE, get_acc_address(acc))
                self.current_accounts.append(acc)
                self.current_account_index += 1
                logger.info(
                    f"(5) Add new address {get_acc_address(acc)} to current accounts, now there are {len(self.current_accounts) + 1} accounts")

                return True
            else:
                # если лимит аккаунтов ещё не превышен, но новых аккаунтов нет, то начинаем заново
                self.current_account_index = 0
                logger.info(
                    f"(6) Cannot add new accounts to current accounts because now new accounts found, return to the first")

                return True

        # просто запускаем следующий аккаунт
        self.current_account_index += 1
        logger.info(
            f"(7) Move from {self.current_account_index - 1} to {self.current_account_index} account (total: {len(self.current_accounts)})")

        return True

    def _finish_current_account(self):
        self.remove_address_from_file(AMBIENT_BADGE_CURRENT_ACCOUNTS_FILE)
        self.append_address_to_file(AMBIENT_BADGE_SCENARIO_FINISHED_ACCOUNTS_FILE)

    async def mint_ambient_providoor_badge(
            self,
            min_deposit_amount_usd,
            max_deposit_amount_usd,
            min_eth_balance_after_script,
            max_eth_balance_after_script,
            ethereum_eth_left_balance_min_after_deposit,
            max_current_accounts,
            min_wait_time_before_accounts,
            max_wait_time_before_accounts,
            min_wait_time_before_iterations,
            max_wait_time_before_iterations,
            adjust_ambient_wrseth_eth_position_scenario
    ):
        self.okex = Okex(OKEX_API_KEY, OKEX_SECRET_KEY, OKEX_PASSPHRASE, OKEX_PROXY)
        self.current_accounts = get_current_accounts()

        # текущие аккаунты закончили выполнение скрипта, нужно получить новые
        if len(self.current_accounts) == 0:
            with open(AMBIENT_BADGE_SCENARIO_FINISHED_ACCOUNTS_FILE, 'r') as file:
                wallets_already_finished_scenario = [row.strip().lower() for row in file if row.strip() != ""]
                logger.info(
                    f"There are {len(wallets_already_finished_scenario)} accounts what already finished ambient badge scenario (file: {AMBIENT_BADGE_SCENARIO_FINISHED_ACCOUNTS_FILE})")
            if self.address.lower() in wallets_already_finished_scenario:
                logger.info(f"{self.log_prefix} Account already finished the scenario, move to next")
                return False

            # добавляем случайный аккаунт
            self.append_address_to_file(AMBIENT_BADGE_CURRENT_ACCOUNTS_FILE)
            self.current_accounts.append(
                {
                    "id": self.account_id,
                    "key": self.private_key
                }
            )

        logger.info(f"Start process {get_acc_address(self.current_accounts[0])} account")

        self.current_account_index = 0
        iterations_map = {}

        while True:
            current_account = self.current_accounts[self.current_account_index]
            self.load_account(current_account["id"], current_account["key"])

            # для каждого аккаунта будет сохранять его итерации
            if self.account_id not in iterations_map:
                iterations_map[self.account_id] = 1
            i = iterations_map[self.account_id]

            logger.info(f"Start {i} iteration")
            iteration_result = await self._mint_ambient_providoor_badge_iteration(
                min_deposit_amount_usd,
                max_deposit_amount_usd,
                min_eth_balance_after_script,
                max_eth_balance_after_script,
                ethereum_eth_left_balance_min_after_deposit,
                adjust_ambient_wrseth_eth_position_scenario
            )

            if iteration_result is None:
                logger.info(f"Finished script for {self.address} for {i} iterations, try to choose new accounts")
                self._finish_current_account()

                find_next_account = self.handle_next_account(max_current_accounts)
                if not find_next_account:
                    logger.info(f"Finished script for all accounts, leave...")
                    break
                await sleep(min_wait_time_before_accounts, max_wait_time_before_accounts)
            elif iteration_result is False:
                logger.info(
                    f"Finished {i} iteration, account have no action to do right now, try to process other accounts")
                find_next_account = self.handle_next_account(max_current_accounts)
                if not find_next_account:
                    logger.info(f"There are no other accounts to process, wait and continue the current")
                    await sleep(2 * min_wait_time_before_iterations, 2 * max_wait_time_before_iterations)
                else:
                    await sleep(min_wait_time_before_accounts, max_wait_time_before_accounts)
            else:
                logger.info(f"Finished {i} iteration, wait and try to process this account again")
                await sleep(min_wait_time_before_iterations, max_wait_time_before_iterations)
            i += 1
