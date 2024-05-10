import random
import sys
import os
import signal
from typing import Union

import questionary
from loguru import logger
from questionary import Choice

from config import ACCOUNTS, RECIPIENTS
from settings import (
    RANDOM_WALLET,
    SLEEP_TO,
    SLEEP_FROM,
    QUANTITY_THREADS,
    THREAD_SLEEP_FROM,
    THREAD_SLEEP_TO,
    REMOVE_WALLET
)
from modules_settings import *
from utils.helpers import remove_wallet
from utils.sleeping import sleep
from eth_account import Account as EthereumAccount

def signal_handler(sig, frame):
    print('Ctrl+C!')
    asyncio.get_event_loop().stop() 
    sys.exit(0)

def get_module():
    result = questionary.select(
        "Select a method to get started",
        choices=[
            Choice("1) Deposit to Scroll", deposit_scroll),
            Choice("2) Withdraw from Scroll", withdraw_scroll),
            Choice("3) Bridge Orbiter", bridge_orbiter),
            Choice("4) Bridge Layerswap", bridge_layerswap),
            Choice("5) Bridge Nitro", bridge_nitro),
            Choice("6) Wrap ETH", wrap_eth),
            Choice("7) Unwrap ETH", unwrap_eth),
            Choice("8) Swap on Skydrome", swap_skydrome),
            Choice("9) Swap on Zebra", swap_zebra),
            Choice("10) Swap on SyncSwap", swap_syncswap),
            Choice("11) Swap on XYSwap", swap_xyswap),
            Choice("12) Deposit LayerBank", deposit_layerbank),
            Choice("13) Deposit Aave", deposit_aave),
            Choice("14) Withdraw LayerBank", withdraw_layerbank),
            Choice("15) Withdraw Aave", withdraw_aave),
            Choice("16) Mint and Bridge Zerius NFT", mint_zerius),
            Choice("17) Mint L2Pass NFT", mint_l2pass),
            Choice("18) Mint ZkStars NFT", mint_zkstars),
            Choice("19) Mint Scroll Citizen NFT", mint_citizen),
            Choice("20) Create NFT collection on Omnisea", create_omnisea),
            Choice("21) RubyScore Vote", rubyscore_vote),
            Choice("22) Send message L2Telegraph", send_message),
            Choice("23) Mint and bridge NFT L2Telegraph", bridge_nft),
            Choice("24) Mint NFT on NFTS2ME", mint_nft),
            Choice("25) Mint Scroll Origins NFT", nft_origins),
            Choice("26) Dmail send email", send_mail),
            Choice("27) Create gnosis safe", create_safe),
            Choice("28) Deploy contract", deploy_contract),
            Choice("29) Swap tokens to ETH", swap_tokens),
            Choice("30) Use MultiSwap", swap_multiswap),
            Choice("31) Use MultiBridge", multibridge),
            Choice("32) Use custom routes", custom_routes),
            Choice("33) Make transfer", make_transfer),
            Choice("34) Check transaction count", "tx_checker"),
            Choice("35) Deposit Compound Finance", deposit_compound_finance),
            Choice("36) Withdraw Compound Finance", withdraw_compound_finance),
            Choice("37) Swap Ambient Finance", swap_ambient_finance),
            Choice("38) Exit", "exit"),
        ],
        qmark="⚙️ ",
        pointer="✅ "
    ).ask()
    if result == "exit":
        # https://etherscan.io/tx/0xee7f7c6181df7611e3373899775778444577a8ee4556b678734599ce296fddd3
        # похоже мы единственные кто донатил автору
        sys.exit()
    return result

def get_wallets(use_recipients: bool = False):
    if use_recipients:
        account_with_recipients = dict(zip(ACCOUNTS, RECIPIENTS))

        wallets = [
            {
                "id": _id,
                "key": key,
                "recipient": account_with_recipients[key],
            } for _id, key in enumerate(account_with_recipients, start=1)
        ]
    else:
        wallets = [
            {
                "id": _id,
                "key": key,
            } for _id, key in enumerate(ACCOUNTS, start=1)
        ]

    return wallets

async def run_module(module, account_id, key, recipient: Union[str, None] = None):
    try:
        result = await module(account_id, key, recipient)
    except Exception as e:
        result = False
        logger.error(e)

    if REMOVE_WALLET:
        remove_wallet(key)

    if result is not False:
        await sleep(SLEEP_FROM, SLEEP_TO)

async def main(module):
    signal.signal(signal.SIGINT, signal_handler)
    
    if module in [make_transfer]:
        wallets = get_wallets(True)
    else:
        wallets = get_wallets()

    if os.path.exists('wl.txt'):
        wallet_addresses = {EthereumAccount.from_key(wallet['key']).address.lower(): wallet for wallet in wallets}
        existing_addresses = set()

        with open('wl.txt', 'r') as file:
            existing_addresses = {line.strip().lower() for line in file.readlines()}

        filtered_wallets = [wallet for address, wallet in wallet_addresses.items() if address in existing_addresses]
        wallets = filtered_wallets

    if RANDOM_WALLET:
        random.shuffle(wallets)

    sem = asyncio.Semaphore(QUANTITY_THREADS)

    async def _worker(module, account_id, key, recipient):
        async with sem:
            await run_module(module, account_id, key, recipient)

    tasks = []
    for _, account in enumerate(wallets, start=1):
        task = asyncio.create_task(_worker(module, account.get("id"), account.get("key"), account.get("recipient", None)))
        tasks.append(task)

    await asyncio.gather(*tasks)

if __name__ == '__main__':
    logger.add("logging.log")

    module = get_module()
    if module == "tx_checker":
        get_tx_count()
    else:
        asyncio.run(main(module))
