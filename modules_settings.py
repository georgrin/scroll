import asyncio
from modules import *

module_cooldown = 8888888


async def deposit_scroll(account_id, key, recipient):
    """
    Deposit from official bridge
    ______________________________________________________
    all_amount - bridge from min_percent to max_percent
    """

    min_amount = 0.001
    max_amount = 0.002
    decimal = 4

    all_amount = True

    min_percent = 1
    max_percent = 1

    scroll = Scroll(account_id, key, "ethereum", recipient)
    await scroll.deposit(min_amount, max_amount, decimal, all_amount, min_percent, max_percent)


async def deposit_economy_scroll(account_id, key, recipient):
    """
    Deposit Economy from official bridge
    ______________________________________________________
    all_amount - bridge from min_percent to max_percent
    """

    min_amount = 0.01
    max_amount = 0.02
    decimal = 4

    all_amount = True

    min_percent = 1
    max_percent = 1

    scroll = Scroll(account_id, key, "ethereum", recipient)
    await scroll.deposit_economy(min_amount, max_amount, decimal, all_amount, min_percent, max_percent)


async def scroll_sing_terms_of_use(account_id, key, recipient):
    scroll = Scroll(account_id, key, "scroll", recipient)
    return await scroll.sign_terms_of_use()


async def scroll_mint_canvas(account_id, key, recipient):
    min_left_eth_balance = 0.001

    scroll = Scroll(account_id, key, "scroll", recipient)
    return await scroll.mint_canvas(min_left_eth_balance)


async def scroll_mint_ethereum_year_badge(account_id, key, recipient):
    min_left_eth_balance = 0.0005

    scroll = Scroll(account_id, key, "scroll", recipient)
    return await scroll.mint_ethereum_year_badge(min_left_eth_balance)


async def withdraw_scroll(account_id, key, recipient):
    """
    Withdraw from official bridge
    ______________________________________________________
    all_amount - withdraw from min_percent to max_percent
    """

    min_amount = 0.0012
    max_amount = 0.0012
    decimal = 4

    all_amount = True

    min_percent = 10
    max_percent = 10

    scroll = Scroll(account_id, key, "scroll", recipient)
    await scroll.withdraw(min_amount, max_amount, decimal, all_amount, min_percent, max_percent)


async def bridge_orbiter(account_id, key, recipient):
    """
    Bridge from orbiter
    ______________________________________________________
    from_chain – ethereum, base, polygon_zkevm, arbitrum, optimism, zksync, scroll | Select one
    to_chain – ethereum, base, polygon_zkevm, arbitrum, optimism, zksync, scroll | Select one
    """

    from_chain = "scroll"
    to_chain = "zksync"

    min_amount = 0.002
    max_amount = 0.003
    decimal = 4

    all_amount = False

    min_percent = 5
    max_percent = 10

    orbiter = Orbiter(account_id=account_id, private_key=key, chain=from_chain, recipient=recipient)
    return await orbiter.bridge(to_chain, min_amount, max_amount, decimal, all_amount, min_percent, max_percent,
                                module_cooldown)


async def bridge_layerswap(account_id, key, recipient):
    """
    Bridge from Layerswap
    ______________________________________________________
    from_chain - Choose any chain: ethereum, arbitrum, optimism, avalanche, polygon, base, scroll
    to_chain - Choose any chain: ethereum, arbitrum, optimism, avalanche, polygon, base, scroll

    make_withdraw - True, if need withdraw after deposit

    all_amount - deposit from min_percent to max_percent
    """

    from_chain = "zksync"
    to_chain = "scroll"

    min_amount = 0.01
    max_amount = 0.011

    decimal = 5

    all_amount = False

    min_percent = 5
    max_percent = 5

    layerswap = LayerSwap(account_id=account_id, private_key=key, chain=from_chain, recipient=recipient)
    return await layerswap.bridge(
        from_chain, to_chain, min_amount, max_amount, decimal, all_amount, min_percent, max_percent, module_cooldown
    )


async def bridge_layerswap2(account_id, key, recipient):
    """
    Bridge from Layerswap
    ______________________________________________________
    from_chain - Choose any chain: ethereum, arbitrum, optimism, avalanche, polygon, base, scroll
    to_chain - Choose any chain: ethereum, arbitrum, optimism, avalanche, polygon, base, scroll

    make_withdraw - True, if need withdraw after deposit

    all_amount - deposit from min_percent to max_percent
    """

    from_chain = "scroll"
    to_chain = "zksync"

    min_amount = 0.002
    max_amount = 0.003

    decimal = 5

    all_amount = False

    min_percent = 5
    max_percent = 5

    layerswap = LayerSwap(account_id=account_id, private_key=key, chain=from_chain, recipient=recipient)
    return await layerswap.bridge(
        from_chain, to_chain, min_amount, max_amount, decimal, all_amount, min_percent, max_percent, module_cooldown
    )


