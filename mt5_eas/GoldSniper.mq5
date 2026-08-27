//+------------------------------------------------------------------+
//|                                               GOLD SNIPER.mq5    |
//|                                    LEVERAGE INVEST - Scalping     |
//|                          Estratégia: EMA 200 + RSI + Scalping     |
//+------------------------------------------------------------------+
#property copyright "LEVERAGE INVEST"
#property link      "leverageinvest.com"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== CONFIGURAÇÕES GERAIS ==="
input double InpRiskPercent    = 2.0;     // % Risco por Trade
input double InpLotMultiplier  = 1.0;     // Multiplicador de Lote
input double InpMaxLot         = 1.0;     // Lote Máximo
input double InpMinLot         = 0.01;    // Lote Mínimo
input bool   InpUseDynamicLot  = true;    // Usar Lote Dinâmico
input double InpFixedLot       = 0.01;    // Lote Fixo (se dinâmico off)

input group "=== ENTRADA ==="
input int    InpEmaFast        = 50;      // EMA Rápida
input int    InpEmaSlow        = 200;     // EMA Lenta
input int    InpRsiPeriod      = 14;      // Período RSI
input double InpRsiOversold    = 30;      // RSI Sobrecompra
input double InpRsiOverbought  = 70;      // RSI Sobrevenda
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_M5; // Timeframe

input group "=== SAÍDA ==="
input int    InpStopLoss       = 50;      // Stop Loss (pips)
input int    InpTakeProfit     = 100;     // Take Profit (pips)
input bool   InpUseTrailing    = false;   // Usar Trailing Stop
input int    InpTrailingPips   = 30;      // Trailing Stop (pips)

input group "=== GERENCIAMENTO ==="
input int    InpMaxDailyTrades = 10;      // Max Trades/Dia
input double InpMaxDailyLoss   = 5.0;     // Max Perda/Dia (%)
input int    InpMagicNumber    = 202401;  // Magic Number

CTrade trade;
int emaFastHandle, emaSlowHandle, rsiHandle;
datetime lastTradeDate = 0;
int dailyTrades = 0;
double dailyPnL = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(20);
   
   emaFastHandle = iMA(Symbol(), InpTimeframe, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE);
   emaSlowHandle = iMA(Symbol(), InpTimeframe, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE);
   rsiHandle = iRSI(Symbol(), InpTimeframe, InpRsiPeriod, PRICE_CLOSE);
   
   if(emaFastHandle == INVALID_HANDLE || emaSlowHandle == INVALID_HANDLE || rsiHandle == INVALID_HANDLE)
   {
      Print("Erro ao criar indicadores!");
      return INIT_FAILED;
   }
   
   Print("GOLD SNIPER inicializado | ", Symbol(), " | TF: ", EnumToString(InpTimeframe));
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(emaFastHandle);
   IndicatorRelease(emaSlowHandle);
   IndicatorRelease(rsiHandle);
}

//+------------------------------------------------------------------+
void OnTick()
{
   datetime today = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));
   if(today != lastTradeDate)
   {
      lastTradeDate = today;
      dailyTrades = 0;
      dailyPnL = 0;
   }
   
   CheckDailyLimits();
   
   if(PositionsTotal() > 0)
   {
      if(InpUseTrailing) ManageTrailing();
      return;
   }
   
   double emaFast[], emaSlow[], rsi[];
   ArraySetAsSeries(emaFast, true);
   ArraySetAsSeries(emaSlow, true);
   ArraySetAsSeries(rsi, true);
   
   if(CopyBuffer(emaFastHandle, 0, 0, 3, emaFast) < 3) return;
   if(CopyBuffer(emaSlowHandle, 0, 0, 3, emaSlow) < 3) return;
   if(CopyBuffer(rsiHandle, 0, 0, 3, rsi) < 3) return;
   
   double close = iClose(Symbol(), InpTimeframe, 1);
   
   bool buySignal = (emaFast[1] > emaSlow[1]) && (emaFast[2] <= emaSlow[2]) && (rsi[1] < InpRsiOverbought) && (close > emaSlow[1]);
   bool sellSignal = (emaFast[1] < emaSlow[1]) && (emaFast[2] >= emaSlow[2]) && (rsi[1] > InpRsiOversold) && (close < emaSlow[1]);
   
   if(buySignal && CountOrders() == 0 && dailyTrades < InpMaxDailyTrades)
      OpenBuy();
   else if(sellSignal && CountOrders() == 0 && dailyTrades < InpMaxDailyTrades)
      OpenSell();
}

