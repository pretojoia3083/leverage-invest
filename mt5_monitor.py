"""
LEVERAGE INVEST - MT5 Monitor
Profissional de sync em tempo real entre MetaTrader 5 e o dashboard.

Instalacao:
  pip install MetaTrader5 requests

Execucao:
  python mt5_monitor.py

Configuracao:
  - Abra o MT5
  - Execute este script no mesmo computador
  - O script monitora as contas e sincroniza com o painel
"""

import MetaTrader5 as mt5
import requests
import time
import json
import logging
import sys
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('mt5_monitor.log', encoding='utf-8'),
    ]
)
log = logging.getLogger('MT5Monitor')

API_BASE = "https://leverage-invest.onrender.com"
SYNC_INTERVAL = 10
ACCOUNTS = [
    {"account": 26006210, "server": "Cent ECN VantageMarkets-Demo 5"},
    {"account": 29267317, "server": "Cent ECN VantageMarkets-Live 5"},
]


class MT5Monitor:
    def __init__(self):
        self.running = True
        self.stats = {"syncs": 0, "trades_reported": 0, "errors": 0}

    def connect_mt5(self):
        if not mt5.initialize():
            log.error("MT5 initialize failed: %s", mt5.last_error())
            return False
        log.info("MT5 conectado: %s", mt5.terminal_info().name)
        return True

    def get_account_info(self, account_num):
        if not mt5.login(account_num):
            log.warning("Falha login conta %d: %s", account_num, mt5.last_error())
            return None
        info = mt5.account_info()
        if info is None:
            return None
        return {
            "balance": info.balance,
            "equity": info.equity,
            "profit_today": info.profit,
            "profit_week": 0.0,
        }

    def get_open_trades(self, account_num):
        if not mt5.login(account_num):
            return []
        positions = mt5.positions_get()
        if positions is None:
            return []

        trades = []
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
        return trades

    def get_closed_trades_today(self, account_num):
        if not mt5.login(account_num):
            return []
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        deals = mt5.history_deals_get(today, datetime.now())
        if deals is None:
            return []

        trades = []
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
        return trades

    def report_to_api(self, account_cfg, acc_info, trades):
        payload = {
            "account_number": str(account_cfg["account"]),
            "server": account_cfg["server"],
            "balance": acc_info["balance"],
            "equity": acc_info["equity"],
            "profit_today": acc_info["profit_today"],
            "profit_week": acc_info["profit_week"],
            "trades": trades,
        }
        try:
            r = requests.post(
                f"{API_BASE}/api/mt5/report",
                json=payload,
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                log.info(
                    "Conta %d | Saldo: $%.2f | Equity: $%.2f | Trades: %d | Sync: %d",
                    account_cfg["account"],
                    acc_info["balance"],
                    acc_info["equity"],
                    len(trades),
                    data.get("trades_synced", 0),
                )
                self.stats["trades_reported"] += len(trades)
                return True
            else:
                log.error("API erro %d: %s", r.status_code, r.text[:200])
                return False
        except Exception as e:
            log.error("Erro conexao API: %s", e)
            return False

    def sync_once(self):
        for cfg in ACCOUNTS:
            acc = self.get_account_info(cfg["account"])
            if acc is None:
                log.warning("Conta %d offline", cfg["account"])
                continue

            open_trades = self.get_open_trades(cfg["account"])
            closed_trades = self.get_closed_trades_today(cfg["account"])
            all_trades = open_trades + closed_trades

            if self.report_to_api(cfg, acc, all_trades):
                self.stats["syncs"] += 1
            else:
                self.stats["errors"] += 1

    def run(self):
        if not self.connect_mt5():
            log.error("Nao foi possivel conectar ao MT5. Verifique se esta aberto.")
            return

        log.info("=" * 60)
        log.info("LEVERAGE INVEST - MT5 Monitor Iniciado")
        log.info("Contas monitoradas: %s", [str(a['account']) for a in ACCOUNTS])
        log.info("Intervalo de sync: %ds", SYNC_INTERVAL)
        log.info("=" * 60)

        while self.running:
            try:
                self.sync_once()
            except KeyboardInterrupt:
                log.info("Monitor interrompido pelo usuario")
                break
            except Exception as e:
                log.error("Erro no ciclo: %s", e)
                self.stats["errors"] += 1

            time.sleep(SYNC_INTERVAL)

        mt5.shutdown()
        log.info("MT5 Monitor encerrado")
        log.info("Stats: %s", self.stats)


if __name__ == "__main__":
    monitor = MT5Monitor()
    monitor.run()
