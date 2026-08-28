import MetaTrader5 as mt5
from datetime import datetime, timedelta
import json

MT5_PATH = r"C:\Program Files\Vantage International MT5\terminal64.exe"
INITIAL_BALANCE = 1000.0
CANCEL_SECONDS = 300
WAIT_SECONDS = 120


def get_data(symbol, days):
    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, from_date, to_date)
    return rates


def simulate(symbol, rates, entry, sl, trail_act, trail_dist, spread, lot=0.01):
    info = mt5.symbol_info(symbol)
    if info is None:
        return None
    point = info.point
    digits = info.digits
    contract = info.trade_contract_size
    balance = INITIAL_BALANCE
    max_equity = INITIAL_BALANCE
    max_dd = 0
    wins = 0
    losses = 0
    total = 0
    state = "WAITING"
    buy_price = 0
    sell_price = 0
    buy_sl = 0
    sell_sl = 0
    orders_time = 0
    cooldown_end = 0
    pos_type = None
    pos_entry = 0
    pos_sl = 0
    trail_active = False
    trail_sl = 0
    cycle = 0

    for i in range(1, len(rates)):
        t = int(rates[i]['time'])
        o = rates[i]['open']
        h = rates[i]['high']
        l = rates[i]['low']
        c = rates[i]['close']
        prev_o = rates[i-1]['open']

        if state == "COOLDOWN":
            if t >= cooldown_end:
                state = "WAITING"
            else:
                continue

        if pos_type is None:
            if state == "WAITING":
                buy_price = round(prev_o + entry * point, digits)
                sell_price = round(prev_o - entry * point, digits)
                buy_sl = round(buy_price - sl * point, digits)
                sell_sl = round(sell_price + sl * point, digits)
                orders_time = t
                state = "PENDING"

            if state == "PENDING":
                if t - orders_time >= CANCEL_SECONDS:
                    state = "COOLDOWN"
                    cooldown_end = t + WAIT_SECONDS
                    continue

                if h >= buy_price:
                    pos_type = "BUY"
                    pos_entry = buy_price + spread * point
                    pos_sl = buy_sl + spread * point
                    trail_active = False
                    trail_sl = 0
                    state = "IN_POS"
                    continue

                if l <= sell_price:
                    pos_type = "SELL"
                    pos_entry = sell_price
                    pos_sl = sell_sl
                    trail_active = False
                    trail_sl = 999999999
                    state = "IN_POS"
                    continue
        elif state == "IN_POS":
            closed = False
            profit_pts = 0
            if pos_type == "BUY":
                profit_pts = (h - pos_entry) / point
                if l <= pos_sl:
                    profit_pts = (pos_sl - pos_entry) / point
                    closed = True
                elif profit_pts >= trail_act:
                    new_trail = round(c - trail_dist * point, digits)
                    if not trail_active or new_trail > trail_sl:
                        trail_sl = new_trail
                        trail_active = True
                        pos_sl = trail_sl
                if trail_active and l <= trail_sl:
                    profit_pts = (trail_sl - pos_entry) / point
                    closed = True
            elif pos_type == "SELL":
                profit_pts = (pos_entry - l) / point
                if h >= pos_sl:
                    profit_pts = (pos_entry - pos_sl) / point
                    closed = True
                elif profit_pts >= trail_act:
                    new_trail = round(c + trail_dist * point, digits)
                    if not trail_active or new_trail < trail_sl:
                        trail_sl = new_trail
                        trail_active = True
                        pos_sl = trail_sl
                if trail_active and h >= trail_sl:
                    profit_pts = (pos_entry - trail_sl) / point
                    closed = True
            if closed:
                spread_cost = spread * point * contract * lot
                profit_usd = profit_pts * point * contract * lot - spread_cost
                balance += profit_usd
                if balance > max_equity:
                    max_equity = balance
                dd = (max_equity - balance) / max_equity * 100
                if dd > max_dd:
                    max_dd = dd
                total += 1
                if profit_usd > 0:
                    wins += 1
                else:
                    losses += 1
                pos_type = None
                state = "WAITING"

    win_rate = (wins / total * 100) if total > 0 else 0
    return {
        "symbol": symbol,
        "entry": entry,
        "sl": sl,
        "trail_act": trail_act,
        "trail_dist": trail_dist,
        "balance": round(balance, 2),
        "profit": round(balance - INITIAL_BALANCE, 2),
        "trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 1),
        "max_dd": round(max_dd, 2),
        "cycles": cycle,
    }