async def bridge_nitro(account_id, key, recipient):
    """
    Bridge from nitro
    ______________________________________________________
    from_chain – ethereum, arbitrum, optimism, zksync, scroll, base, linea | Select one
    to_chain – ethereum, arbitrum, optimism, zksync, scroll, base, linea | Select one
    """

    from_chain = "zksync"
    to_chain = "scroll"

    min_amount = 0.004
    max_amount = 0.006
    decimal = 4

    all_amount = False

    min_percent = 5
    max_percent = 10

    nitro = Nitro(account_id=account_id, private_key=key, chain=from_chain, recipient=recipient)
    return await nitro.bridge(to_chain, min_amount, max_amount, decimal, all_amount, min_percent, max_percent,
                              module_cooldown)


async def bridge_nitro1(account_id, key, recipient):
    """
    Bridge from nitro
    ______________________________________________________
    from_chain – ethereum, arbitrum, optimism, zksync, scroll, base, linea | Select one
    to_chain – ethereum, arbitrum, optimism, zksync, scroll, base, linea | Select one
    """

    from_chain = "scroll"
    to_chain = "zksync"

    min_amount = 0.002
    max_amount = 0.003
    decimal = 4

    all_amount = False

    min_percent = 5
    max_percent = 10

    nitro = Nitro(account_id=account_id, private_key=key, chain=from_chain, recipient=recipient)
    return await nitro.bridge(to_chain, min_amount, max_amount, decimal, all_amount, min_percent, max_percent,
                              module_cooldown)


async def wrap_eth(account_id, key, recipient):
    """
    Wrap ETH
    ______________________________________________________
    all_amount - wrap from min_percent to max_percent
    """

    min_amount = 0.001
    max_amount = 0.002
    decimal = 4

    all_amount = True

    min_percent = 5
    max_percent = 10

    scroll = Scroll(account_id, key, "scroll", recipient)
    await scroll.wrap_eth(min_amount, max_amount, decimal, all_amount, min_percent, max_percent)


async def unwrap_eth(account_id, key, recipient):
    """
    Unwrap ETH
    ______________________________________________________
    all_amount - unwrap from min_percent to max_percent
    """

    min_amount = 0.001
    max_amount = 0.002
    decimal = 4

    all_amount = True

    min_percent = 100
    max_percent = 100

    scroll = Scroll(account_id, key, "scroll", recipient)
    await scroll.unwrap_eth(min_amount, max_amount, decimal, all_amount, min_percent, max_percent)


async def swap_skydrome(account_id, key, recipient):
    """
    Make swap on Skydrome
    ______________________________________________________
    from_token – Choose SOURCE token ETH, USDC | Select one
    to_token – Choose DESTINATION token ETH, USDC | Select one

    Disclaimer - You can swap only ETH to any token or any token to ETH!
    ______________________________________________________
    all_amount - swap from min_percent to max_percent
    """

    from_token = "USDC"
    to_token = "ETH"

    min_amount = 0.0001
    max_amount = 0.0002
    decimal = 6
    slippage = 1

    all_amount = True

    min_percent = 100
    max_percent = 100

    skydrome = Skydrome(account_id, key, recipient)
    return await skydrome.swap(
        from_token, to_token, min_amount, max_amount, decimal, slippage, all_amount, min_percent, max_percent
    )


async def swap_kyberswap(account_id, key, recipient):
    """
    Make swap on Kyberswap
    ______________________________________________________
    from_token – Choose SOURCE token ETH, USDC | Select one
    to_token – Choose DESTINATION token ETH, USDC | Select one

    Disclaimer - You can swap only ETH to any token or any token to ETH!
    ______________________________________________________
    all_amount - swap from min_percent to max_percent
    """

    from_token = "ETH"
    to_token = "USDC"

    min_amount = 0.001
    max_amount = 0.005
    decimal = 6
    slippage = 1

    all_amount = True

    min_percent = 30
    max_percent = 60

    kyberswap = KyberSwap(account_id, key, recipient)
    return await kyberswap.swap(
        from_token, to_token, min_amount, max_amount, decimal, slippage, all_amount, min_percent, max_percent
    )


async def swap_openocean(account_id, key, recipient):
    """
    Make swap on OpenOcean
    ______________________________________________________
    from_token – Choose SOURCE token ETH, USDC | Select one
    to_token – Choose DESTINATION token ETH, USDC | Select one

    Disclaimer - You can swap only ETH to any token or any token to ETH!
    ______________________________________________________
    all_amount - swap from min_percent to max_percent
    """

    from_token = "ETH"
    to_token = "USDC"

    min_amount = 0.001
    max_amount = 0.005
    decimal = 6
    slippage = 1

    all_amount = True

    min_percent = 30
    max_percent = 60

    openocean = OpenOcean(account_id, key, recipient)
    return await openocean.swap(
        from_token, to_token, min_amount, max_amount, decimal, slippage, all_amount, min_percent, max_percent
    )


