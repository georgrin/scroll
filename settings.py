# RANDOM WALLETS MODE
RANDOM_WALLET = True  # True/False

# EXPLORER CACHE
EXPLORER_CACHE_MS = 1000 * 3

# removing a wallet from the list after the job is done
REMOVE_WALLET = False

# пропускаем кошелёк, если у него кол-во транзакций больше (для отключения ставим 0)
MAX_TX_COUNT_FOR_WALLET = 0

# пропускаем кошелёк если со времени последней транзакции прошло меньше времени (для отключения ставим 0)
MIN_TIME_AFTER_LAST_TX_S = 0

SLEEP_FROM = 500  # Second
SLEEP_TO = 1000  # Second

QUANTITY_THREADS = 1

THREAD_SLEEP_FROM = 5
THREAD_SLEEP_TO = 5

# GWEI CONTROL MODE
CHECK_GWEI = False  # True/False
MAX_GWEI = 20

MAX_PRIORITY_FEE = {
    "ethereum": 0.01,
    "polygon": 40,
    "arbitrum": 0.1,
    "base": 0.1,
    "zksync": 0.25,
}

GAS_MULTIPLIER = 1
GAS_LIMIT_MULTIPLIER = 1.3

# RETRY MODE
RETRY_COUNT = 3

LAYERSWAP_API_KEY = ""
SCROLL_API_KEY = ""
ETHEREUM_API_KEY = ""

# PROXY = "socks5://127.0.0.1:1080"
PROXY = None
# Пока используется только для запросов к Scroll (офф сайт)
USE_PROXIES = True
