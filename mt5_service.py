"""
LEVERAGE INVEST - MT5 Monitor (Service)
Instala e roda como servico do Windows.
Inicia automaticamente com o computador, sem precisar de janela aberta.

Instalacao:
  pip install MetaTrader5 requests pywin32
  python mt5_service.py install

Iniciar:
  python mt5_service.py start

Parar:
  python mt5_service.py stop

Remover:
  python mt5_service.py remove
"""

import os
import sys
import time
import json
import logging
import win32serviceutil
import win32service
import win32event
import servicemanager
from datetime import datetime

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

try:
    import requests
except ImportError:
    requests = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mt5_service.log'),
            encoding='utf-8'
        ),
    ]
)
log = logging.getLogger('MT5Service')

API_BASE = "https://leverage-invest.onrender.com"
SYNC_INTERVAL = 15
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mt5_accounts.json')

DEFAULT_ACCOUNTS = [
    {"account": 26006210, "server": "Cent ECN VantageMarkets-Demo 5"},
    {"account": 29267317, "server": "Cent ECN VantageMarkets-Live 5"},
]


def load_accounts():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(DEFAULT_ACCOUNTS, f, indent=2)
    return DEFAULT_ACCOUNTS


class MT5MonitorService(win32serviceutil.ServiceFramework):
    _svc_name_ = "LeverageInvestMT5"
    _svc_display_name_ = "LEVERAGE INVEST - MT5 Monitor"
    _svc_description_ = "Monitora trades do MT5 e sincroniza com o painel LEVERAGE INVEST"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.running = False
        win32event.SetEvent(self.stop_event)
        log.info("Servico LEVERAGE INVEST MT5 Monitor parado")

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ''),
        )
        self.main()

    def connect_mt5(self):
        if mt5 is None:
            log.error("MetaTrader5 nao instalado: pip install MetaTrader5")
            return False
        if not mt5.initialize():
            log.error("MT5 initialize: %s", mt5.last_error())
            return False
        return True

    def get_account_info(self, account_num):
        if not mt5.login(account_num):
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
        if not positions:
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

    def get_closed_today(self, account_num):
        if not mt5.login(account_num):
            return []
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        deals = mt5.history_deals_get(today, datetime.now())
        if not deals:
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

    def report(self, cfg, acc, trades):
        if requests is None:
            log.error("requests nao instalado: pip install requests")
            return False
        payload = {
            "account_number": str(cfg["account"]),
            "server": cfg["server"],
            "balance": acc["balance"],
            "equity": acc["equity"],
            "profit_today": acc["profit_today"],
            "profit_week": acc["profit_week"],
            "trades": trades,
        }
        try:
            r = requests.post(f"{API_BASE}/api/mt5/report", json=payload, timeout=15)
            if r.status_code == 200:
                log.info(
                    "Conta %d | $%.2f | Trades: %d | Sync OK",
                    cfg["account"], acc["balance"], len(trades)
                )
                return True
            else:
                log.warning("API %d: %s", r.status_code, r.text[:100])
                return False
        except Exception as e:
            log.error("API erro: %s", e)
            return False

    def sync_cycle(self):
        accounts = load_accounts()
        for cfg in accounts:
            acc = self.get_account_info(cfg["account"])
            if acc is None:
                log.warning("Conta %d offline", cfg["account"])
                continue
            open_t = self.get_open_trades(cfg["account"])
            closed_t = self.get_closed_today(cfg["account"])
            self.report(cfg, acc, open_t + closed_t)

    def main(self):
        if not self.connect_mt5():
            log.error("MT5 nao encontrado. Verifique se esta aberto.")
            return

        log.info("=" * 50)
        log.info("LEVERAGE INVEST MT5 Monitor - INICIADO")
        log.info("=" * 50)

        while self.running:
            try:
                self.sync_cycle()
            except Exception as e:
                log.error("Ciclo erro: %s", e)
            time.sleep(SYNC_INTERVAL)

        mt5.shutdown()


if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(MT5MonitorService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(MT5MonitorService)