async def swap_sushiswap(account_id, key, recipient):
    """
    Make swap on Sushiswap
    ______________________________________________________
    from_token – Choose SOURCE token ETH, USDC | Select one
    to_token – Choose DESTINATION token ETH, USDC | Select one

    Disclaimer - You can swap only ETH to any token or any token to ETH!
    ______________________________________________________
    all_amount - swap from min_percent to max_percent
    """

    from_token = "ETH"
    to_token = "USDC"

    min_amount = 0.001
    max_amount = 0.005
    decimal = 5
    slippage = 1

    all_amount = True

    min_percent = 30
    max_percent = 60

    sushiswap = SushiSwap(account_id, key, recipient)
    return await sushiswap.swap(
        from_token, to_token, min_amount, max_amount, decimal, slippage, all_amount, min_percent, max_percent
    )


async def swap_ambient_finance(account_id, key, recipient):
    """
    Make swap on Ambient Finance
    ______________________________________________________
    from_token – Choose SOURCE token ETH, USDC | Select one
    to_token – Choose DESTINATION token ETH, USDC | Select one

    Disclaimer - You can swap only ETH to any token or any token to ETH!
    ______________________________________________________
    all_amount - swap from min_percent to max_percent
    """

    from_token = "WRSETH"
    to_token = "ETH"

    min_amount = 0.0007
    max_amount = 0.001
    decimal = 6
    slippage = 2

    all_amount = True

    min_percent = 100
    max_percent = 100

    ambient_finance = AmbientFinance(account_id, key, recipient)
    return await ambient_finance.swap(
        from_token, to_token, min_amount, max_amount, decimal, slippage, all_amount, min_percent, max_percent
    )


async def swap_zebra(account_id, key, recipient):
    """
    Make swap on Zebra
    ______________________________________________________
    from_token – Choose SOURCE token ETH, USDC | Select one
    to_token – Choose DESTINATION token ETH, USDC | Select one

    Disclaimer - You can swap only ETH to any token or any token to ETH!
    ______________________________________________________
    all_amount - swap from min_percent to max_percent
    """

    from_token = "USDC"
    to_token = "ETH"

    min_amount = 0.0001
    max_amount = 0.0002
    decimal = 6
    slippage = 1

    all_amount = True

    min_percent = 100
    max_percent = 100

    zebra = Zebra(account_id, key, recipient)
    return await zebra.swap(
        from_token, to_token, min_amount, max_amount, decimal, slippage, all_amount, min_percent, max_percent
    )


async def swap_syncswap(account_id, key, recipient):
    """
    Make swap on SyncSwap

    from_token – Choose SOURCE token ETH, USDC | Select one
    to_token – Choose DESTINATION token ETH, USDC | Select one

    Disclaimer – Don't use stable coin in from and to token | from_token USDC to_token USDT DON'T WORK!!!
    ______________________________________________________
    all_amount - swap from min_percent to max_percent
    """

    from_token = "USDC"
    to_token = "ETH"

    min_amount = 1
    max_amount = 2
    decimal = 6
    slippage = 1

    all_amount = True

    min_percent = 100
    max_percent = 100

    syncswap = SyncSwap(account_id, key, recipient)
    return await syncswap.swap(
        from_token, to_token, min_amount, max_amount, decimal, slippage, all_amount, min_percent, max_percent
    )


async def swap_xyswap(account_id, key, recipient):
    """
    Make swap on XYSwap
    ______________________________________________________
    from_token – Choose SOURCE token ETH, WETH, USDC | Select one
    to_token – Choose DESTINATION token ETH, WETH, USDC | Select one

    Disclaimer - If you use True for use_fee, you support me 1% of the transaction amount
    ______________________________________________________
    all_amount - swap from min_percent to max_percent
    """

    from_token = "USDC"
    to_token = "ETH"

    min_amount = 0.0001
    max_amount = 0.0001
    decimal = 6
    slippage = 3

    all_amount = True

    min_percent = 100
    max_percent = 100

    xyswap = XYSwap(account_id, key, recipient)
    return await xyswap.swap(
        from_token, to_token, min_amount, max_amount, decimal, slippage, all_amount, min_percent, max_percent
    )


