import random

from loguru import logger

from config import SCROLL_TOKENS
from utils.sleeping import sleep
from . import AmbientFinance, Kelp
from .account import Account

wrsETH = "WRSETH"


class Scenarios(Account):
    def __init__(self, account_id: int, private_key: str, recipient: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="scroll", recipient=recipient)

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
            f"[{self.account_id}][{self.address}] Current estimated ETH amount deposited to wrsETH/ETH pool: {current_deposit * 0.5}")

        if current_deposit * 0.5 > max_deposit_amount:
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

                kelp = Kelp(self.account_id, self.private_key, self.recipient)
                kelp_result = await kelp.deposit(
                    kelp_min_amount if old_kelp_min_percent == new_kelp_min_percent else (
                        balance_wrseth + balance_eth) * new_kelp_min_percent / 100 / 10 ** 18,
                    kelp_max_amount if old_kelp_min_percent == new_kelp_min_percent else (
                        balance_wrseth + balance_eth) * new_kelp_max_percent / 100 / 10 ** 18,
                    decimal,
                    kelp_all_amount if old_kelp_min_percent == new_kelp_min_percent else False,
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

    async def sell_redundant_wrseth_and_reposit_ambient(self,
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
                                                        max_deposit_percent: int):
        logger.info(f"[{self.account_id}][{self.address}] Start check redundant wrsETH and reposit ambient positions")
        ambient_finance = AmbientFinance(self.account_id, self.private_key, self.recipient)

        min_left_eth_balance_wei = int(self.w3.to_wei(min_left_eth_balance, "ether"))
        total_deposit_amount = await ambient_finance.get_total_deposit_amount()
        balance_wrseth_wei = await self.get_wrseth_balance()
        balance_wrseth = balance_wrseth_wei / 10 ** 18

        if total_deposit_amount == 0:
            logger.info(f"[{self.account_id}][{self.address}] No active positions, skipping")
            return

        logger.info(
            f"[{self.account_id}][{self.address}] account have {balance_wrseth} wrsETH and {total_deposit_amount} total deposit amount")

        balance_eth_wei = await self.w3.eth.get_balance(self.address)
        balance_eth = balance_eth_wei / 10 ** 18
        logger.info(
            f"[{self.account_id}][{self.address}] balance: {balance_eth} ETH, {balance_wrseth} {wrsETH}")

        total_wrseth_eth_balance_wei = balance_wrseth_wei + balance_eth_wei
        deposit_current_proportion = round(self.w3.to_wei(total_deposit_amount, "ether") / total_wrseth_eth_balance_wei, 4)
        deposit_current_percent = int(self.w3.to_wei(total_deposit_amount, "ether") / (
                    self.w3.to_wei(total_deposit_amount, "ether") + total_wrseth_eth_balance_wei) * 100)

        # TODO: ДОБАВИТЬБ СЮДА УЧЁТ баланс wrsETH

        logger.info(
            f"[{self.account_id}][{self.address}] current deposit proportion {deposit_current_proportion} to total ETH and wrsETH balances")

        if deposit_current_percent > min_deposit_percent * 0.95:
            logger.info(
                f"[{self.account_id}][{self.address}] current deposit is {deposit_current_percent}% of total ETH and wrsETH balances, that is enough")

            # Если текущий баланс wrsETH достаточно не маленький, то продаём его
            if balance_wrseth_wei > 200000000000000:
                logger.info(f"[{self.account_id}][{self.address}] try to sell redundant {balance_wrseth} wrsETH")
                return await self._sell_wrseth()
            return True

        logger.info(
            f"[{self.account_id}][{self.address}] current deposit is {deposit_current_percent}% of total ETH balance, should be minimum {min_deposit_percent}%")

        new_deposit = total_deposit_amount * (min_deposit_percent / deposit_current_percent)
        # считаем сколько нужно добавить в позицию, чтобы депозит был нужного объёма
        need_deposit = new_deposit - total_deposit_amount - balance_wrseth
        need_deposit_wei = int(self.w3.to_wei(need_deposit, "ether")) if need_deposit > 0 else 0

        if need_deposit_wei > 0:
            logger.info(f"[{self.account_id}][{self.address}] will spend {need_deposit} ETH to increase current deposit")
        else:
            logger.info(f"[{self.account_id}][{self.address}] no need to spend ETH balance to increase current deposit")

        total_wrseth_eth_amount_wei = balance_wrseth_wei + balance_eth_wei
        should_be_wrseth_wei = int(0.5 * (total_wrseth_eth_amount_wei * random.randint(max_deposit_percent, max_deposit_percent) / 100))
        need_to_sell_wrseth_wei = balance_wrseth_wei - should_be_wrseth_wei if balance_wrseth_wei > should_be_wrseth_wei else 0

        # так как мы продадим лишний wrsETH, то оставш
        # считаем новый баланс после депозита, он не должен быть слишком маленьким
        balance_eth_after_deposit_wei = balance_eth_wei - need_deposit_wei + need_to_sell_wrseth_wei
        balance_eth_after_deposit = balance_eth_after_deposit_wei  / 10 ** 18
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
                if balance_wrseth > 200000000000000:  # 0.0002 ETH
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

            # делаем попытку вывести максимум 5 рах
            if i > 3:
                logger.error(f"[{self.account_id}][{self.address}] Failed to withdraw all positions, leave")
                raise Exception("Failed to withdraw all positions")
            else:
                logger.error(f"[{self.account_id}][{self.address}] Failed to withdraw all positions, try again")
            await sleep(40, 80)

        balance_wrseth_wei = await self.get_wrseth_balance()
        balance_wrseth = balance_wrseth_wei / 10 ** 18
        balance_eth_wei = await self.w3.eth.get_balance(self.address)
        balance_eth = balance_eth_wei / 10 ** 18

        logger.info(
            f"[{self.account_id}][{self.address}] balance after withdrawal: {balance_wrseth} wrsETH, {balance_eth} ETH")

        total_wrseth_eth_amount_wei = balance_wrseth_wei + balance_eth_wei
        should_be_wrseth_wei = int(0.5 * (total_wrseth_eth_amount_wei * random.randint(max_deposit_percent, max_deposit_percent) / 100))

        # TODO: проверяем что после покупки останется минимальный баланс
        need_to_buy_wrseth_wei = should_be_wrseth_wei - balance_wrseth_wei
        need_to_buy_wrseth = need_to_buy_wrseth_wei / 10 ** 18

        if need_to_buy_wrseth_wei > 400000000000000:   # 0.0004 ETH
            logger.info(
                f"[{self.account_id}][{self.address}] need to buy {need_to_buy_wrseth} wrsETH to make deposit")

            await self._buy_wrseth(need_to_buy_wrseth)
            await sleep(30, 60)
        else:
            logger.info(f"[{self.account_id}][{self.address}] no need to buy wrsETH to make deposit")

        need_to_sell_wrseth_wei = balance_wrseth_wei - should_be_wrseth_wei
        need_to_sell_wrseth = need_to_sell_wrseth_wei / 10 ** 18

        if need_to_sell_wrseth_wei > 400000000000000:   # 0.0004 ETH
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

        if balance_wrseth_wei > 200000000000000:  # 0.0002 ETH
            logger.info(f"[{self.account_id}][{self.address}] try to sell redundant {balance_wrseth} wrsETH")
            await self._sell_wrseth()

        try:
            total_deposit_amount = await ambient_finance.get_total_deposit_amount()
            balance_wrseth_wei = await self.get_wrseth_balance()
            balance_eth_wei = await self.w3.eth.get_balance(self.address)
            total_wrseth_eth_balance_wei = balance_wrseth_wei + balance_eth_wei
            deposit_current_percent = int(self.w3.to_wei(total_deposit_amount, "ether") / (
                        self.w3.to_wei(total_deposit_amount, "ether") + total_wrseth_eth_balance_wei) * 100)

            logger.info(f"[{self.account_id}][{self.address}] current deposit is {deposit_current_percent}% of total ETH balance, should be minimum {min_deposit_percent}%")
        except Exception as ex:
            logger.error(f"Failed to get deposit proportion after deposit: {ex}")
