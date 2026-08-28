"""
LEVERAGE INVEST - BTC Scalper Backtest
Simula a estrategia BTCScalper com dados historicos do MT5.
"""

import MetaTrader5 as mt5
from datetime import datetime, timedelta
import json
import os

MT5_PATH = r"C:\Program Files\Vantage International MT5\terminal64.exe"

#--- Configuracao do EA (iguais ao .mq5)
ENTRY_DISTANCE = 6000   # pontos (precisa cobrir spread)
STOP_LOSS = 4000        # pontos (maior que spread)
TAKE_PROFIT = 0         # 0 = desabilitado
TRAIL_ACTIVATE = 4000   # pontos (ate cobrir spread + lucro)
TRAIL_DISTANCE = 2000   # pontos
CANCEL_SECONDS = 300    # 5 min
WAIT_SECONDS = 120      # 2 min
LOT = 0.01
INITIAL_BALANCE = 1000.0
UseTrailing = True
SPREAD = 1705           # spread real BTC Vantage (pontos)

def run_backtest(days):
    from datetime import timezone

    if not mt5.initialize(path=MT5_PATH, timeout=30000):
        print("MT5 init falhou:", mt5.last_error())
        return

    if not mt5.login(26006210, "Michelle82@#", "VantageMarkets-Demo", timeout=30000):
        print("Login falhou:", mt5.last_error())
        return

    symbol = "BTCUSD"
    info = mt5.symbol_info(symbol)
    if info is None:
        print("BTCUSD nao encontrado")
        return

    point = info.point
    digits = info.digits
    contract = info.trade_contract_size

    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)

    print(f"\n{'='*60}")
    print(f"BACKTEST BTCScalper - {days} DIAS")
    print(f"Periodo: {from_date.strftime('%d/%m/%Y')} a {to_date.strftime('%d/%m/%Y')}")
    print(f"Config: Entry={ENTRY_DISTANCE}pts | SL={STOP_LOSS}pts | Trail={TRAIL_ACTIVATE}pts")
    print(f"{'='*60}\n")

    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, from_date, to_date)
    if rates is None or len(rates) == 0:
        print("Sem dados historicos")
        return

    print(f"Dados: {len(rates)} velas M1 carregadas\n")

    balance = INITIAL_BALANCE
    equity = INITIAL_BALANCE
    max_equity = INITIAL_BALANCE
    max_drawdown = 0
    trades = []
    total_wins = 0
    total_losses = 0
    total_trades = 0
    max_consecutive_wins = 0
    max_consecutive_losses = 0
    current_consecutive_wins = 0
    current_consecutive_losses = 0

    #--- Simulacao
    state = "WAITING_ORDERS"
    buy_stop_price = 0
    sell_stop_price = 0
    buy_sl = 0
    sell_sl = 0
    buy_tp = 0
    sell_tp = 0
    orders_placed_time = 0
    cooldown_end = 0
    position_type = None
    position_entry = 0
    position_sl = 0
    position_tp = 0
    position_trail_active = False
    trail_sl = 0
    cycle = 0

    for i in range(1, len(rates)):
        candle_time = int(rates[i]['time'])
        open_price = rates[i]['open']
        high = rates[i]['high']
        low = rates[i]['low']
        close = rates[i]['close']

        #--- Cooldown
        if state == "COOLDOWN":
            if candle_time >= cooldown_end:
                state = "WAITING_ORDERS"
            else:
                continue

        #--- Sem posicao aberta
        if position_type is None:

            #--- Colocar ordens pendentes
            if state == "WAITING_ORDERS" or state == "NO_ORDERS":
                buy_stop_price = round(open_price + ENTRY_DISTANCE * point, digits)
                sell_stop_price = round(open_price - ENTRY_DISTANCE * point, digits)
                buy_sl = round(buy_stop_price - STOP_LOSS * point, digits) if STOP_LOSS > 0 else 0
                sell_sl = round(sell_stop_price + STOP_LOSS * point, digits) if STOP_LOSS > 0 else 0
                buy_tp = round(buy_stop_price + TAKE_PROFIT * point, digits) if TAKE_PROFIT > 0 else 0
                sell_tp = round(sell_stop_price - TAKE_PROFIT * point, digits) if TAKE_PROFIT > 0 else 0
                orders_placed_time = candle_time
                state = "PENDING"
                cycle += 1

            #--- Verificar ordens pendentes
            if state == "PENDING":
                #--- Verificar tempo
                if candle_time - orders_placed_time >= CANCEL_SECONDS:
                    state = "COOLDOWN"
                    cooldown_end = candle_time + WAIT_SECONDS
                    continue

                #--- Buy Stop atingida
                if high >= buy_stop_price:
                    position_type = "BUY"
                    position_entry = buy_stop_price + SPREAD * point  # spread no BUY
                    position_sl = buy_sl + SPREAD * point
                    position_tp = buy_tp + SPREAD * point if buy_tp > 0 else 0
                    position_trail_active = False
                    trail_sl = 0
                    state = "IN_POSITION"
                    continue

                #--- Sell Stop atingida
                if low <= sell_stop_price:
                    position_type = "SELL"
                    position_entry = sell_stop_price  # spread ja embutido no SELL
                    position_sl = sell_sl
                    position_tp = sell_tp
                    position_trail_active = False
                    trail_sl = 999999
                    state = "IN_POSITION"
                    continue

        #--- Posicao aberta
        elif state == "IN_POSITION":
            profit_points = 0
            closed = False
            close_price = 0

            if position_type == "BUY":
                profit_points = (high - position_entry) / point

                #--- Verificar stop loss
                if low <= position_sl:
                    close_price = position_sl
                    profit_points = (close_price - position_entry) / point
                    closed = True

                #--- Verificar take profit
                elif position_tp > 0 and high >= position_tp:
                    close_price = position_tp
                    profit_points = (close_price - position_entry) / point
                    closed = True

                #--- Trailing stop
                elif UseTrailing and profit_points >= TRAIL_ACTIVATE:
                    new_trail = round(close - TRAIL_DISTANCE * point, digits)
                    if not position_trail_active or new_trail > trail_sl:
                        trail_sl = new_trail
                        position_trail_active = True
                        position_sl = trail_sl

                #--- Verificar trailing SL
                if position_trail_active and low <= trail_sl:
                    close_price = trail_sl
                    profit_points = (close_price - position_entry) / point
                    closed = True

            elif position_type == "SELL":
                profit_points = (position_entry - low) / point

                #--- Verificar stop loss
                if high >= position_sl:
                    close_price = position_sl
                    profit_points = (position_entry - close_price) / point
                    closed = True

                #--- Verificar take profit
                elif position_tp > 0 and low <= position_tp:
                    close_price = position_tp
                    profit_points = (position_entry - close_price) / point
                    closed = True

                #--- Trailing stop
                elif UseTrailing and profit_points >= TRAIL_ACTIVATE:
                    new_trail = round(close + TRAIL_DISTANCE * point, digits)
                    if not position_trail_active or new_trail < trail_sl:
                        trail_sl = new_trail
                        position_trail_active = True
                        position_sl = trail_sl

                #--- Verificar trailing SL
                if position_trail_active and high >= trail_sl:
                    close_price = trail_sl
                    profit_points = (position_entry - close_price) / point
                    closed = True

            #--- Fechar posicao (descontar spread)
            if closed:
                spread_cost = SPREAD * point * contract * LOT
                profit_dollars = profit_points * point * contract * LOT - spread_cost
                balance += profit_dollars
                equity = balance

                if balance > max_equity:
                    max_equity = balance
                dd = (max_equity - balance) / max_equity * 100
                if dd > max_drawdown:
                    max_drawdown = dd

                total_trades += 1
                if profit_dollars > 0:
                    total_wins += 1
                    current_consecutive_wins += 1
                    current_consecutive_losses = 0
                    if current_consecutive_wins > max_consecutive_wins:
                        max_consecutive_wins = current_consecutive_wins
                else:
                    total_losses += 1
                    current_consecutive_losses += 1
                    current_consecutive_wins = 0
                    if current_consecutive_losses > max_consecutive_losses:
                        max_consecutive_losses = current_consecutive_losses

                trades.append({
                    "type": position_type,
                    "entry": position_entry,
                    "close": close_price,
                    "profit_pts": profit_points,
                    "profit_usd": profit_dollars,
                    "balance": balance,
                })

                position_type = None
                position_entry = 0
                state = "WAITING_ORDERS"

    #--- Resultados
    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    total_profit = balance - INITIAL_BALANCE
    avg_win = 0
    avg_loss = 0
    if total_wins > 0:
        avg_win = sum(t["profit_usd"] for t in trades if t["profit_usd"] > 0) / total_wins
    if total_losses > 0:
        avg_loss = sum(t["profit_usd"] for t in trades if t["profit_usd"] < 0) / total_losses

    print(f"RESULTADOS - {days} DIAS")
    print(f"{'='*60}")
    print(f"Saldo Inicial:    ${INITIAL_BALANCE:.2f}")
    print(f"Saldo Final:      ${balance:.2f}")
    print(f"Lucro Total:      ${total_profit:.2f} ({total_profit/INITIAL_BALANCE*100:.1f}%)")
    print(f"{'='*60}")
    print(f"Total Trades:     {total_trades}")
    print(f"Wins:             {total_wins} ({win_rate:.1f}%)")
    print(f"Losses:           {total_losses} ({100-win_rate:.1f}%)")
    print(f"{'='*60}")
    print(f"Lucro Medio Win:  ${avg_win:.2f}")
    print(f"Lucro Medio Loss: ${avg_loss:.2f}")
    print(f"Max Consec Wins:  {max_consecutive_wins}")
    print(f"Max Consec Losses:{max_consecutive_losses}")
    print(f"{'='*60}")
    print(f"Max Drawdown:     {max_drawdown:.2f}%")
    print(f"Ciclos:           {cycle}")
    print(f"{'='*60}")

    if trades:
        print(f"\nUltimas 10 trades:")
        print(f"{'Tipo':<6} {'Entrada':<12} {'Saida':<12} {'Pontos':<10} {'Lucro':<12} {'Saldo':<12}")
        print("-" * 64)
        for t in trades[-10:]:
            print(f"{t['type']:<6} {t['entry']:<12.2f} {t['close']:<12.2f} {t['profit_pts']:<10.0f} ${t['profit_usd']:<11.2f} ${t['balance']:<11.2f}")

    return {
        "days": days,
        "balance": balance,
        "profit": total_profit,
        "trades": total_trades,
        "wins": total_wins,
        "losses": total_losses,
        "win_rate": win_rate,
        "max_drawdown": max_drawdown,
    }


if __name__ == "__main__":
    results = []
    for days in [30, 60, 90]:
        r = run_backtest(days)
        if r:
            results.append(r)
        mt5.shutdown()

    if results:
        print(f"\n\n{'='*60}")
        print(f"RESUMO COMPARATIVO")
        print(f"{'='*60}")
        print(f"{'Periodo':<10} {'Lucro':<12} {'Trades':<8} {'Win%':<8} {'Drawdown':<10}")
        print("-" * 48)
        for r in results:
            print(f"{r['days']}d{'':<7} ${r['profit']:<11.2f} {r['trades']:<8} {r['win_rate']:<7.1f}% {r['max_drawdown']:<9.2f}%")