async def swap_odos(account_id, key, recipient):
    """
    Make swap on Odos
    ______________________________________________________
    from_token – Choose SOURCE token ETH, WETH, USDC | Select one
    to_token – Choose DESTINATION token ETH, WETH, USDC | Select one
    ______________________________________________________
    all_amount - swap from min_percent to max_percent
    """

    from_token = "ETH"
    to_token = "USDC"

    min_amount = 0.001
    max_amount = 0.002
    decimal = 4
    slippage = 2

    all_amount = True

    min_percent = 30
    max_percent = 50

    odos = Odos(account_id, key, recipient)
    return await odos.swap(
        from_token, to_token, min_amount, max_amount, decimal, slippage, all_amount, min_percent, max_percent
    )


async def deposit_layerbank(account_id, key, recipient):
    """
    Make deposit on LayerBank
    ______________________________________________________
    make_withdraw - True, if need withdraw after deposit

    all_amount - deposit from min_percent to max_percent
    """
    min_amount = 0.0001
    max_amount = 0.0002
    decimal = 5

    sleep_from = 5
    sleep_to = 24

    make_withdraw = False

    all_amount = True

    min_percent = 30
    max_percent = 60

    layerbank = LayerBank(account_id, key, recipient)
    return await layerbank.deposit(
        min_amount, max_amount, decimal, sleep_from, sleep_to, make_withdraw, all_amount, min_percent, max_percent,
        module_cooldown
    )


async def stake_kelp_and_deposit_ambient_finance(account_id, key, recipient):
    # не запускаем сценарий для аккаунтов с балансом меньше
    min_eth_balance = 0.003

    # не запускаем сценарий для аккаунта, у которого депозит больше
    max_deposit_amount = 0.005

    # после запуска сценария на аккаунте должно остаться не меньше
    min_left_eth_balance = 0.0045
    max_left_eth_balance = 0.0055

    decimal = 5

    kelp_min_amount = 0.0001
    kelp_max_amount = 0.0002
    # all_amount - deposit from min_percent to max_percent of ETH
    kelp_all_amount = True
    kelp_min_percent = 38
    kelp_max_percent = 41

    kelp_module_cooldown = 60 * 24

    ambient_min_amount = 0.0001
    ambient_max_amount = 0.0002
    # all_amount - deposit from min_percent to max_percent of wrsETH
    ambient_all_amount = True
    ambient_min_percent = 100
    ambient_max_percent = 100
    # Percentage width of the range around current pool price (1 = 1%, 0.5 = 0.5%)
    # Tighter ranges accumulate rewards at faster rates, but are more likely to suffer divergence losses.
    ambient_range_width = 0.5

    scenario = Scenarios(account_id, key, recipient)
    return await scenario.stake_eth_and_deposit_wrseth(
        decimal,
        kelp_min_amount,
        kelp_max_amount,
        kelp_all_amount,
        kelp_min_percent,
        kelp_max_percent,
        ambient_min_amount,
        ambient_max_amount,
        ambient_all_amount,
        ambient_min_percent,
        ambient_max_percent,
        ambient_range_width,
        min_left_eth_balance,
        max_left_eth_balance,
        max_deposit_amount,
        kelp_module_cooldown,
        min_eth_balance,
    )


async def adjust_ambient_wrseth_eth_position_scenario(account_id, key, recipient):
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
    min_deposit_percent = 91
    max_deposit_percent = 100

    # сколько раз повторяем депозит с уменьшением кол-ва баланса
    ambient_max_deposit_attempts = 100

    # минимальный размер ордера продажи покупки wrseth
    min_trade_amount_wrseth_wei = 5000000000000000

    scenario = Scenarios(account_id, key, recipient)
    return await scenario.adjust_ambient_wrseth_eth_position(
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
        ambient_max_deposit_attempts,
        min_trade_amount_wrseth_wei)


async def mint_ambient_providoor_badge(account_id, key, recipient):
    # минимальный размер позиции на амбиенте (с учётом скачков курсов рекомедовал бы ставить больше 1000  USD)
    min_deposit_amount_usd = 1150
    max_deposit_amount_usd = 1250

    # сколько минимум должно остаться на аккаунте скролл после минта значка и вывода денег на окекс
    min_eth_balance_after_script = 0.02
    max_eth_balance_after_script = 0.035

    # сколько минимум должно остаться на аккаунте ethereum после депозита в скролл (чтобы потом сделать транзу claim на вывод)
    ethereum_eth_left_balance_min_after_deposit = 0.005

    # сколько аккаунтов можно запускать дополнительно, когда мы упираемся в действие, которое требует ожидание большого времени (например, ожидаем час вывод или депозит)
    max_current_accounts = 48

    # время между действиями для разных аккаунтов
    min_wait_time_before_accounts = 1
    max_wait_time_before_accounts = 1

    min_wait_time_before_iterations = 5
    max_wait_time_before_iterations = 5

    scenario = Scenarios(account_id, key, recipient)
    return await scenario.mint_ambient_providoor_badge(
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
    )


