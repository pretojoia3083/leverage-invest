"""
LEVERAGE INVEST - MT5 Monitor + Copy Trader
Le trades da conta demo e copia para conta real automaticamente.

Conta demo: PipScalperEA rodando
Conta real: receiving copies

Uma terminal MT5, duas contas, copia automatica.
"""

import MetaTrader5 as mt5
from MetaTrader5 import (
    TRADE_ACTION_DEAL, ORDER_TYPE_BUY, ORDER_TYPE_SELL,
    TRADE_RETCODE_DONE, TRADE_RETCODE_PLACED,
    SYMBOL_ASK, SYMBOL_BID, SYMBOL_VOLUME_MIN, SYMBOL_VOLUME_MAX, SYMBOL_VOLUME_STEP,
    POSITION_TYPE_BUY, POSITION_TYPE_SELL,
)
import requests
import time
import json
import logging
import sys
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, 'mt5_monitor.log')
STATE_FILE = os.path.join(SCRIPT_DIR, 'copy_state.json')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
    ]
)
log = logging.getLogger('MT5Monitor')

API_BASE = "https://leverage-invest.onrender.com"
MT5_PATH = r"C:\Program Files\Vantage International MT5\terminal64.exe"
SYNC_INTERVAL = 10

MASTER_LOGIN = 26006210
MASTER_PASS = "Michelle82@#"
MASTER_SERVER = "VantageMarkets-Demo"

FOLLOWER_LOGIN = 29267317
FOLLOWER_PASS = "Michelle82@#"
FOLLOWER_SERVER = "Cent ECN VantageMarkets-Live 5"

LOT_MULTIPLIER = 1.0
MAX_LOT = 1.0
MIN_LOT = 0.01
COPY_MAGIC = 999999


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"copied_tickets": [], "last_sync": None}


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)


