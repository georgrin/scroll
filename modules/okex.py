import time
import ccxt

from decimal import Decimal
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple

from ccxt import RequestTimeout, RateLimitExceeded
from onecache import CacheDecorator
from loguru import logger

from utils.helpers import retry_sync


class ExchangeError(Exception):
    pass


class NotWhitelistedAddress(ExchangeError):
    pass


class WithdrawCanceled(ExchangeError):
    pass


class WithdrawFailed(ExchangeError):
    pass


class WithdrawTimeout(ExchangeError):
    pass


class WithdrawNotFound(ExchangeError):
    pass


@dataclass
class WithdrawInfo:
    symbol: str
    chain: str
    fee: float
    min_amount: float


@dataclass
class DepositInfo:
    symbol: str
    chain: str
    can_deposit: bool
    min_amount: float


class WithdrawStatus(Enum):
    INITIATED = 0
    PENDING = 1
    FINISHED = 2
    CANCELED = 3
    FAILED = 4


OKEX_RETRIES = 5
OKEX_RETRY_DELAY = 15
WAIT_TX_SLEEP = 30
MAX_TIME_WAIT_OKEX_WITHDRAWAL = 60 * 60


class Okex:
    NAME = "okex"

    def __init__(self, api_key: str, secret_key: str, passphrase: str, proxy: str = None):
        if not (api_key or secret_key or passphrase):
            raise ValueError(f"Okex config not defined (api_key, secret_key and passphrase are mandatory)")
        ccxt_args = {
            "apiKey": api_key,
            "secret": secret_key,
            "enableRateLimit": True,
            "password": passphrase,
            "timeout": 30000,
        }
        if proxy:
            logger.info(f"Use Okex proxy: {proxy}")
            ccxt_args['proxies'] = {
                'http': proxy,
                'https': proxy
            }
        self._api = getattr(ccxt, "okx")(ccxt_args)

        self.funding_account = 'funding'
        self.trading_account = 'spot'

    @CacheDecorator(ttl=1000 * 60 * 30)
    @retry_sync(OKEX_RETRIES, (RequestTimeout, RateLimitExceeded), OKEX_RETRY_DELAY, OKEX_RETRY_DELAY * 2)
    def _fetch_currencies_data(self):
        return self._api.fetch_currencies()

    @staticmethod
    def convert_symbol(symbol: str, network_name: str):
        return symbol

    @staticmethod
    def convert_network(network_name: str, symbol: str):
        if network_name.lower() == "ethereum":
            return "ERC20"
        return network_name

    @staticmethod
    def _get_chain_name(symbol: str, okx_network: str):
        return f"{symbol}-{okx_network}"

    def _get_withdraw_info(self, symbol: str) -> List[WithdrawInfo]:
        currencies = self._fetch_currencies_data()
        chains_info = currencies[symbol]['networks']

        result = []

        for chain_info in chains_info.values():
            info = WithdrawInfo(symbol, chain_info["info"]["chain"], chain_info["fee"],
                                chain_info["limits"]["withdraw"]["min"])
            result.append(info)

        return result

    def _get_deposit_info(self, symbol: str) -> List[DepositInfo]:
        currencies = self._fetch_currencies_data()
        if symbol not in currencies:
            raise Exception(f"OKEX doesn't support {symbol} currency")
        chains_info = currencies[symbol]["networks"]

        result = []

        for chain_info in chains_info.values():
            info = DepositInfo(symbol, chain_info["info"]["chain"], chain_info["info"]["canDep"],
                               float(chain_info["info"]["minDep"]))
            result.append(info)

        return result

    def get_withdraw_info(self, network_symbol: str, network: str) -> WithdrawInfo:
        symbol = self.convert_symbol(network_symbol, network)
        okx_network = self.convert_network(network, network_symbol)

        withdraw_options = self._get_withdraw_info(symbol)
        chain = self._get_chain_name(symbol, okx_network)
        withdraw_info = next((option for option in withdraw_options if option.chain == chain), None)

        if not withdraw_info:
            supported_chains = [option.chain for option in withdraw_options]
            raise ExchangeError(f"OKEX doesn't support {chain} withdrawals, supported chains: {supported_chains}")

        return withdraw_info

    def get_deposit_info(self, network_symbol: str, network: str) -> DepositInfo:
        symbol = self.convert_symbol(network_symbol, network)
        okx_network = self.convert_network(network, network_symbol)

        deposit_options = self._get_deposit_info(symbol)
        chain = self._get_chain_name(symbol, okx_network)
        deposit_info = next((option for option in deposit_options if option.chain == chain), None)

        if not deposit_info:
            supported_chains = [option.chain for option in deposit_options]
            raise ExchangeError(f"OKEX doesn't support {chain} deposits, supported chains: {supported_chains}")

        return deposit_info

    @CacheDecorator(ttl=1000 * 60 * 30)
    @retry_sync(OKEX_RETRIES, (RequestTimeout, RateLimitExceeded), OKEX_RETRY_DELAY, OKEX_RETRY_DELAY * 2)
    def get_trading_pair_info(self, base_symbol: str, quote_symbol: str) -> dict:
        trading_pairs = self._api.fetch_markets_by_type("SPOT")
        pair_name = f"{base_symbol}-{quote_symbol}"
        trading_pair = next((tp for tp in trading_pairs if tp["info"]["instId"] == pair_name), None)
        if not trading_pair:
            raise ExchangeError(f"OKEX doesn't support {pair_name} trading")

        # {..., "info": {"alias":"","baseCcy":"MATIC","category":"1","ctMult":"","ctType":"","ctVal":"","ctValCcy":"","expTime":"",
        # "instFamily":"","instId":"MATIC-USDT","instType":"SPOT","lever":"10","listTime":"1617008400000",
        # "lotSz":"0.000001","maxIcebergSz":"999999999999.0000000000000000","maxLmtAmt":"20000000",
        # "maxLmtSz":"999999999999","maxMktAmt":"1000000","maxMktSz":"1000000","maxStopSz":"1000000",
        # "maxTriggerSz":"999999999999.0000000000000000","maxTwapSz":"999999999999.0000000000000000",
        # "minSz":"1","optType":"","quoteCcy":"USDT","settleCcy":"","state":"live","stk":"","tickSz":"0.0001","uly":""}}

        return trading_pair

    @retry_sync(OKEX_RETRIES, (RequestTimeout, RateLimitExceeded), OKEX_RETRY_DELAY, OKEX_RETRY_DELAY * 2)
    def withdraw(self, symbol: str, amount: float, network: str, address: str) -> str:
        """ Method that initiates the withdrawal and returns the withdrawal id """
        logger.warning(
            f'{symbol} withdraw initiated from OKEX. Amount: {amount}. Network: {network}. Address: {address}')
        withdraw_info = self.get_withdraw_info(symbol, network)
        amount -= withdraw_info.fee
        logger.info(f'Amount with fee: {amount}')

        try:
            result = self._api.withdraw(symbol, amount, address,
                                        {"chain": withdraw_info.chain, 'fee': withdraw_info.fee, 'pwd': "-"})
        except Exception as ex:
            if 'Withdrawal address is not whitelisted for verification exemption' in str(ex):
                raise NotWhitelistedAddress(f'Unable to withdraw {symbol}({network}) to {address}. '
                                            f'The address must be added to the whitelist') from ex
            raise

        logger.debug(f'Withdraw result: {result}')
        withdraw_id = result['id']

        return str(withdraw_id)

    def wait_for_withdraw_to_finish(self, withdraw_id: str, timeout: int = MAX_TIME_WAIT_OKEX_WITHDRAWAL) -> None:
        logger.info(f'Waiting for #{withdraw_id} withdraw to be sent')

        time.sleep(WAIT_TX_SLEEP)  # Sleep to let the exchange process the withdrawal request
        start_time = time.time()

        while True:
            status, info = self.get_withdraw_status(withdraw_id)
            logger.debug(f'Withdrawal #{withdraw_id}: {status}')

            if status == WithdrawStatus.FINISHED:
                logger.info(f"Withdraw #{withdraw_id} finished")
                return

            if status == WithdrawStatus.CANCELED:
                raise WithdrawCanceled(f'Withdraw #{withdraw_id} canceled: {info}')

            if status == WithdrawStatus.FAILED:
                raise WithdrawFailed(f'Withdraw #{withdraw_id} failed: {info}')

            if time.time() - start_time >= timeout:
                raise WithdrawTimeout(f"Withdraw timeout reached. Id: {withdraw_id}")

            time.sleep(WAIT_TX_SLEEP)  # Wait for 30 seconds before checking again

    @retry_sync(OKEX_RETRIES, (RequestTimeout, RateLimitExceeded), OKEX_RETRY_DELAY, OKEX_RETRY_DELAY * 2)
    def get_pending_withdrawals(self, address: str) -> List[dict]:
        all_withdrawals = self._api.fetch_withdrawals()
        return [w for w in all_withdrawals if
                w["addressTo"].lower() == address.lower() and w["status"] == "pending"]

    @retry_sync(OKEX_RETRIES, (RequestTimeout, RateLimitExceeded), OKEX_RETRY_DELAY, OKEX_RETRY_DELAY * 2)
    def get_withdraw_status(self, withdrawal_id: str) -> Tuple[WithdrawStatus, str]:
        withdraw_info = self._api.fetch_withdrawal(withdrawal_id)
        return self._parse_withdraw_status(withdraw_info)

    @retry_sync(OKEX_RETRIES, (RequestTimeout, RateLimitExceeded), OKEX_RETRY_DELAY, OKEX_RETRY_DELAY * 2)
    def transfer_funds(self, symbol: str, amount: float, from_account: str, to_account: str):
        logger.info(f'{symbol} transfer initiated from {from_account} to {to_account}')
        self._api.transfer(symbol, amount, from_account, to_account)

    @retry_sync(OKEX_RETRIES, (RequestTimeout, RateLimitExceeded), OKEX_RETRY_DELAY, OKEX_RETRY_DELAY * 2)
    def buy_tokens_with_usdt(self, symbol: str, amount: float) -> Decimal:
        logger.info(f'Buy {amount} {symbol} with USDT')
        trading_symbol = symbol + '/USDT'

        creation_result = self._api.create_market_order(trading_symbol, 'buy', amount)
        order = self._api.fetch_order(creation_result['id'], trading_symbol)
        logger.debug("Created order: %r", order)

        filled = Decimal(order['filled'])
        fee = Decimal(order['fee']['cost'])
        received_amount = filled - fee

        return received_amount

    @retry_sync(OKEX_RETRIES, (RequestTimeout, RateLimitExceeded), OKEX_RETRY_DELAY, OKEX_RETRY_DELAY * 2)
    def get_funding_balance(self, symbol: str) -> Decimal:
        balance = self._api.fetch_balance(params={'type': self.funding_account})

        if symbol not in balance['total']:
            return Decimal("0")
        token_balance = Decimal(balance['total'][symbol])

        return token_balance

    @retry_sync(OKEX_RETRIES, (RequestTimeout, RateLimitExceeded), OKEX_RETRY_DELAY, OKEX_RETRY_DELAY * 2)
    def get_trading_balance(self, symbol: str) -> Decimal:
        balance = self._api.fetch_balance(params={'type': self.trading_account})

        if symbol not in balance['total']:
            return Decimal("0")
        token_balance = Decimal(balance['total'][symbol])

        return token_balance

    def transfer_usdt_for_order(self, symbol: str, amount: float):
        funding_balance_usdt = self.get_funding_balance("USDT")
        logger.debug(f"USDT funding balance: {funding_balance_usdt}")
        trading_balance_usdt = self.get_trading_balance("USDT")
        logger.debug(f"USDT trading balance: {trading_balance_usdt}")
        total_balance_usdt = funding_balance_usdt + trading_balance_usdt
        logger.debug(f"USDT total balance: {total_balance_usdt}")
        amount_usdt = self.convert_to_usdt(symbol, Decimal(amount))

        if amount_usdt > trading_balance_usdt:
            # у нас не хватает USDT для покупки
            if amount_usdt > total_balance_usdt:
                raise Exception(
                    f"Not enough USDT to buy {amount} {symbol} (has {total_balance_usdt}, need {amount_usdt})")
            # отправляем чуть больше USDT c funding чем нужно на случай изменения цены
            need_transfer_usdt = amount_usdt * Decimal(1.1) - trading_balance_usdt
            if need_transfer_usdt > funding_balance_usdt or need_transfer_usdt < 0:
                need_transfer_usdt = funding_balance_usdt

            logger.debug(f"Transfer {float(need_transfer_usdt)} USDT to {self.trading_account}")
            self.transfer_funds("USDT", float(need_transfer_usdt), self.funding_account, self.trading_account)
            self.wait_balance_update("USDT", float(need_transfer_usdt), float(funding_balance_usdt), self.funding_account, self.trading_account)

    def buy_token_and_withdraw(self, symbol: str, network: str, address: str, amount: float) -> None:
        internal_symbol = self.convert_symbol(symbol, network)
        internal_network = self.convert_network(network, symbol)

        logger.debug(f"Request buy and withdraw {amount} {symbol} ({internal_symbol})")
        if symbol == "USDT":
            raise Exception("Cannot buy USDT")

        withdraw_info = self.get_withdraw_info(symbol, network)

        if withdraw_info.min_amount > amount:
            raise Exception(
                f"Withdrawal amount is lower than the lower limit: {amount} < {withdraw_info.min_amount}")

        amount_need = amount + withdraw_info.fee
        logger.debug(f"{internal_symbol} amount_need: {amount_need} ({amount} + {withdraw_info.fee})")

        funding_balance = self.get_funding_balance(internal_symbol)
        logger.debug(f"{internal_symbol} funding balance: {funding_balance}")

        if funding_balance < amount_need:
            trading_balance = self.get_trading_balance(internal_symbol)
            logger.debug(f"{symbol} trading balance: {trading_balance}")
            total_balance = funding_balance + trading_balance
            logger.debug(f"{symbol} total balance: {total_balance}")

            if total_balance < amount_need:
                need_to_buy = (amount_need - float(total_balance)) * 1.1
                logger.debug(
                    f"No enough {internal_symbol} total balance ({total_balance} < {amount_need}), need to buy {need_to_buy}")
                self.transfer_usdt_for_order(internal_symbol, need_to_buy)
                bought_amount = self.buy_tokens_with_usdt(symbol, float(need_to_buy))
                logger.debug(f"{internal_symbol} bought amount: {bought_amount}")
                logger.debug(f"Transfer {float(bought_amount)} {internal_symbol} to {self.funding_account}")
                self.transfer_funds(internal_symbol, float(bought_amount), self.trading_account, self.funding_account)
            else:
                logger.debug(
                    f"Enough {internal_symbol} total balance ({total_balance} >= {amount_need}), transfer {trading_balance} to funding account")
                self.transfer_funds(internal_symbol, float(trading_balance), self.trading_account, self.funding_account)

            self.wait_balance_update(internal_symbol, float(amount_need), float(funding_balance), self.trading_account, self.funding_account)

        funding_balance_after_transfer = self.get_funding_balance(internal_symbol)
        logger.debug(f"{internal_symbol} funding balance after transfer: {funding_balance_after_transfer}")

        withdraw_id = self.withdraw(internal_symbol, float(funding_balance_after_transfer), internal_network, address)
        self.wait_for_withdraw_to_finish(withdraw_id)

    def wait_balance_update(self, symbol: str, amount_need: float, amount_was: float, src_type: str, dst_type: str, attempts: int = 5):
        logger.debug(f"Waiting {WAIT_TX_SLEEP}s for {symbol} transfer from {src_type} to {dst_type}")
        time.sleep(WAIT_TX_SLEEP)

        if src_type == dst_type:
            raise ValueError(f"Src and dst account type must be different, {src_type}={dst_type}")

        for i in range(1, attempts + 1):
            try:
                balance = self.get_funding_balance(
                    symbol) if dst_type == self.funding_account else self.get_trading_balance(symbol)
                if balance >= amount_need:
                    logger.debug(
                        f"Requested {symbol} transfer from {src_type} to {dst_type} finished (balance: {balance}, need: {amount_need})")
                    break
                elif amount_was < float(balance):
                    logger.debug(
                        f"Requested {symbol} transfer from {src_type} to {dst_type} finished with less balance then need (balance: {balance}, need: {amount_need})")
                else:
                    logger.debug(
                        f"Waiting for {symbol} transfer from {src_type} to {dst_type} (balance: {balance}, need: {amount_need} ({i}/{attempts} attempt)")
            except Exception as ex:
                logger.error(
                    f"Failed to check requested {symbol} transfer from {src_type} to {dst_type} ({i}/{attempts} attempt): {ex}")
            time.sleep(WAIT_TX_SLEEP)

    @CacheDecorator(ttl=1000 * 60)
    @retry_sync(OKEX_RETRIES, (RequestTimeout, RateLimitExceeded), OKEX_RETRY_DELAY, OKEX_RETRY_DELAY * 2)
    def get_price(self, symbol: str) -> Decimal:
        trading_symbol = symbol + '/USDT'
        ticker = self._api.fetch_ticker(trading_symbol)
        price = ticker['last']
        return Decimal(price)

    def convert_usdt_to(self, amount_usdt: Decimal, symbol: str) -> Decimal:
        price = self.get_price(symbol)
        return amount_usdt / price

    def convert_to_usdt(self, symbol: str, amount: Decimal) -> Decimal:
        price = self.get_price(symbol)
        return price * amount

    @staticmethod
    def _parse_withdraw_status(withdraw_info: dict) -> Tuple[WithdrawStatus, str]:
        if "status" not in withdraw_info:
            raise Exception(f"Incorrect withdraw_info: {withdraw_info}")

        info = withdraw_info.get("info", "No additional info")
        status = withdraw_info["status"]
        if status == "ok":
            # {'info': {'id': '8cce4cabfd3040c7ab6434ca94d7e192', 'amount': '0.02', 'transactionFee': '0.0005',
            #  'coin': 'BNB', 'status': '6', 'address': '....', 'txId': '...', 'applyTime': '2023-07-13 20:07:45',
            #  'network': 'BSC', 'transferType': '0', 'info': '0xeb2d2f1b8c558a40207669291fda468e50c8a0bb',
            #  'confirmNo': '20', 'walletType': '0', 'txKey': '', 'completeTime': '2023-07-13 20:09:41',
            #  'type': 'withdrawal'}, 'id': '8cce4cabfd3040c7ab6434ca94d7e192', 'txid':
            #  '...', 'timestamp': 1689278865000,
            #  'datetime': '2023-07-13T20:07:45.000Z', 'network': 'BSC', 'address': '...', 'addressTo':
            #  '...', 'addressFrom': None, 'tag': None, 'tagTo': None,
            #  'tagFrom': None, 'type': 'withdrawal', 'amount': 0.02, 'currency': 'BNB', 'status': 'ok', 'updated':
            # None, 'internal': False, 'fee': {'currency': 'BNB', 'cost': 0.0005}}
            return WithdrawStatus.FINISHED, info
        if status == "pending":
            # {'info': {'id': '8cce4cabfd3040c7ab6434ca94d7e192', 'amount': '0.02', 'transactionFee': '0.0005',
            #  'coin': 'BNB', 'status': '4', 'address': '...', 'txId': '...', 'applyTime': '2023-07-13 20:07:45',
            #  'network': 'BSC', 'transferType': '0', 'info': 'Please note that you will receive an email once it is
            #  completed.', 'confirmNo': '20', 'walletType': '0', 'txKey': '', 'type': 'withdrawal'},
            #  'id': '8cce4cabfd3040c7ab6434ca94d7e192', 'txid': '...', 'timestamp': 1689278865000,
            #  'datetime': '2023-07-13T20:07:45.000Z', 'network': 'BSC', 'address':
            #  '...', 'addressTo': '...', 'addressFrom': None, 'tag': None, 'tagTo': None,
            #  'tagFrom': None, 'type': 'withdrawal', 'amount': 0.02, 'currency': 'BNB', 'status': 'pending',
            #  'updated': None, 'internal': False, 'fee': {'currency': 'BNB', 'cost': 0.0005}}
            return WithdrawStatus.PENDING, info
        if status == 'canceled':
            return WithdrawStatus.CANCELED, info
        if status == 'failed':
            # {'info': {'id': '4b53f2b479c841169b3b44ab3f52e854', 'amount': '10', 'transactionFee': '0.1',
            #  'coin': 'MATIC', 'status': '3', 'address': '...', 'txId': '', 'applyTime': '2023-07-13 18:17:07',
            #  'network': 'MATIC', 'transferType': '0', 'info': 'Network busy, please try again later', 'walletType':
            #  '0', 'txKey': '', 'type': 'withdrawal'}, 'id': '4b53f2b479c841169b3b44ab3f52e854', 'txid': None,
            #  'timestamp': 1689272227000, 'datetime': '2023-07-13T18:17:07.000Z', 'network': 'MATIC', 'address':
            #  '...', 'addressTo': '...', 'addressFrom': None, 'tag': None, 'tagTo': None,
            #  'tagFrom': None, 'type': 'withdrawal', 'amount': 10.0, 'currency': 'MATIC', 'status': 'failed',
            #  'updated': None, 'internal': False, 'fee': {'currency': 'MATIC', 'cost': 0.1}}
            return WithdrawStatus.FAILED, info

        raise Exception(f'Unknown withdraw status: {withdraw_info}')
