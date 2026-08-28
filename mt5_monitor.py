"""
LEVERAGE INVEST - MT5 Monitor
Sincroniza contas MT5 com o dashboard em tempo real.

Instalacao: pip install MetaTrader5 requests
Execucao: python mt5_monitor.py
Auto-start: Executar instalar_monitor.bat como administrador
"""

import MetaTrader5 as mt5
import requests
import time
import json
import logging
import sys
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, 'mt5_monitor.log')
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'mt5_config.json')

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
SYNC_INTERVAL = 10


def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)


class MT5Monitor:
    def __init__(self):
        self.running = True
        self.stats = {"syncs": 0, "trades_reported": 0, "errors": 0}
        self.last_positions = {}
        self.config = load_config()
        self.accounts = self.config["accounts"]

    def connect_mt5(self):
        if not mt5.initialize():
            log.error("MT5 initialize failed: %s", mt5.last_error())
            return False
        info = mt5.terminal_info()
        log.info("MT5 conectado: %s", info.name if info else "OK")
        return True

    def get_account_trades(self, login, password, server):
        if not mt5.login(login, password, server):
            log.warning("Falha login %s: %s", login, mt5.last_error())
            return None, []

        info = mt5.account_info()
        if info is None:
            return None, []

        acc = {
            "login": info.login,
            "balance": info.balance,
            "equity": info.equity,
            "profit": info.profit,
            "server": info.server,
        }

        trades = []

        positions = mt5.positions_get()
        if positions:
            for pos in positions:
                trades.append({
                    "ticket": str(pos.ticket),
                    "symbol": pos.symbol,
                    "order_type": "buy" if pos.type == mt5.ORDER_TYPE_BUY else "sell",
                    "volume": pos.volume,
                    "open_price": pos.price_open,
                    "close_price": None,
                    "stop_loss": pos.sl,
                    "take_profit": pos.tp,
                    "profit": pos.profit,
                    "status": "open",
                    "opened_at": datetime.fromtimestamp(pos.time).isoformat() if pos.time else None,
                })

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        deals = mt5.history_deals_get(today, datetime.now())
        if deals:
            for deal in deals:
                if deal.entry == 0:
                    continue
                trades.append({
                    "ticket": str(deal.ticket),
                    "symbol": deal.symbol,
                    "order_type": "buy" if deal.type == mt5.DEAL_TYPE_BUY else "sell",
                    "volume": deal.volume,
                    "open_price": deal.price,
                    "close_price": deal.price,
                    "stop_loss": None,
                    "take_profit": None,
                    "profit": deal.profit,
                    "status": "closed",
                    "opened_at": datetime.fromtimestamp(deal.time).isoformat(),
                })

        return acc, trades

    def report_to_api(self, login, acc, trades):
        payload = {
            "account_number": str(login),
            "server": acc["server"],
            "balance": acc["balance"],
            "equity": acc["equity"],
            "profit_today": acc["profit"],
            "profit_week": 0.0,
            "trades": trades,
        }
        try:
            r = requests.post(f"{API_BASE}/api/mt5/report", json=payload, timeout=15)
            if r.status_code == 200:
                log.info(
                    "Conta %s | Saldo: $%.2f | Equity: $%.2f | Trades: %d",
                    login, acc["balance"], acc["equity"], len(trades),
                )
                self.stats["trades_reported"] += len(trades)
                return True
            else:
                log.error("API %d: %s", r.status_code, r.text[:150])
                return False
        except Exception as e:
            log.error("API erro: %s", e)
            return False

    def sync_once(self):
        for acct in self.accounts:
            login = acct["login"]
            password = acct["password"]
            server = acct["server"]

            acc, trades = self.get_account_trades(login, password, server)
            if acc is None:
                continue

            if self.report_to_api(login, acc, trades):
                self.stats["syncs"] += 1
            else:
                self.stats["errors"] += 1

    def run(self):
        if not self.connect_mt5():
            log.error("MT5 nao encontrado. Verifique se esta aberto.")
            return

        log.info("=" * 50)
        log.info("LEVERAGE INVEST - MT5 Monitor Iniciado")
        log.info("Contas: %s", [str(a['login']) for a in self.accounts])
        log.info("Intervalo: %ds", SYNC_INTERVAL)
        log.info("=" * 50)

        while self.running:
            try:
                self.sync_once()
            except KeyboardInterrupt:
                log.info("Interrompido")
                break
            except Exception as e:
                log.error("Erro: %s", e)
                self.stats["errors"] += 1
            time.sleep(SYNC_INTERVAL)

        mt5.shutdown()
        log.info("Monitor encerrado | Stats: %s", self.stats)


if __name__ == "__main__":
    monitor = MT5Monitor()
    monitor.run()