async def deposit_ambient_finance(account_id, key, recipient):
    """
    Make deposit on Ambient Finance to wrsETH/ETH pool
    ______________________________________________________

    all_amount - deposit from min_percent to max_percent of wrsETH
    """
    min_amount = 0.0001
    max_amount = 0.0002
    decimal = 5

    all_amount = True

    min_percent = 100
    max_percent = 100

    # Percentage width of the range around current pool price (1 = 1%, 0.5 = 0.5%)
    # Tighter ranges accumulate rewards at faster rates, but are more likely to suffer divergence losses.
    range_width = 0.5  # 0.25, 0.5, 1, 5, 10

    min_left_eth_balance: float = 0.0045
    max_left_eth_balance: float = 0.0055

    ambient_finance = AmbientFinance(account_id, key, recipient)
    return await ambient_finance.deposit(
        min_amount,
        max_amount,
        decimal,
        all_amount,
        min_percent,
        max_percent,
        range_width,
        min_left_eth_balance,
        max_left_eth_balance
    )


async def reposit_ambient_finance(account_id, key, recipient):
    # Percentage width of the range around current pool price (1 = 1%, 0.5 = 0.5%)
    # Tighter ranges accumulate rewards at faster rates, but are more likely to suffer divergence losses.
    range_width = 1  # 0.25, 0.5, 1, 5, 10

    ambient_finance = AmbientFinance(account_id, key, recipient)
    return await ambient_finance.reposit_outrage_deposits(
        range_width
    )


async def withdrawal_ambient_finance(account_id, key, recipient):
    """
    Make withdraw from Ambient Finance wrsETH/ETH pool
    """

    ambient_finance = AmbientFinance(account_id, key, recipient)
    return await ambient_finance.withdrawal()


async def deposit_aave(account_id, key, recipient):
    """
    Make deposit on Aave
    ______________________________________________________
    make_withdraw - True, if need withdraw after deposit

    all_amount - deposit from min_percent to max_percent
    """

    module_cooldown = 77777

    min_amount = 0.0001
    max_amount = 0.0002
    decimal = 5

    sleep_from = 5
    sleep_to = 24

    make_withdraw = False

    all_amount = True

    min_percent = 85
    max_percent = 90

    aave = Aave(account_id, key, recipient)
    return await aave.deposit(
        min_amount, max_amount, decimal, sleep_from, sleep_to, make_withdraw, all_amount, min_percent, max_percent,
        module_cooldown
    )


async def deposit_rhomarkets(account_id, key, recipient):
    """
    Make deposit on Rhomarkets
    ______________________________________________________
    make_withdraw - True, if need withdraw after deposit

    all_amount - deposit from min_percent to max_percent
    """
    min_amount = 0.0001
    max_amount = 0.0002
    decimal = 5

    sleep_from = 5
    sleep_to = 24

    make_withdraw = False

    all_amount = True

    min_percent = 80
    max_percent = 90

    rhomarkets = Rhomarkets(account_id, key, recipient)
    return await rhomarkets.deposit(
        min_amount, max_amount, decimal, sleep_from, sleep_to, make_withdraw, all_amount, min_percent, max_percent,
        module_cooldown
    )


async def deposit_kelp(account_id, key, recipient):
    """
    Make deposit on Kelp
    ______________________________________________________
    make_withdraw - True, if need withdraw after deposit

    all_amount - deposit from min_percent to max_percent
    """
    min_amount = 0.0001
    max_amount = 0.0002
    decimal = 5

    all_amount = True

    min_percent = 35
    max_percent = 40

    kelp = Kelp(account_id, key, recipient)
    return await kelp.deposit(
        min_amount, max_amount, decimal, all_amount, min_percent, max_percent,
        module_cooldown
    )


async def deposit_compound_finance(account_id, key, recipient):
    """
    Make deposit on Compound Finance
    ______________________________________________________
    make_withdraw - True, if need withdraw after deposit

    all_amount - deposit from min_percent to max_percent
    """
    min_amount = 0.0005
    max_amount = 0.0009
    decimal = 5

    sleep_from = 5
    sleep_to = 24

    make_withdraw = False

    all_amount = True

    min_percent = 30
    max_percent = 50

    compound_finance = CompoundFinance(account_id, key, recipient)
    return await compound_finance.deposit(
        min_amount, max_amount, decimal, sleep_from, sleep_to, make_withdraw, all_amount, min_percent, max_percent,
        module_cooldown
    )


