"""
LEVERAGE INVEST - MT5 Monitor
Sincroniza a conta demo (com PipScalperEA) com o dashboard.
"""

import MetaTrader5 as mt5
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import time
import json
import logging
import sys
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, 'mt5_monitor.log')

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


class MT5Monitor:
    def __init__(self):
        self.running = True
        self.stats = {"syncs": 0, "trades_reported": 0, "errors": 0}

    def connect(self):
        if not mt5.initialize(path=MT5_PATH, timeout=15000):
            log.error("MT5 falhou: %s", mt5.last_error())
            return False
        info = mt5.account_info()
        if info is None:
            log.error("Nenhuma conta logada no MT5")
            return False
        log.info("MT5 OK | Conta: %s | Servidor: %s", info.login, info.server)
        return True

    def sync_once(self):
        info = mt5.account_info()
        if info is None:
            return

        positions = mt5.positions_get()
        open_trades = []
        if positions:
            for pos in positions:
                open_trades.append({
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
        closed_trades = []
        if deals:
            for deal in deals:
                if deal.entry == 0:
                    continue
                closed_trades.append({
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

        all_trades = open_trades + closed_trades

        payload = {
            "account_number": str(info.login),
            "server": info.server,
            "balance": info.balance,
            "equity": info.equity,
            "profit_today": info.profit,
            "profit_week": 0.0,
            "trades": all_trades,
        }

        try:
            r = requests.post(f"{API_BASE}/api/mt5/report", json=payload, timeout=60, verify=False)
            if r.status_code == 200:
                log.info(
                    "Conta %s | Saldo: $%.2f | Equity: $%.2f | Posicoes: %d | Historico: %d",
                    info.login, info.balance, info.equity,
                    len(open_trades), len(closed_trades),
                )
                self.stats["syncs"] += 1
                self.stats["trades_reported"] += len(all_trades)
            else:
                log.error("API %d: %s", r.status_code, r.text[:150])
        except Exception as e:
            log.error("API erro: %s", e)
            self.stats["errors"] += 1

    def run(self):
        if not self.connect():
            return

        log.info("=" * 50)
        log.info("LEVERAGE INVEST - MT5 Monitor Rodando")
        log.info("Sync a cada %ds", SYNC_INTERVAL)
        log.info("=" * 50)

        while self.running:
            try:
                self.sync_once()
            except KeyboardInterrupt:
                break
            except Exception as e:
                log.error("Erro: %s", e)
                self.stats["errors"] += 1
            time.sleep(SYNC_INTERVAL)

        mt5.shutdown()
        log.info("Encerrado | %s", self.stats)


if __name__ == "__main__":
    MT5Monitor().run()
