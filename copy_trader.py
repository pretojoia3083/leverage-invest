"""
LEVERAGE INVEST - Copy Trader v2
Copia trades da conta Demo para a Real automaticamente.
Um terminal MT5, alterna entre contas.
"""

import MetaTrader5 as mt5
import time
import json
import logging
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(SCRIPT_DIR, 'copy_trade.log'), encoding='utf-8'),
    ]
)
log = logging.getLogger('CopyTrade')

MT5_PATH = r"C:\Program Files\Vantage International MT5\terminal64.exe"

MASTER_LOGIN = 26006210
MASTER_PASS = "Michelle82@#"
MASTER_SERVER = "VantageMarkets-Demo"

FOLLOWER_LOGIN = 29267317
FOLLOWER_PASS = "Michelle82@#"
FOLLOWER_SERVER = "Cent ECN VantageMarkets-Live 5"

LOT_MULT = 1.0
MAX_LOT = 1.0
MIN_LOT = 0.01
INTERVAL = 10


def init():
    if not mt5.initialize(path=MT5_PATH, timeout=30000):
        log.error("MT5 init: %s", mt5.last_error())
        return False
    return True


def do_login(login, password, server):
    for i in range(3):
        if mt5.login(login, password, server, timeout=60000):
            return True
        log.warning("Login %s falhou tentativa %d: %s", login, i + 1, mt5.last_error())
        time.sleep(5)
    return False


def get_positions_no_magic():
    positions = mt5.positions_get()
    if not positions:
        return {}
    result = {}
    for p in positions:
        result[str(p.ticket)] = {
            "ticket": str(p.ticket),
            "symbol": p.symbol,
            "type": "buy" if p.type == mt5.POSITION_TYPE_BUY else "sell",
            "volume": p.volume,
            "sl": p.sl,
            "tp": p.tp,
            "profit": p.profit,
            "comment": p.comment,
        }
    return result


def open_trade(symbol, order_type, volume, sl, tp):
    for attempt in range(3):
        info = mt5.symbol_info(symbol)
        if info is None:
            time.sleep(1)
            continue

        price = info.ask if order_type == "buy" else info.bid
        if price <= 0:
            time.sleep(1)
            continue

        step = info.volume_step
        min_vol = info.volume_min
        max_vol = info.volume_max

        if step > 0:
            volume = max(min_vol, round(volume / step) * step)
        volume = min(volume, max_vol)

        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY if order_type == "buy" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "deviation": 30,
            "comment": "COPY",
        }
        if sl > 0:
            req["sl"] = sl
        if tp > 0:
            req["tp"] = tp

        result = mt5.order_send(req)
        if result and result.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED):
            log.info("ABERTO: %s %s %.2f lotes @ %.2f", symbol, order_type.upper(), volume, price)
            return True

        log.warning("Tentativa %d falhou: %s %s", attempt + 1, result.retcode if result else "None", result.comment if result else "")
        time.sleep(2)
    return False


def close_trade_by_ticket(ticket):
    pos = mt5.positions_get(ticket=ticket)
    if not pos:
        return False
    p = pos[0]
    close_type = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
    info = mt5.symbol_info(p.symbol)
    price = info.bid if p.type == mt5.POSITION_TYPE_BUY else info.ask

    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": ticket,
        "symbol": p.symbol,
        "volume": p.volume,
        "type": close_type,
        "price": price,
        "deviation": 30,
        "comment": "COPY_CLOSE",
    }
    result = mt5.order_send(req)
    return result and result.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED)


def close_by_symbol_type(symbol, order_type):
    positions = mt5.positions_get()
    if not positions:
        return False
    for p in positions:
        pos_type = "buy" if p.type == mt5.POSITION_TYPE_BUY else "sell"
        if p.symbol == symbol and pos_type == order_type:
            return close_trade_by_ticket(p.ticket)
    return False


def run():
    if not init():
        return

    log.info("=" * 55)
    log.info("LEVERAGE INVEST - Copy Trader v2")
    log.info("Master (Demo): %s -> Follower (Real): %s", MASTER_LOGIN, FOLLOWER_LOGIN)
    log.info("Intervalo: %ds | Mult: %sx", INTERVAL, LOT_MULT)
    log.info("=" * 55)

    copied = {}
    stats = {"copies": 0, "closes": 0, "errors": 0}

    while True:
        try:
            if not do_login(MASTER_LOGIN, MASTER_PASS, MASTER_SERVER):
                log.warning("Demo offline")
                time.sleep(INTERVAL)
                continue

            master_positions = get_positions_no_magic()
            master_info = mt5.account_info()
            log.info("DEMO | $%.2f | %d posicoes",
                     master_info.balance if master_info else 0, len(master_positions))

            if not do_login(FOLLOWER_LOGIN, FOLLOWER_PASS, FOLLOWER_SERVER):
                log.warning("Real offline")
                time.sleep(INTERVAL)
                continue

            follower_info = mt5.account_info()
            log.info("REAL | $%.2f", follower_info.balance if follower_info else 0)

            master_keys = set(master_positions.keys())

            for ticket, mp in master_positions.items():
                key = f"{mp['symbol']}_{mp['type']}"
                if key in copied:
                    continue

                lot = mp["volume"] * LOT_MULT
                lot = max(MIN_LOT, min(lot, MAX_LOT))

                log.info("Copiando: %s %s %.2f lotes", mp["symbol"], mp["type"].upper(), lot)
                if open_trade(mp["symbol"], mp["type"], lot, mp["sl"], mp["tp"]):
                    copied[key] = mp
                    stats["copies"] += 1
                else:
                    stats["errors"] += 1

            for key in list(copied.keys()):
                if key not in master_keys:
                    parts = key.split("_")
                    symbol = parts[0]
                    order_type = parts[1]
                    log.info("Fechando: %s %s (master fechou)", symbol, order_type.upper())
                    if close_by_symbol_type(symbol, order_type):
                        del copied[key]
                        stats["closes"] += 1
                    else:
                        log.warning("Nao conseguiu fechar %s %s", symbol, order_type)

            stats["cycles"] = stats.get("cycles", 0) + 1
            if stats["cycles"] % 10 == 0:
                log.info("Stats: copias=%d fechamentos=%d erros=%d",
                         stats["copies"], stats["closes"], stats["errors"])

        except KeyboardInterrupt:
            log.info("Interrompido")
            break
        except Exception as e:
            log.error("Erro: %s", e)
            stats["errors"] += 1

        time.sleep(INTERVAL)

    mt5.shutdown()
    log.info("Encerrado | copias=%d fechamentos=%d erros=%d",
             stats["copies"], stats["closes"], stats["errors"])


if __name__ == "__main__":
    run()