class MT5CopyTrader:
    def __init__(self):
        self.running = True
        self.stats = {"syncs": 0, "copies": 0, "closes": 0, "errors": 0}
        self.state = load_state()

    def connect(self):
        if not mt5.initialize(path=MT5_PATH, timeout=15000):
            log.error("MT5 falhou: %s", mt5.last_error())
            return False
        log.info("MT5 conectado")
        return True

    def login_as(self, login, password, server):
        if not mt5.login(login, password, server):
            err = mt5.last_error()
            log.warning("Falha login %s: %s", login, err)
            return False
        return True

    def get_positions(self):
        positions = mt5.positions_get()
        if not positions:
            return []
        result = []
        for pos in positions:
            result.append({
                "ticket": pos.ticket,
                "symbol": pos.symbol,
                "type": "buy" if pos.type == mt5.ORDER_TYPE_BUY else "sell",
                "volume": pos.volume,
                "open_price": pos.price_open,
                "sl": pos.sl,
                "tp": pos.tp,
                "profit": pos.profit,
                "time": pos.time,
            })
        return result

    def open_trade(self, symbol, order_type, volume, sl, tp):
        price = SymbolInfoDouble(symbol, SYMBOL_ASK) if order_type == "buy" else SymbolInfoDouble(symbol, SYMBOL_BID)

        min_vol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN)
        max_vol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX)
        step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP)

        if step > 0:
            volume = max(min_vol, round(volume / step) * step)
        volume = min(volume, max_vol)

        req = {
            "action": TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": ORDER_TYPE_BUY if order_type == "buy" else ORDER_TYPE_SELL,
            "price": price,
            "deviation": 30,
            "magic": COPY_MAGIC,
            "comment": "COPY",
        }

        if sl > 0:
            req["sl"] = sl
        if tp > 0:
            req["tp"] = tp

        result = order_send(req)
        return result

    def close_position(self, ticket):
        pos = mt5.positions_get(ticket=ticket)
        if not pos:
            return None

        pos = pos[0]
        symbol = pos.symbol
        volume = pos.volume
        pos_type = pos.type

        close_type = ORDER_TYPE_SELL if pos_type == POSITION_TYPE_BUY else ORDER_TYPE_BUY
        price = SymbolInfoDouble(symbol, SYMBOL_BID) if pos_type == POSITION_TYPE_BUY else SymbolInfoDouble(symbol, SYMBOL_ASK)

        req = {
            "action": TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": symbol,
            "volume": volume,
            "type": close_type,
            "price": price,
            "deviation": 30,
            "magic": COPY_MAGIC,
            "comment": "COPY_CLOSE",
        }

        return order_send(req)

    def sync_to_api(self, account_info, positions):
        payload = {
            "account_number": str(account_info.login),
            "server": account_info.server,
            "balance": account_info.balance,
            "equity": account_info.equity,
            "profit_today": account_info.profit,
            "profit_week": 0.0,
            "trades": [{
                "ticket": str(p["ticket"]),
                "symbol": p["symbol"],
                "order_type": p["type"],
                "volume": p["volume"],
                "open_price": p["open_price"],
                "close_price": None,
                "stop_loss": p["sl"],
                "take_profit": p["tp"],
                "profit": p["profit"],
                "status": "open",
                "opened_at": datetime.fromtimestamp(p["time"]).isoformat() if p["time"] else None,
            } for p in positions],
        }
        try:
            r = requests.post(f"{API_BASE}/api/mt5/report", json=payload, timeout=60)
            return r.status_code == 200
        except Exception as e:
            log.error("API erro: %s", e)
            return False

    def copy_cycle(self):
        # 1. Ler trades da conta demo (master)
        if not self.login_as(MASTER_LOGIN, MASTER_PASS, MASTER_SERVER):
            log.warning("Nao conseguiu logar na demo")
            return

        master_info = mt5.account_info()
        master_positions = self.get_positions()

        if not master_info:
            return

        log.info(
            "Demo %s | Saldo: $%.2f | Posicoes: %d",
            master_info.login, master_info.balance, len(master_positions),
        )

        self.sync_to_api(master_info, master_positions)

        # 2. Trocar pra conta real e copiar
        if not self.login_as(FOLLOWER_LOGIN, FOLLOWER_PASS, FOLLOWER_SERVER):
            log.warning("Nao conseguiu logar na real")
            return

        follower_info = mt5.account_info()
        follower_positions = self.get_positions()

        if not follower_info:
            return

        log.info(
            "Real %s | Saldo: $%.2f | Posicoes: %d",
            follower_info.login, follower_info.balance, len(follower_positions),
        )

        self.sync_to_api(follower_info, follower_positions)

        # 3. Copiar trades novos da demo
        master_tickets = {p["ticket"] for p in master_positions}
        follower_tickets = set()

        for pos in follower_positions:
            if pos["ticket"] in self.state.get("copied_tickets", []):
                follower_tickets.add(pos["ticket"])

        for mp in master_positions:
            if mp["ticket"] in self.state.get("copied_tickets", []):
                continue

            copy_lot = mp["volume"] * LOT_MULTIPLIER
            copy_lot = max(MIN_LOT, min(copy_lot, MAX_LOT))

            log.info(
                "Copiando: %s %s %.2f lotes @ %.5f",
                mp["symbol"], mp["type"].upper(), copy_lot, mp["open_price"],
            )

            result = self.open_trade(
                mp["symbol"], mp["type"], copy_lot, mp["sl"], mp["tp"]
            )

            if result and result.retcode in (TRADE_RETCODE_DONE, TRADE_RETCODE_PLACED):
                log.info("Trade copiado! Ticket: %d", result.order)
                self.state["copied_tickets"].append(mp["ticket"])
                self.stats["copies"] += 1
            else:
                err = result.retcode if result else "None"
                log.error("Erro copiar: %s", err)

        # 4. Fechar trades que o master fechou
        copied = self.state.get("copied_tickets", [])
        for ct in list(copied):
            if ct not in master_tickets:
                for fp in follower_positions:
                    if fp["ticket"] == ct:
                        log.info("Fechando copia: ticket %d", ct)
                        self.close_position(ct)
                        copied.remove(ct)
                        self.stats["closes"] += 1
                        break

        self.state["copied_tickets"] = copied
        self.state["last_sync"] = datetime.now().isoformat()
        save_state(self.state)
        self.stats["syncs"] += 1

        # 5. Voltar pra demo pro proximo ciclo
        self.login_as(MASTER_LOGIN, MASTER_PASS, MASTER_SERVER)

    def run(self):
        if not self.connect():
            return

        log.info("=" * 55)
        log.info("LEVERAGE INVEST - Copy Trader Iniciado")
        log.info("Master (Demo): %s", MASTER_LOGIN)
        log.info("Follower (Real): %s", FOLLOWER_LOGIN)
        log.info("Multiplicador: %sx | Intervalo: %ds", LOT_MULTIPLIER, SYNC_INTERVAL)
        log.info("=" * 55)

        while self.running:
            try:
                self.copy_cycle()
            except KeyboardInterrupt:
                break
            except Exception as e:
                log.error("Erro: %s", e)
                self.stats["errors"] += 1
            time.sleep(SYNC_INTERVAL)

        mt5.shutdown()
        log.info("Encerrado | %s", self.stats)


if __name__ == "__main__":
    MT5CopyTrader().run()
