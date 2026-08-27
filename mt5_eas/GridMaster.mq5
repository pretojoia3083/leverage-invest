//+------------------------------------------------------------------+
//|                                            GRID MASTER.mq5        |
//|                                    LEVERAGE INVEST - Grid         |
//|                          Estratégia: Grid + Risk Management       |
//+------------------------------------------------------------------+
#property copyright "LEVERAGE INVEST"
#property link      "leverageinvest.com"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input group "=== CONFIGURAÇÕES GERAIS ==="
input double InpRiskPercent    = 1.0;
input double InpMaxLot         = 0.5;
input double InpMinLot         = 0.01;

input group "=== GRID ==="
input int    InpGridSize       = 30;      // Tamanho do Grid (pips)
input int    InpMaxGridLevels  = 10;      // Máximo de Níveis
input double InpGridMultiplier = 1.2;     // Multiplicador por nível
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_M5;

input group "=== SAÍDA ==="
input int    InpTakeProfit     = 20;      // TP por nível (pips)
input double InpMaxDrawdown    = 10.0;    // Max Drawdown (%)

input group "=== GERENCIAMENTO ==="
input int    InpMagicNumber    = 202403;

CTrade trade;
int gridLevels = 0;
double gridPrices[];
datetime lastBar = 0;

int OnInit()
{
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(20);
   Print("GRID MASTER inicializado | ", Symbol());
   return INIT_SUCCEEDED;
}

void OnTick()
{
   datetime currentBar = iTime(Symbol(), InpTimeframe, 0);
   if(currentBar == lastBar) return;
   lastBar = currentBar;
   
   if(AccountInfoDouble(ACCOUNT_EQUITY) < AccountInfoDouble(ACCOUNT_BALANCE) * (1 - InpMaxDrawdown / 100.0))
   {
      CloseAll();
      gridLevels = 0;
      return;
   }
   
   ManageGrid();
   
   if(gridLevels < InpMaxGridLevels)
   {
      double close = iClose(Symbol(), InpTimeframe, 1);
      double ema20 = iMA(Symbol(), InpTimeframe, 20, 0, MODE_EMA, PRICE_CLOSE);
      
      if(gridLevels == 0)
      {
         if(close > ema20) OpenGrid(ORDER_TYPE_BUY);
         else if(close < ema20) OpenGrid(ORDER_TYPE_SELL);
      }
      else
      {
         ExpandGrid();
      }
   }
   
   CheckTakeProfit();
}

void OpenGrid(ENUM_ORDER_TYPE type)
{
   double price = (type == ORDER_TYPE_BUY) ? SymbolInfoDouble(Symbol(), SYMBOL_ASK) : SymbolInfoDouble(Symbol(), SYMBOL_BID);
   double lot = MathMax(InpMinLot, InpMinLot * MathPow(InpGridMultiplier, 0));
   
   string comment = StringFormat("GRID L0 %s", (type == ORDER_TYPE_BUY) ? "BUY" : "SELL");
   
   if(type == ORDER_TYPE_BUY)
      trade.Buy(lot, Symbol(), price, 0, 0, comment);
   else
      trade.Sell(lot, Symbol(), price, 0, 0, comment);
   
   gridLevels = 1;
   ArrayResize(gridPrices, 1);
   gridPrices[0] = price;
}

void ExpandGrid()
{
   if(gridLevels >= InpMaxGridLevels) return;
   
   double lastPrice = gridPrices[gridLevels - 1];
   double gridDist = InpGridSize * _Point * 10;
   double lot = MathMax(InpMinLot, InpMinLot * MathPow(InpGridMultiplier, gridLevels));
   
   ENUM_ORDER_TYPE lastType = GetLastOrderType();
   ENUM_ORDER_TYPE newType = (lastType == ORDER_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
   double price = (newType == ORDER_TYPE_BUY) ? SymbolInfoDouble(Symbol(), SYMBOL_ASK) : SymbolInfoDouble(Symbol(), SYMBOL_BID);
   
   bool shouldOpen = false;
   if(newType == ORDER_TYPE_BUY && price <= lastPrice - gridDist) shouldOpen = true;
   if(newType == ORDER_TYPE_SELL && price >= lastPrice + gridDist) shouldOpen = true;
   
   if(shouldOpen)
   {
      string comment = StringFormat("GRID L%d %s", gridLevels, (newType == ORDER_TYPE_BUY) ? "BUY" : "SELL");
      if(newType == ORDER_TYPE_BUY)
         trade.Buy(lot, Symbol(), price, 0, 0, comment);
      else
         trade.Sell(lot, Symbol(), price, 0, 0, comment);
      
      gridLevels++;
      ArrayResize(gridPrices, gridLevels);
      gridPrices[gridLevels - 1] = price;
   }
}

void CheckTakeProfit()
{
   double totalPnl = 0;
   double totalVolume = 0;
   double avgPrice = 0;
   int buys = 0, sells = 0;
   
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetString(POSITION_SYMBOL) != Symbol() || PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
         
         totalPnl += PositionGetDouble(POSITION_PROFIT);
         double vol = PositionGetDouble(POSITION_VOLUME);
         totalVolume += vol;
         avgPrice += PositionGetDouble(POSITION_PRICE_OPEN) * vol;
         
         if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) buys++;
         else sells++;
      }
   }
   
   if(totalVolume > 0) avgPrice /= totalVolume;
   
   double tpAmount = totalVolume * InpTakeProfit * _Point * 10 * SymbolInfoDouble(Symbol(), SYMBOL_TRADE_TICK_VALUE) / _Point;
   
   if(totalPnl >= tpAmount && tpAmount > 0)
      CloseAll();
}

ENUM_ORDER_TYPE GetLastOrderType()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetString(POSITION_SYMBOL) == Symbol() && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
            return (ENUM_ORDER_TYPE)PositionGetInteger(POSITION_TYPE);
      }
   }
   return ORDER_TYPE_BUY;
}

void ManageGrid() {}

void CloseAll()
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
   gridLevels = 0;
}
//+------------------------------------------------------------------+