//+------------------------------------------------------------------+
double CalculateLot()
{
   if(!InpUseDynamicLot) return MathMax(InpMinLot, MathMin(InpFixedLot, InpMaxLot));
   
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount = balance * InpRiskPercent / 100.0;
   
   double tickValue = SymbolInfoDouble(Symbol(), SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(Symbol(), SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(Symbol(), SYMBOL_POINT);
   
   double slPoints = InpStopLoss;
   double slMoney = slPoints * tickValue * InpLotMultiplier;
   
   double lot = 0;
   if(slMoney > 0)
      lot = riskAmount / (slMoney * 10);
   
   lot *= InpLotMultiplier;
   lot = MathMax(InpMinLot, MathMin(NormalizeDouble(lot, 2), InpMaxLot));
   
   return lot;
}

//+------------------------------------------------------------------+
void OpenBuy()
{
   double lot = CalculateLot();
   double ask = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
   double sl = ask - InpStopLoss * _Point * 10;
   double tp = ask + InpTakeProfit * _Point * 10;
   
   if(trade.Buy(lot, Symbol(), ask, sl, tp, "GOLD SNIPER BUY"))
   {
      dailyTrades++;
      Print("BUY aberto: ", lot, " lotes | SL: ", sl, " | TP: ", tp);
   }
}

//+------------------------------------------------------------------+
void OpenSell()
{
   double lot = CalculateLot();
   double bid = SymbolInfoDouble(Symbol(), SYMBOL_BID);
   double sl = bid + InpStopLoss * _Point * 10;
   double tp = bid - InpTakeProfit * _Point * 10;
   
   if(trade.Sell(lot, Symbol(), bid, sl, tp, "GOLD SNIPER SELL"))
   {
      dailyTrades++;
      Print("SELL aberto: ", lot, " lotes | SL: ", sl, " | TP: ", tp);
   }
}

//+------------------------------------------------------------------+
void ManageTrailing()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetString(POSITION_SYMBOL) != Symbol()) continue;
         if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
         
         double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
         double currentSL = PositionGetDouble(POSITION_SL);
         long type = PositionGetInteger(POSITION_TYPE);
         
         if(type == POSITION_TYPE_BUY)
         {
            double bid = SymbolInfoDouble(Symbol(), SYMBOL_BID);
            double newSL = bid - InpTrailingPips * _Point * 10;
            if(newSL > openPrice && newSL > currentSL)
               trade.PositionModify(ticket, newSL, PositionGetDouble(POSITION_TP));
         }
         else if(type == POSITION_TYPE_SELL)
         {
            double ask = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
            double newSL = ask + InpTrailingPips * _Point * 10;
            if(newSL < openPrice && (currentSL == 0 || newSL < currentSL))
               trade.PositionModify(ticket, newSL, PositionGetDouble(POSITION_TP));
         }
      }
   }
}

//+------------------------------------------------------------------+
int CountOrders()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetString(POSITION_SYMBOL) == Symbol() && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
            count++;
      }
   }
   return count;
}

//+------------------------------------------------------------------+
void CheckDailyLimits()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double maxLoss = balance * InpMaxDailyLoss / 100.0;
   if(dailyPnL < 0 && MathAbs(dailyPnL) >= maxLoss)
   {
      CloseAllPositions();
   }
}

//+------------------------------------------------------------------+
void CloseAllPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetString(POSITION_SYMBOL) == Symbol() && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
            trade.PositionClose(ticket);
      }
   }
}

//+------------------------------------------------------------------+
void OnTrade()
{
   datetime today = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket > 0)
      {
         datetime dealTime = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
         if(dealTime >= today)
         {
            if(HistoryDealGetInteger(ticket, DEAL_MAGIC) == InpMagicNumber)
            {
               double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT) + HistoryDealGetDouble(ticket, DEAL_SWAP) + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
               dailyPnL += profit;
            }
         }
      }
   }
}
//+------------------------------------------------------------------+
