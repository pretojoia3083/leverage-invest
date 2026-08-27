//+------------------------------------------------------------------+
//|                                               BTC TREND.mq5       |
//|                                    LEVERAGE INVEST - Trend        |
//|                          Estratégia: Breakout + Volume + ATR      |
//+------------------------------------------------------------------+
#property copyright "LEVERAGE INVEST"
#property link      "leverageinvest.com"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== CONFIGURAÇÕES GERAIS ==="
input double InpRiskPercent    = 2.0;
input double InpLotMultiplier  = 1.0;
input double InpMaxLot         = 1.0;
input double InpMinLot         = 0.01;
input bool   InpUseDynamicLot  = true;
input double InpFixedLot       = 0.01;

input group "=== ENTRADA ==="
input int    InpEmaFast        = 20;
input int    InpEmaSlow        = 100;
input int    InpAtrPeriod      = 14;
input double InpAtrMultiplier  = 1.5;
input int    InpVolumePeriod   = 20;
input double InpVolumeThresh   = 1.5;
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_M15;

input group "=== SAÍDA ==="
input int    InpStopLoss       = 80;
input int    InpTakeProfit     = 160;
input bool   InpUseTrailing    = true;
input int    InpTrailingPips   = 50;

input group "=== GERENCIAMENTO ==="
input int    InpMaxDailyTrades = 8;
input double InpMaxDailyLoss   = 5.0;
input int    InpMagicNumber    = 202402;

CTrade trade;
int emaFastH, emaSlowH, atrH, volH;
datetime lastTradeDate = 0;
int dailyTrades = 0;
double dailyPnL = 0;

int OnInit()
{
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(30);
   
   emaFastH = iMA(Symbol(), InpTimeframe, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE);
   emaSlowH = iMA(Symbol(), InpTimeframe, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE);
   atrH = iATR(Symbol(), InpTimeframe, InpAtrPeriod);
   volH = iVolumes(Symbol(), InpTimeframe, VOLUMES_TICK);
   
   if(emaFastH == INVALID_HANDLE || emaSlowH == INVALID_HANDLE || atrH == INVALID_HANDLE)
   {
      Print("Erro ao criar indicadores BTC TREND!");
      return INIT_FAILED;
   }
   
   Print("BTC TREND inicializado | ", Symbol());
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   IndicatorRelease(emaFastH);
   IndicatorRelease(emaSlowH);
   IndicatorRelease(atrH);
}

void OnTick()
{
   datetime today = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));
   if(today != lastTradeDate) { lastTradeDate = today; dailyTrades = 0; dailyPnL = 0; }
   
   CheckDailyLimits();
   
   if(PositionsTotal() > 0)
   {
      if(InpUseTrailing) ManageTrailing();
      return;
   }
   
   double emaF[], emaS[], atr[];
   ArraySetAsSeries(emaF, true);
   ArraySetAsSeries(emaS, true);
   ArraySetAsSeries(atr, true);
   
   if(CopyBuffer(emaFastH, 0, 0, 3, emaF) < 3) return;
   if(CopyBuffer(emaSlowH, 0, 0, 3, emaS) < 3) return;
   if(CopyBuffer(atrH, 0, 0, 3, atr) < 3) return;
   
   double high1 = iHigh(Symbol(), InpTimeframe, 1);
   double high2 = iHigh(Symbol(), InpTimeframe, 2);
   double low1 = iLow(Symbol(), InpTimeframe, 1);
   double low2 = iLow(Symbol(), InpTimeframe, 2);
   double close1 = iClose(Symbol(), InpTimeframe, 1);
   
   double atrVal = atr[1];
   double buffer = atrVal * InpAtrMultiplier;
   
   bool buySignal = (emaF[1] > emaS[1]) && (close1 > high2 + buffer) && (close1 > emaS[1]);
   bool sellSignal = (emaF[1] < emaS[1]) && (close1 < low2 - buffer) && (close1 < emaS[1]);
   
   if(buySignal && CountOrders() == 0 && dailyTrades < InpMaxDailyTrades)
      OpenBuy();
   else if(sellSignal && CountOrders() == 0 && dailyTrades < InpMaxDailyTrades)
      OpenSell();
}

double CalculateLot()
{
   if(!InpUseDynamicLot) return MathMax(InpMinLot, MathMin(InpFixedLot, InpMaxLot));
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk = balance * InpRiskPercent / 100.0;
   double tickVal = SymbolInfoDouble(Symbol(), SYMBOL_TRADE_TICK_VALUE);
   double lot = (tickVal > 0) ? risk / (InpStopLoss * tickVal * InpLotMultiplier * 10) : InpMinLot;
   lot *= InpLotMultiplier;
   return MathMax(InpMinLot, MathMin(NormalizeDouble(lot, 2), InpMaxLot));
}

void OpenBuy()
{
   double lot = CalculateLot();
   double ask = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
   double sl = ask - InpStopLoss * _Point * 10;
   double tp = ask + InpTakeProfit * _Point * 10;
   if(trade.Buy(lot, Symbol(), ask, sl, tp, "BTC TREND BUY")) { dailyTrades++; Print("BTC BUY: ", lot); }
}

void OpenSell()
{
   double lot = CalculateLot();
   double bid = SymbolInfoDouble(Symbol(), SYMBOL_BID);
   double sl = bid + InpStopLoss * _Point * 10;
   double tp = bid - InpTakeProfit * _Point * 10;
   if(trade.Sell(lot, Symbol(), bid, sl, tp, "BTC TREND SELL")) { dailyTrades++; Print("BTC SELL: ", lot); }
}

void ManageTrailing()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetString(POSITION_SYMBOL) != Symbol() || PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
         double open = PositionGetDouble(POSITION_PRICE_OPEN);
         double curSL = PositionGetDouble(POSITION_SL);
         long type = PositionGetInteger(POSITION_TYPE);
         
         if(type == POSITION_TYPE_BUY)
         {
            double bid = SymbolInfoDouble(Symbol(), SYMBOL_BID);
            double newSL = bid - InpTrailingPips * _Point * 10;
            if(newSL > open && newSL > curSL) trade.PositionModify(ticket, newSL, PositionGetDouble(POSITION_TP));
         }
         else
         {
            double ask = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
            double newSL = ask + InpTrailingPips * _Point * 10;
            if(newSL < open && (curSL == 0 || newSL < curSL)) trade.PositionModify(ticket, newSL, PositionGetDouble(POSITION_TP));
         }
      }
   }
}

int CountOrders()
{
   int c = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(PositionSelectByTicket(t) && PositionGetString(POSITION_SYMBOL) == Symbol() && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber) c++;
   }
   return c;
}

void CheckDailyLimits()
{
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   if(dailyPnL < 0 && MathAbs(dailyPnL) >= bal * InpMaxDailyLoss / 100.0)
      for(int i = PositionsTotal() - 1; i >= 0; i--) { ulong t = PositionGetTicket(i); if(PositionSelectByTicket(t) && PositionGetString(POSITION_SYMBOL) == Symbol() && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber) trade.PositionClose(t); }
}

void OnTrade()
{
   datetime today = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
   {
      ulong t = HistoryDealGetTicket(i);
      if(t > 0 && (datetime)HistoryDealGetInteger(t, DEAL_TIME) >= today && HistoryDealGetInteger(t, DEAL_MAGIC) == InpMagicNumber)
         dailyPnL += HistoryDealGetDouble(t, DEAL_PROFIT) + HistoryDealGetDouble(t, DEAL_SWAP) + HistoryDealGetDouble(t, DEAL_COMMISSION);
   }
}
//+------------------------------------------------------------------+
