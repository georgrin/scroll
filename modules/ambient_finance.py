import math
import random

import aiohttp

from loguru import logger
from web3 import Web3
from eth_abi import encode
from config import (AMBIENT_FINANCE_ROUTER_ABI,
                    AMBIENT_FINANCE_CROC_ABI,
                    AMBIENT_FINANCE_CONTRACTS,
                    SCROLL_TOKENS,
                    RSETH_ABI,
                    RSETH_CONTRACT)
from utils.gas_checker import check_gas
from utils.helpers import retry, checkLastIteration, get_action_tx_count
from utils.sleeping import sleep
from .account import Account


q64 = 2 ** 64
wrsETH = "WRSETH"


def price_to_tick(p):
    return math.floor(math.log(p, 1.0001))


def tick_to_price(p):
    return 1.0001 ** p


def price_to_sqrtp(p):
    return int(math.sqrt(p) * q64)


def sqrtp_to_price(p):
    return (p / q64) ** 2


def liquidity0(amount, pa, pb):
    if pa > pb:
        pa, pb = pb, pa
    return (amount * (pa * pb) / q64) / (pb - pa)


def liquidity1(amount, pa, pb):
    if pa > pb:
        pa, pb = pb, pa
    return amount * q64 / (pb - pa)


def calc_amount0(liq, pa, pb):
    if pa > pb:
        pa, pb = pb, pa
    return int(liq * q64 * (pb - pa) / pa / pb)


def calc_amount1(liq, pa, pb):
    if pa > pb:
        pa, pb = pb, pa
    return int(liq * (pb - pa) / q64)


