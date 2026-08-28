//+------------------------------------------------------------------+
//|                                        BTCBreakout.mq5           |
//|                        LEVERAGE INVEST - BTC Breakout EA          |
//|                        Ordens pendentes Buy/Sell Stop             |
//+------------------------------------------------------------------+
#property copyright "LEVERAGE INVEST"
#property link      ""
#property version   "1.00"

//--- Inputs
input double   Lot = 0.01;                    // Lote
input int      PointsDistance = 2500;         // Distancia em pontos (2500 = $25)
input int      StopLoss = 3000;               // Stop Loss em pontos
input int      TakeProfit = 5000;             // Take Profit em pontos
input int      MagicNumber = 888888;          // Magic Number
input int      Slippage = 30;                 // Slippage
input int      MaxSpread = 2500;              // Spread maximo permitido
input bool     UseTrailing = true;            // Usar Trailing Stop
input int      TrailingStart = 2000;          // Trailing Start (pontos de lucro)
input int      TrailingStep = 500;            // Trailing Step (pontos)

//--- Globals
ulong buyTicket = 0;
ulong sellTicket = 0;
bool orderActive = false;

//+------------------------------------------------------------------+
int OnInit()
{
   Print("=== BTC Breakout EA Iniciado ===");
   Print("Distancia: ", PointsDistance, " pontos ($", PointsDistance * 0.01, ")");

   EventSetTimer(1);
   PlacePendingOrders();
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("=== BTC Breakout EA Encerrado ===");
}

//+------------------------------------------------------------------+
void OnTimer()
{
   CheckPendingOrders();

   if(UseTrailing && orderActive)
      ManageTrailing();

   RefreshPendingOrders();
}

//+------------------------------------------------------------------+
void OnTrade()
{
   CheckPendingOrders();
}

//+------------------------------------------------------------------+
void PlacePendingOrders()
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(ask <= 0 || bid <= 0) return;

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   double buyPrice = NormalizeDouble(ask + PointsDistance * point, _Digits);
   double sellPrice = NormalizeDouble(bid - PointsDistance * point, _Digits);

   double buySL = NormalizeDouble(buyPrice - StopLoss * point, _Digits);
   double buyTP = NormalizeDouble(buyPrice + TakeProfit * point, _Digits);
   double sellSL = NormalizeDouble(sellPrice + StopLoss * point, _Digits);
   double sellTP = NormalizeDouble(sellPrice - TakeProfit * point, _Digits);

   //--- Buy Stop
   MqlTradeRequest req = {};
   MqlTradeResult res = {};

   req.action = TRADE_ACTION_PENDING;
   req.symbol = _Symbol;
   req.volume = Lot;
   req.type = ORDER_TYPE_BUY_STOP;
   req.price = buyPrice;
   req.sl = buySL;
   req.tp = buyTP;
   req.deviation = Slippage;
   req.magic = MagicNumber;
   req.comment = "BTC_Breakout_BUY";

   if(OrderSend(req, res))
   {
      buyTicket = res.order;
      Print("BUY STOP criado @ ", buyPrice, " | SL: ", buySL, " | TP: ", buyTP);
   }
   else
   {
      Print("Erro BUY STOP: ", res.retcode, " - ", res.comment);
   }

   //--- Sell Stop
   req = {};
   res = {};

   req.action = TRADE_ACTION_PENDING;
   req.symbol = _Symbol;
   req.volume = Lot;
   req.type = ORDER_TYPE_SELL_STOP;
   req.price = sellPrice;
   req.sl = sellSL;
   req.tp = sellTP;
   req.deviation = Slippage;
   req.magic = MagicNumber;
   req.comment = "BTC_Breakout_SELL";

   if(OrderSend(req, res))
   {
      sellTicket = res.order;
      Print("SELL STOP criado @ ", sellPrice, " | SL: ", sellSL, " | TP: ", sellTP);
   }
   else
   {
      Print("Erro SELL STOP: ", res.retcode, " - ", res.comment);
   }
}

//+------------------------------------------------------------------+
void CheckPendingOrders()
{
   //--- Check if any position opened from our pending orders
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;

      //--- Position found, cancel pending orders
      if(!orderActive)
      {
         orderActive = true;
         Print("Posicao aberta! Ticket: ", ticket, " | Tipo: ",
               PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "BUY" : "SELL");

         CancelPendingOrders();
      }
   }
}

//+------------------------------------------------------------------+
void CancelPendingOrders()
{
   //--- Cancel buy pending
   if(buyTicket > 0)
   {
      MqlTradeRequest req = {};
      MqlTradeResult res = {};
      req.action = TRADE_ACTION_REMOVE;
      req.order = buyTicket;
      OrderSend(req, res);
      buyTicket = 0;
   }

   //--- Cancel sell pending
   if(sellTicket > 0)
   {
      MqlTradeRequest req = {};
      MqlTradeResult res = {};
      req.action = TRADE_ACTION_REMOVE;
      req.order = sellTicket;
      OrderSend(req, res);
      sellTicket = 0;
   }
}

//+------------------------------------------------------------------+
void RefreshPendingOrders()
{
   if(orderActive) return;

   //--- Check if pending orders still exist
   bool buyExists = false;
   bool sellExists = false;

   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0) continue;
      if(OrderGetInteger(ORDER_MAGIC) != MagicNumber) continue;

      if(ticket == buyTicket) buyExists = true;
      if(ticket == sellTicket) sellExists = true;
   }

   //--- If one was triggered, cancel the other
   if(!buyExists && buyTicket > 0) buyTicket = 0;
   if(!sellExists && sellTicket > 0) sellTicket = 0;

   //--- If both gone, place new ones
   if(!buyExists && !sellExists && !orderActive)
   {
      Print("Ambas ordens executadas/canceladas. Recriando...");
      PlacePendingOrders();
   }
}

//+------------------------------------------------------------------+
void ManageTrailing()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;

      double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
      double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      double currentSL = PositionGetDouble(POSITION_SL);
      double currentTP = PositionGetDouble(POSITION_TP);
      long posType = PositionGetInteger(POSITION_TYPE);

      if(posType == POSITION_TYPE_BUY)
      {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double profit = (bid - openPrice) / point;

         if(profit >= TrailingStart)
         {
            double newSL = NormalizeDouble(bid - TrailingStep * point, _Digits);
            if(newSL > currentSL)
            {
               ModifyPosition(ticket, newSL, currentTP);
            }
         }
      }
      else if(posType == POSITION_TYPE_SELL)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double profit = (openPrice - ask) / point;

         if(profit >= TrailingStart)
         {
            double newSL = NormalizeDouble(ask + TrailingStep * point, _Digits);
            if(newSL < currentSL || currentSL == 0)
            {
               ModifyPosition(ticket, newSL, currentTP);
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
bool ModifyPosition(ulong ticket, double sl, double tp)
{
   MqlTradeRequest req = {};
   MqlTradeResult res = {};

   req.action = TRADE_ACTION_SLTP;
   req.position = ticket;
   req.symbol = _Symbol;
   req.sl = sl;
   req.tp = tp;

   return OrderSend(req, res);
}
//+------------------------------------------------------------------+