def run():
    if not mt5.initialize(path=MT5_PATH, timeout=30000):
        print("MT5 init falhou")
        return
    if not mt5.login(26006210, "Michelle82@#", "VantageMarkets-Demo", timeout=30000):
        print("Login falhou")
        return

    symbols_config = {
        "BTCO": 6,
        "GBTC": 3,
        "BTCUSD": 1705,
    }

    btcusd_params = [
        (25000, 12000, 12000, 6000),
        (25000, 15000, 15000, 7000),
        (30000, 20000, 20000, 10000),
        (40000, 20000, 20000, 10000),
        (50000, 30000, 25000, 12000),
        (50000, 25000, 25000, 10000),
        (60000, 30000, 30000, 15000),
        (60000, 35000, 30000, 15000),
        (70000, 35000, 35000, 15000),
        (75000, 40000, 35000, 17000),
    ]

    etf_params = [
        (10, 8, 8, 4),
        (15, 10, 10, 5),
        (20, 12, 12, 6),
        (20, 15, 15, 7),
        (25, 15, 15, 8),
        (30, 18, 18, 9),
        (30, 20, 20, 10),
        (40, 25, 25, 12),
        (50, 30, 30, 15),
        (50, 35, 30, 15),
        (80, 50, 50, 25),
        (80, 60, 50, 25),
    ]

    all_results = []
    days = 60

    for sym, spread in symbols_config.items():
        print(f"\n{'='*60}")
        print(f"Testando {sym} (spread: {spread} pts)")
        print(f"{'='*60}")

        data = get_data(sym, days)
        if data is None or len(data) == 0:
            print(f"  Sem dados para {sym}")
            continue

        print(f"  Dados: {len(data)} velas M1")

        if sym == "BTCUSD":
            combos = btcusd_params
        else:
            combos = etf_params

        for entry, sl, trail_act, trail_dist in combos:
            r = simulate(sym, data, entry, sl, trail_act, trail_dist, spread)
            if r and r["trades"] > 5:
                all_results.append(r)
                status = "LUCRO" if r["profit"] > 0 else "PREJUIZO"
                print(f"  Entry={entry} SL={sl} Trail={trail_act}/{trail_dist} -> "
                      f"${r['profit']:.2f} | {r['trades']} trades | "
                      f"Win {r['win_rate']}% | DD {r['max_dd']}% [{status}]")

    mt5.shutdown()

    all_results.sort(key=lambda x: x["profit"], reverse=True)

    print(f"\n\n{'='*60}")
    print(f"TOP 15 MELHORES RESULTADOS")
    print(f"{'='*60}")
    print(f"{'#':<3} {'Symbol':<8} {'Entry':<7} {'SL':<7} {'Trail':<12} {'Lucro':<12} {'Trades':<8} {'Win%':<7} {'DD%':<7}")
    print("-" * 72)
    for i, r in enumerate(all_results[:15]):
        print(f"{i+1:<3} {r['symbol']:<8} {r['entry']:<7} {r['sl']:<7} {r['trail_act']}/{r['trail_dist']:<8} "
              f"${r['profit']:<11.2f} {r['trades']:<8} {r['win_rate']:<6.1f}% {r['max_dd']:<6.1f}%")

    with open('backtest_results.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResultados salvos em backtest_results.json")


if __name__ == "__main__":
    run()