class AmbientFinance(Account):
    def __init__(self, account_id: int, private_key: str, recipient: str) -> None:
        super().__init__(account_id=account_id, private_key=private_key, chain="scroll", recipient=recipient)

        self.swap_contract = self.get_contract(AMBIENT_FINANCE_CONTRACTS["router"], AMBIENT_FINANCE_ROUTER_ABI)
        self.croc_contract = self.get_contract(AMBIENT_FINANCE_CONTRACTS["croc_query"], AMBIENT_FINANCE_CROC_ABI)
        self.wrs_eth_pool_contract = self.get_contract(RSETH_CONTRACT, RSETH_ABI)
        self.pool_id = 420
        self.eth_address = "0x0000000000000000000000000000000000000000"
        self.wrseth_address = "0xa25b25548b4c98b0c7d3d27dca5d5ca743d68b7f"

    async def get_action_tx_count(self):
        return await get_action_tx_count(
            self.account.address,
            self.swap_contract.address,
            'scroll')

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
            ["address", "address", "uint256", "bool", "bool", "uint128", "uint16", "uint128", "uint128", "uint8"],
            [base, quote, self.pool_id, is_buy, in_base_amount, amount, tip, limit_price, min_out, settle_flags]
        )

        transaction = await self.swap_contract.functions.userCmd(
            callpath_code,
            cmd
        ).build_transaction(tx_data)

        return transaction

    async def get_curve_price(self,
                              base: str,
                              quote: str):
        return await self.croc_contract.functions.queryPrice(
            Web3.to_checksum_address(base),
            Web3.to_checksum_address(quote),
            self.pool_id
        ).call()

    async def get_price(
            self,
            base: str,
            quote: str,
            is_buy: bool
    ):
        price = int((await self.get_curve_price(base, quote) / q64) ** 2)

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

        # return price
        price = await self.get_price(base, quote, is_buy)

        min_amount_out_wei = int(float(price) * float(amount_wei))
        min_amount_out_wei = int(min_amount_out_wei * (1 - slippage / 100))

        logger.info(f"Get pool price: {price}, set min amount out wei")

        # Using a meaningful value here is not necessary if the caller is uninterested in partial fills and slippage is set with minOut parameter value
        # In this case this value can be set to "max values" below based on the direction of the swap:
        limit_price = 21267430153580247136652501917186561137 if is_buy else 65537

        if from_token != "ETH":
            logger.info(f"Check if {from_token} is allow to swap")
            await self.approve(int(amount_wei * 100), SCROLL_TOKENS[from_token], self.swap_contract.address)

        contract_txn = await self._swap(base,
                                        quote,
                                        amount_wei,
                                        is_buy,
                                        is_base_amount,
                                        min_amount_out_wei,
                                        limit_price)

        signed_txn = await self.sign(contract_txn)
        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())

    @retry
    @check_gas
    async def deposit(self,
                      min_amount: float,
                      max_amount: float,
                      decimal: int,
                      all_amount: bool,
                      min_percent: int,
                      max_percent: int,
                      range_width: float = 1,
                      min_left_eth_balance: float = 0,
                      max_left_eth_balance: float = 0):
        amount_wei_wrseth, amount_wrseth, balance = await self.get_amount(
            wrsETH,
            min_amount,
            max_amount,
            decimal,
            all_amount,
            min_percent,
            max_percent
        )

        logger.info(f"[{self.account_id}][{self.address}] Make deposit on Ambient Finance | {amount_wrseth} {wrsETH}")

        if amount_wei_wrseth < 500000000000000:  # 0.0005 ETH
            logger.info(f"[{self.account_id}][{self.address}] Cannot deposit, deposit amount less than min deposit, {amount_wrseth} < 0.0005")
            return False

        logger.info(f"Check if {wrsETH} is allow to deposit")
        allowed_amount = await self.check_allowance(SCROLL_TOKENS[wrsETH], self.swap_contract.address)
        if allowed_amount < amount_wei_wrseth:
            logger.info(f"Allowed {allowed_amount} {wrsETH} to deposit, create approve tx")
            # делаем апрув для амаунта в 10 раз больше, чтобы не делать повторные транзакции при попытках с большим амаунтом
            await self.approve(int(amount_wei_wrseth * 10), SCROLL_TOKENS[wrsETH], self.swap_contract.address)

        # (12, '0x0000000000000000000000000000000000000000', '0xa25b25548b4c98b0c7d3d27dca5d5ca743d68b7f', 420, 4,
        # 208, 5896785964741205, 18453258108933701632, 18554781007215525888, 0, '0x0000000000000000000000000000000000000000')

        code = 11  # Fixed in base tokens
        base = self.eth_address
        quote = self.wrseth_address

        eth_wrs_curve_price = await self.get_curve_price(base, quote)
        price = sqrtp_to_price(eth_wrs_curve_price)

        low_tick = price_to_tick(price * (1 - range_width / 100))
        low_tick = int(low_tick / 4) * 4

        upper_tick = price_to_tick(price * (1 + range_width / 100))
        upper_tick = int(upper_tick / 4) * 4 + 4

        low_price = tick_to_price(low_tick)
        upper_price = tick_to_price(upper_tick)

        limitLower = price_to_sqrtp(low_price)
        limitHigher = price_to_sqrtp(upper_price)
        settleFlags = 0
        lpConduit = self.eth_address

        amount_wei_eth = int(amount_wei_wrseth * (1 / price))

        liq_eth = liquidity0(amount_wei_eth, eth_wrs_curve_price, limitHigher)
        liq_wrseth = liquidity1(amount_wei_wrseth, eth_wrs_curve_price, limitLower)
        liq = int(min(liq_eth, liq_wrseth))

        amount_wei_eth = calc_amount0(liq, limitHigher, eth_wrs_curve_price)
        amount_wei_wrseth = calc_amount1(liq, limitLower, eth_wrs_curve_price)

        amount_eth = amount_wei_eth / 10 ** 18
        amount_wrseth = (amount_wei_wrseth / 10 ** 18)

        min_left_eth_balance = round(random.uniform(min_left_eth_balance, max_left_eth_balance), decimal) if min_left_eth_balance > 0 or max_left_eth_balance > 0 else 0

        # мы проверяем что после депозита на аккаунте останется минимальный баланс из настроек
        balance_eth = await self.w3.eth.get_balance(self.address)
        if min_left_eth_balance > 0 and balance_eth - amount_wei_eth < self.w3.to_wei(min_left_eth_balance, "ether"):
            logger.info(
                f"[{self.account_id}][{self.address}] Cannot deposit {amount_eth} ETH, " +
                f"because left balance would be less than {min_left_eth_balance} ETH, " +
                f"new deposit amount is {(amount_wei_eth - self.w3.to_wei(min_left_eth_balance, 'ether')) / 10 ** 18}"
            )

            # уменьшаем амаунт депозита, чтобы на балансе осталось мин баланс
            amount_wei_eth -= self.w3.to_wei(min_left_eth_balance, "ether")
            amount_wei_wrseth -= self.w3.to_wei(min_left_eth_balance, "ether")
            amount_eth = amount_wei_eth / 10 ** 18
            amount_wrseth = (amount_wei_wrseth / 10 ** 18)

        qty = amount_wei_eth

        logger.info(f"[{self.account_id}][{self.address}] Deposit {amount_wrseth} wrsETH and {amount_eth} ETH (price range: {low_price}-{upper_price})")

        cmd = encode(
            ["uint8",
             "address",
             "address",
             "uint256",
             "int24",
             "int24",
             "uint128",
             "uint128",
             "uint128",
             "uint8",
             "address"],
            [code,
             base,
             quote,
             self.pool_id,
             low_tick,
             upper_tick,
             qty,
             limitLower,
             limitHigher,
             settleFlags,
             lpConduit]
        )
        callpath_code = 128

        tx_data = await self.get_tx_data(amount_wei_eth)

        transaction = await self.swap_contract.functions.userCmd(
            callpath_code,
            cmd
        ).build_transaction(tx_data)

        signed_txn = await self.sign(transaction)
        txn_hash = await self.send_raw_transaction(signed_txn)

        await self.wait_until_tx_finished(txn_hash.hex())

    async def get_liquidity_positions(self, base: str, quote: str):
        url = "https://ambindexer.net/scroll-gcgo/user_pool_positions"
        params = {
            "user": self.address,
            "base": base,
            "quote": quote,
            "poolIdx": self.pool_id,
            "chainId": "0x82750",
        }

        async with aiohttp.ClientSession() as session:
            response = await session.get(url=url, params=params)

            if response.status == 200:
                positions_data = await response.json()

                if "data" in positions_data and type(positions_data["data"]) is list:
                    return positions_data["data"]
                else:
                    logger.error(f"[{self.account_id}][{self.address}][{self.chain}] Ambient finance positions wrong response: {positions_data}")

                    raise Exception(f"Ambient finance positions wrong response: {positions_data}")
            else:
                logger.error(f"[{self.account_id}][{self.address}][{self.chain}] Bad Ambient finance request to get positions")

                return False

    async def get_total_deposit_amount(self) -> float:
        base = self.eth_address
        quote = self.wrseth_address

        positions = await self.get_liquidity_positions(base, quote)
        active_positions = [p for p in positions if int(p["concLiq"]) > 0]

        total = 0
        for position in active_positions:
            total += position["aprEst"]

        return total

    @retry
    @check_gas
    async def withdrawal(self):
        code = 2  # Fixed in liquidity units
        base = self.eth_address
        quote = self.wrseth_address
        settleFlags = 0
        lpConduit = self.eth_address

        positions = await self.get_liquidity_positions(base, quote)
        active_positions = [p for p in positions if int(p["concLiq"]) > 0]

        logger.info(f"[{self.account_id}][{self.address}][{self.chain}] have {len(active_positions)} active position at ETH/wrsETH pool (total {len(positions)})")

        count = 1

        for position in active_positions:
            try:
                logger.info(
                    f"[{self.account_id}][{self.address}][{self.chain}] start remove {count} position: {position['positionId']}, {position['concLiq']} liq")

                cmd = encode(
                    ["uint8",
                     "address",
                     "address",
                     "uint256",
                     "int24",
                     "int24",
                     "uint128",
                     "uint128",
                     "uint128",
                     "uint8",
                     "address"],
                    [code,
                     base,
                     quote,
                     self.pool_id,
                     position["bidTick"],
                     position["askTick"],
                     position["concLiq"],
                     price_to_sqrtp(tick_to_price(position["bidTick"] + 4)),
                     price_to_sqrtp(tick_to_price(position["askTick"] - 4)),
                     settleFlags,
                     lpConduit]
                )
                callpath_code = 128

                tx_data = await self.get_tx_data()

                transaction = await self.swap_contract.functions.userCmd(
                    callpath_code,
                    cmd
                ).build_transaction(tx_data)

                signed_txn = await self.sign(transaction)
                txn_hash = await self.send_raw_transaction(signed_txn)

                await self.wait_until_tx_finished(txn_hash.hex())

                count += 1
                await sleep(15, 30)
            except Exception as ex:
                logger.error(f"Failed to remove liquidity {count} position {position['positionId']}: {ex}")

                raise