async def mint_zerius(account_id, key, recipient):
    """
    Mint + bridge Zerius NFT
    ______________________________________________________
    chains - list chains for random chain bridge: arbitrum, optimism, polygon, bsc, avalanche
    Disclaimer - The Mint function should be called "mint", to make sure of this, look at the name in Rabby Wallet or in explorer
    """

    chains = ["arbitrum"]

    sleep_from = 10
    sleep_to = 20

    zerius = Zerius(account_id, key, recipient)
    await zerius.bridge(chains, sleep_from, sleep_to)


async def mint_l2pass(account_id, key, recipient):
    """
    Mint L2Pass NFT
    """

    contract = "0x0000049f63ef0d60abe49fdd8bebfa5a68822222"

    l2pass = L2Pass(account_id, key, recipient)
    await l2pass.mint(contract)


async def mint_nft(account_id, key, recipient):
    """
    Mint NFT on NFTS2ME
    ______________________________________________________
    contracts - list NFT contract addresses
    """

    contracts = [""]

    minter = Minter(account_id, key, recipient)
    await minter.mint_nft(contracts)


async def mint_zkstars(account_id, key, recipient):
    """
    Mint ZkStars NFT
    """

    contracts = [
        "0x609c2f307940b8f52190b6d3d3a41c762136884e",
        "0x16c0baa8a2aa77fab8d0aece9b6947ee1b74b943",
        "0xc5471e35533e887f59df7a31f7c162eb98f367f7",
        "0xf861f5927c87bc7c4781817b08151d638de41036",
        "0x954e8ac11c369ef69636239803a36146bf85e61b",
        "0xa576ac0a158ebdcc0445e3465adf50e93dd2cad8",
        "0x17863384c663c5f95e4e52d3601f2ff1919ac1aa",
        "0x4c2656a6d1c0ecac86f5024e60d4f04dbb3d1623",
        "0x4e86532cedf07c7946e238bd32ba141b4ed10c12",
        "0x6b9db0ffcb840c3d9119b4ff00f0795602c96086",
        "0x10d4749bee6a1576ae5e11227bc7f5031ad351e4",
        "0x373148e566e4c4c14f4ed8334aba3a0da645097a",
        "0xdacbac1c25d63b4b2b8bfdbf21c383e3ccff2281",
        "0x2394b22b3925342f3216360b7b8f43402e6a150b",
        "0xf34f431e3fc0ad0d2beb914637b39f1ecf46c1ee",
        "0x6f1e292302dce99e2a4681be4370d349850ac7c2",
        "0xa21fac8b389f1f3717957a6bb7d5ae658122fc82",
        "0x1b499d45e0cc5e5198b8a440f2d949f70e207a5d",
        "0xec9bef17876d67de1f2ec69f9a0e94de647fcc93",
        "0x5e6c493da06221fed0259a49beac09ef750c3de1"
    ]

    mint_min = 1
    mint_max = 1

    mint_all = False

    sleep_from = 5
    sleep_to = 10

    zkkstars = ZkStars(account_id, key, recipient)
    await zkkstars.mint(contracts, mint_min, mint_max, mint_all, sleep_from, sleep_to)


async def mint_citizen(account_id, key, recipient):
    """
    Mint Scroll Citizen NFT
    """

    contracts = [
        "0xc519d9d47c003b6274e20cfe21d58fee1efa7a0e",
        "0x1249e38bb84aa3cbe6f4506a85b6831ef49ed48f",
        "0xcde5e31d0c7348161b76579a6e25b8874de91434",
        "0xd4eac5a09e5e8ac8e94f62e46b5d9e808e577d2e",
        "0x51c8b85aedb821712c7115f36d252018951c4b16",
        "0x6982d37e2bc0de66ce744a65a79c57926f11a947",
        "0xf4647c674e32506809f77cf3236ed8034e817cc9",
        "0x6b4772a613a63cbdb15c767bd604e9f5ecf60fcd",
        "0x4395df30ef87a2c23ab393fe0bf1f2d2ef6eefc1",
        "0x36c9724d98dc3f46676bf213da318e556bcc3d16",
        "0x80151e432f5c6d6c89427bceee6738bcc61e3fa6",
        "0xd4215d6aff866151c2df3ebed8ff0cc084b7d2cf",
        "0xde2fea1c76d1d08b0055b8ae6bc4ce8a31403192",
        "0xbdb2cd55421ecd520a04be90b6dee93689a203de",
        "0x65665e3275e2a122c61f953929ca13c1bb5a593b",
        "0x07e2f41b117b34dda4c7044242e903053a7ea025",
        "0x6de8a54d6771325e53e53e85aaf614392839caff",
        "0x9efd036f4f30d9802d4dc1b7ece292d2ef896883",
        "0x57324f9d28d0b89ec980b0b0c6a432c761faf6b2",
        "0x2ab5a55aac0df0087fb2b352372fe19e84f46041"
    ]

    mint_min = 1
    mint_max = 1

    mint_all = False

    sleep_from = 5
    sleep_to = 10

    citizen = ScrollCitizen(account_id, key, recipient)
    await citizen.mint(contracts, mint_min, mint_max, mint_all, sleep_from, sleep_to)


