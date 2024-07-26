import random

from loguru import logger

from config import SCROLL_TOKENS, OKEX_API_KEY, OKEX_SECRET_KEY, OKEX_PASSPHRASE, OKEX_PROXY
from utils.helpers import get_eth_usd_price
from utils.sleeping import sleep
from . import AmbientFinance, Kelp, Scroll
from .account import Account
from .okex import Okex

wrsETH = "WRSETH"


class Scenarios(Account):
    def __init__(self, account_id: int, private_key: str, recipient: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="scroll", recipient=recipient)
        self.ambient_finance = AmbientFinance(account_id, private_key, recipient)
        self.scroll = Scroll(account_id, private_key, "scroll", recipient)
        self.scroll_ethereum = Scroll(account_id, private_key, "ethereum", recipient)
        self.okex = None

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
                if balance_wrseth > min_trade_amount_wrseth_wei:  # 0.005 ETH
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

        if balance_wrseth > min_trade_amount_wrseth_wei:  # 0.005 ETH  # 0.0005 ETH
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

    async def _withdraw_to_okex(self):
        # на балансе более $1000, то делаем вывод на биржу через майннет
        # проверяем что нет активного вывода
        # проверяем что есть активная позиция и она больше 500 долларов
        # проверяем что текущий баланс больше 500 долларов
        # выводим с ambient finance позицию у которой больше 500 долларов (?)
        # выводим со скролла в майннет
        # выводим с майннета на окекс

        # если все действия выполнены и ничего делать не надо, то возращаем Noner

        return None

    async def _make_1000_usd_deposit_ambient(self):
        min_left_eth_balance = 0.0045
        max_left_eth_balance = 0.0055

        decimal = 5

        ambient_min_amount = 0.0001
        ambient_max_amount = 0.0002
        # all_amount - deposit from min_percent to max_percent of wrsETH
        ambient_all_amount = True
        ambient_min_percent = 100
        ambient_max_percent = 100
        # Percentage width of the range around current pool price (1 = 1%, 0.5 = 0.5%)
        # Tighter ranges accumulate rewards at faster rates, but are more likely to suffer divergence losses.
        ambient_range_width = 0.5

        # сколько процентов депозит должен составлять от баланса ETH - min_left_eth_balance
        min_deposit_percent = 98
        max_deposit_percent = 99

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

    async def _deposit_economy_to_scroll(self):
        min_amount = 0.01
        max_amount = 0.02
        decimal = 4

        all_amount = True

        min_percent = 100
        max_percent = 100

        sub_fee_from_value = True

        await self.scroll_ethereum.deposit_economy(min_amount, max_amount, decimal, all_amount, min_percent,
                                                   max_percent, sub_fee_from_value)

    async def _get_pending_bridge_tx(self):
        proxy = self.scroll.get_random_proxy()
        tx_list = await self.scroll.get_bridge_tx_list(4, proxy)

        for tx in tx_list:
            # tx["message_type"] == 3 это депозит
            if tx["tx_status"] != 8 and tx["message_type"] == 3:
                return tx
            # tx["message_type"] == 2 это вывод
            elif tx["tx_status"] != 2 and tx["message_type"] == 2:
                return tx
            # какой то другой тип
            if tx["tx_status"] != 8 and tx["message_type"] not in [2, 3]:
                return tx
        return None

    async def _get_okex_total_balance(self, symbol) -> float:
        funding_balance = self.okex.get_funding_balance(symbol)
        trading_balance = self.okex.get_trading_balance(symbol)
        total_balance = funding_balance + trading_balance

        logger.debug(
            f"{symbol} funding balance: {funding_balance}; trading balance: {trading_balance}; total: {total_balance}")

        return float(total_balance)

    async def _buy_and_withdraw_eth(self, amount: float):
        return self.okex.buy_token_and_withdraw("ETH", "Ethereum", self.address, amount)

    async def _mint_ambient_providoor_badge_iteration(self):
        min_deposit_amount_usd = 900
        logger.info(f"[{self.account_id}][{self.address}] Start check conditions to mint Ambient Providoor badge")

        is_minted_badge = await self.scroll.is_ambient_providoor_badge_minted()

        # TODO: проверяем что нет pending transaction у аккаунта

        if is_minted_badge:
            # если у нас уже есть значок, то нам нужно вывести деньги назад на окекс
            logger.info(f"[{self.account_id}][{self.address}] Badge minted")
            result = await self._withdraw_to_okex()
            return result

        logger.info(f"[{self.account_id}][{self.address}] Badge is not minted")

        # если у нас нет значка, то нужно его сминтить
        is_badge_eligible = await self.scroll.is_ambient_providoor_badge_eligible()

        if is_badge_eligible:
            # если у нас нет значка, но мы можем его сминтить, то запускаем минт
            logger.info(f"[{self.account_id}][{self.address}] Badge is eligible to mint")
            await self.scroll.mint_ambient_providoor_badge()
            return True

        logger.info(f"[{self.account_id}][{self.address}] Badge is not eligible to mint")

        eth_price_in_usd = await get_eth_usd_price("scroll")

        logger.info(f"[{self.account_id}][{self.address}] ETH price is {eth_price_in_usd} USD")

        current_deposit = await self.ambient_finance.get_total_deposit_amount()
        est_current_deposit_in_usd = current_deposit * eth_price_in_usd

        logger.info(f"[{self.account_id}][{self.address}] current deposit ~{est_current_deposit_in_usd} USD")

        if est_current_deposit_in_usd > min_deposit_amount_usd:
            # если текущий депозит уже больше необходимого, но значок ещё не доступен, то нужно просто ждать
            logger.info(
                f"[{self.account_id}][{self.address}] current deposit is enough, but the badge is still not eligible to mint, need to wait some time")
            return True

        balance_eth_wei = await self.w3.eth.get_balance(self.address)
        balance_eth = balance_eth_wei / 10 ** 18
        balacne_wrseth_wei = await self.get_wrseth_balance()
        balance_wrseth = balacne_wrseth_wei / 10 ** 18

        logger.info(
            f"[{self.account_id}][{self.address}] current Scroll balance: {balance_eth} ETH and {balance_wrseth} wrsETH")

        if eth_price_in_usd * (balance_eth + balance_wrseth) > min_deposit_amount_usd:
            logger.info(
                f"[{self.account_id}][{self.address}] current Scroll balance is enough to make deposit")
            # если на аккаунте достаточно средств, чтобы сделать новый депозит, то делаем его
            await self._make_1000_usd_deposit_ambient()
            return True

        # если на аккаунте недостаточно средств, то проверяем нет ли пендинг вывода
        bridge_tx_pending = await self._get_pending_bridge_tx()
        if bridge_tx_pending:
            # мы не можем действовать пока нет пендинг бридж транзакции
            logger.info(
                f"[{self.account_id}][{self.address}] there PENDING bridge TX, wait it for complete before take any actions: {bridge_tx_pending}")
            return True

        logger.info(
            f"[{self.account_id}][{self.address}] there no PENDING bridge TXs, continue")

        # теперь мы должно проверить, что в майннете нет нужного баланса, чтобы сделать депозит
        balance_eth_wei_ethereum = await self.scroll_ethereum.w3.eth.get_balance(self.address)
        balance_eth_ethereum = balance_eth_wei_ethereum / 10 ** 18
        balance_eth_ethereum_in_usd = eth_price_in_usd * balance_eth_ethereum

        logger.info(f"[{self.account_id}][{self.address}] current Ethereum balance: {balance_eth_ethereum} ETH (~{balance_eth_ethereum_in_usd} USD)")

        if balance_eth_ethereum_in_usd > min_deposit_amount_usd:
            # если на аккаунте в майннете достаточно средств, чтобы сделать новый депозит, то делаем бридж
            logger.info(
                f"[{self.account_id}][{self.address}] current Ethereum balance is enough to make deposit, try to make bridge to Scroll")
            await self._deposit_economy_to_scroll()
            return True

        # если на аккаунте в майннете недостаточно средств, чтобы сделать новый депозит, то делаем вывод с биржи
        # но для начала проверяем что нет сейчас пендинг выводов
        pending_withdrawals = self.okex.get_pending_withdrawals(self.address)

        if len(pending_withdrawals) > 0:
            logger.info(f"There are pending withdrawals, have to wait them before continue: {pending_withdrawals}")
            return True

        logger.info(f"There are no pending withdrawals")

        # делаем вывод ETH
        amount_to_withdraw = min_deposit_amount_usd * (1 / eth_price_in_usd) * 1.1
        logger.info(f"Try to buy and withdraw {amount_to_withdraw} ETH")

        okex_balance_usdt = await self._get_okex_total_balance("USDT")
        okex_balance_eth = await self._get_okex_total_balance("ETH")
        okex_balance_usdt_in_eth = okex_balance_usdt * (1 / eth_price_in_usd)
        can_withdraw_eth_estimated = okex_balance_usdt_in_eth + okex_balance_eth
        can_withdraw_usd_estimated = can_withdraw_eth_estimated * eth_price_in_usd

        logger.info(f"Can withdraw from Okex approximately {can_withdraw_eth_estimated} ETH (~{can_withdraw_usd_estimated} USD)")

        if can_withdraw_eth_estimated < amount_to_withdraw:
            logger.info(
                f"Not enough money on Okex to continue, need: {amount_to_withdraw} ETH, but can only ~{can_withdraw_eth_estimated} ETH")
            return None

        await self._buy_and_withdraw_eth(amount_to_withdraw)

        logger.info(f"Done this iteration, return")

        return True

    async def mint_ambient_providoor_badge(
            self,
    ):
        self.okex = Okex(OKEX_API_KEY, OKEX_SECRET_KEY, OKEX_PASSPHRASE, OKEX_PROXY)
        i = 1
        while True:
            logger.info(f"Start {i} iteration")
            iteration_result = await self._mint_ambient_providoor_badge_iteration()

            if iteration_result is None:
                logger.info(f"Finished script")
                break
            elif iteration_result is False:
                logger.info(f"Finished {i} iteration")
                await sleep(30, 90)
            else:
                logger.info(f"Finished {i} iteration")
                await sleep(15, 30)
            i+=1