async def send_message(account_id, key, recipient):
    """
    Send message with L2Telegraph
    ______________________________________________________
    chain - select need chain to send message, you can specify several, one will be selected randomly

    availiable chaines: bsc, optimism, avalanche, arbitrum, polygon, linea, moonbeam, kava, telos, klaytn, gnosis, moonriver
    """
    use_chain = ["gnosis", "moonriver"]

    l2telegraph = L2Telegraph(account_id, key, recipient)
    await l2telegraph.send_message(use_chain)


async def bridge_nft(account_id, key, recipient):
    """
    Make mint NFT and bridge NFT on L2Telegraph
    ______________________________________________________
    chain - select need chain to send message, you can specify several, one will be selected randomly

    availiable chaines: bsc, optimism, avalanche, arbitrum, polygon, linea
    """
    use_chain = ["polygon"]

    sleep_from = 5
    sleep_to = 20

    l2telegraph = L2Telegraph(account_id, key, recipient)
    await l2telegraph.bridge(use_chain, sleep_from, sleep_to)


async def make_transfer(_id, key, recipient):
    """
    Transfer ETH
    """

    min_amount = 0.0001
    max_amount = 0.0002
    decimal = 5

    all_amount = True

    min_percent = 10
    max_percent = 10

    transfer = Transfer(_id, key, recipient)
    await transfer.transfer(min_amount, max_amount, decimal, all_amount, min_percent, max_percent)


async def swap_tokens(account_id, key, recipient):
    """
    SwapTokens module: Automatically swap tokens to ETH
    ______________________________________________________
    use_dex - Choose any dex: syncswap, skydrome, zebra, xyswap
    """

    use_dex = [
        "syncswap", "skydrome", "zebra"
    ]

    use_tokens = ["USDC"]

    sleep_from = 1
    sleep_to = 5

    slippage = 0.1

    min_percent = 100
    max_percent = 100

    swap_tokens = SwapTokens(account_id, key, recipient)
    return await swap_tokens.swap(use_dex, use_tokens, sleep_from, sleep_to, slippage, min_percent, max_percent)


async def swap_multiswap(account_id, key, recipient):
    """
    Multi-Swap module: Automatically performs the specified number of swaps in one of the dexes.
    ______________________________________________________
    use_dex - Choose any dex: syncswap, skydrome, zebra, xyswap, ambient_finance
    quantity_swap - Quantity swaps
    ______________________________________________________
    If back_swap is True, then, if USDC remains, it will be swapped into ETH.
    """

    use_dex = ["syncswap",
               "skydrome",
               "zebra",
               "xyswap",
               "ambient_finance",
               "kyberswap",
               "sushiswap",
               "openocean",
               "odos"]
    dex_max_tx = 2

    min_swap = 1
    max_swap = 1

    sleep_from = 20
    sleep_to = 60

    slippage = 1

    back_swap = True

    min_percent = 20
    max_percent = 60

    # Поставить True, чтобы начать цепочку свапов с USDC->ETH, если есть баланс USDC
    # При False цепочка всегда начинается с ETH->USDC
    first_swap_from_udsc_if_can = True

    multi = Multiswap(account_id, key, recipient)
    return await multi.swap(
        use_dex, sleep_from, sleep_to, min_swap, max_swap, slippage, back_swap, min_percent, max_percent, dex_max_tx,
        first_swap_from_udsc_if_can
    )


async def multibridge(account_id, key, recipient):
    """
    MultriBridge - Makes a bridge from a random network where there is a minimum acceptable balance
    ______________________________________________________
    use_bridge - right now only nitro

    source_chain – ethereum, arbitrum, optimism, zksync, scroll, base, linea | Select one or more
    destination_chain - ethereum, arbitrum, optimism, zksync, scroll, base, linea | Select one

    min_chain_balance - minimum acceptable balance for bridge
    """

    use_bridge = "nitro"

    source_chain = ["optimism", "zksync", "base", "linea"]
    destination_chain = "scroll"

    min_amount = 0.005
    max_amount = 0.006
    decimal = 4

    all_amount = False

    min_percent = 5
    max_percent = 10

    min_chain_balance = 0.006

    multibridge = Multibridge(account_id=account_id, private_key=key, recipient=recipient)
    await multibridge.bridge(use_bridge, source_chain, destination_chain, min_amount, max_amount, decimal, all_amount,
                             min_percent, max_percent, min_chain_balance)


async def multilanding(account_id, key, recipient):
    """
    MultiLanding - Makes a deposit/withdrawal to/from random DEXs
    """

    use_dex = ["aave", "layerbank", "compoundfinance"]
    min_amount = 0.005
    max_amount = 0.006
    decimal = 4

    sleep_from = 300
    sleep_to = 600

    all_amount = True

    min_percent = 80
    max_percent = 90

    deposit_cooldown = 8888888
    make_withdrawal = False
    withdrawal_cooldown_min = 60 * 60 * 25 * 3
    withdrawal_cooldown_max = 60 * 60 * 25 * 15

    max_dex = 1

    multilanding = Multilanding(account_id=account_id, private_key=key, recipient=recipient)
    await multilanding.deposit(use_dex,
                               min_amount,
                               max_amount,
                               decimal,
                               sleep_from,
                               sleep_to,
                               make_withdrawal,
                               withdrawal_cooldown_min,
                               withdrawal_cooldown_max,
                               all_amount,
                               min_percent,
                               max_percent,
                               deposit_cooldown,
                               max_dex)


async def custom_routes(account_id, key, recipient):
    """
    BRIDGE:
        – deposit_scroll
        – withdraw_scroll
        – bridge_orbiter
        – bridge_layerswap
        – bridge_nitro
    WRAP:
        – wrap_eth
        – unwrap_eth
    DEX:
        – swap_skydrome
        – swap_syncswap
        – swap_zebra
        – swap_xyswap
    LIQUIDITY:
    LANDING:
        – depost_layerbank
        – withdraw_layerbank
        – deposit_aave
        – withdraw_aave
    NFT/DOMAIN:
        – mint_zerius
        – mint_zkstars
        – create_omnisea
        – mint_nft
        – mint_l2pass
    ANOTHER:
        – swap_multiswap
        – multibridge
        – swap_tokens
        – send_mail (Dmail)
        – create_safe
        – rubyscore_vote
        – deploy_contract
    ______________________________________________________
    Disclaimer - You can add modules to [] to select random ones,
    example [module_1, module_2, [module_3, module_4], module 5]
    The script will start with module 1, 2, 5 and select a random one from module 3 and 4

    You can also specify None in [], and if None is selected by random, this module will be skipped

    You can also specify () to perform the desired action a certain number of times
    example (send_mail, 1, 10) run this module 1 to 10 times
    """

    use_modules = [
        # create_omnisea,
        # [create_omnisea, mint_zerius, None],
        # (create_omnisea, 1, 3),
        # bridge_nitro,
        # bridge_layerswap,
        # bridge_layerswap2,
        # bridge_nitro1,
        # bridge_orbiter,
        # withdraw_layerbank,
        # withdraw_aave,
        # deposit_layerbank,
        # withdraw_compound_finance,
        # withdraw_rhomarkets,
        # stake_kelp_and_deposit_ambient_finance,
        withdrawal_ambient_finance,
        adjust_ambient_wrseth_eth_position_scenario
    ]

    sleep_from = 10
    sleep_to = 20

    random_module = False

    routes = Routes(account_id, key, recipient)
    return await routes.start(use_modules, sleep_from, sleep_to, random_module)


#########################################
########### NO NEED TO CHANGE ###########
#########################################

async def withdraw_layerbank(account_id, key, recipient):
    layerbank = LayerBank(account_id, key, recipient)
    return await layerbank.withdraw()


async def withdraw_aave(account_id, key, recipient):
    aave = Aave(account_id, key, recipient)
    return await aave.withdraw()


async def withdraw_rhomarkets(account_id, key, recipient):
    rhomarkets = Rhomarkets(account_id, key, recipient)
    return await rhomarkets.withdraw()


async def withdraw_compound_finance(account_id, key, recipient):
    compound_finance = CompoundFinance(account_id, key, recipient)
    return await compound_finance.withdraw()


async def send_mail(account_id, key, recipient):
    dmail = Dmail(account_id, key, recipient)
    await dmail.send_mail()


async def create_omnisea(account_id, key, recipient):
    omnisea = Omnisea(account_id, key, recipient)
    await omnisea.create()


async def create_safe(account_id, key, recipient):
    gnosis_safe = GnosisSafe(account_id, key, recipient)
    return await gnosis_safe.create_safe(module_cooldown)


async def deploy_contract(account_id, key, recipient):
    deployer = Deployer(account_id, key, recipient)
    await deployer.deploy_token()


async def rubyscore_vote(account_id, key, recipient):
    rubyscore = RubyScore(account_id, key, recipient)
    await rubyscore.vote()


async def nft_origins(account_id, key, recipient):
    nft = NftOrigins(account_id, key, recipient)
    await nft.mint()


def get_tx_count():
    asyncio.run(check_tx())
