//+------------------------------------------------------------------+
//|                                        BTCScalper.mq5            |
//|                        LEVERAGE INVEST - BTC Scalper EA           |
//|                        Ordens pendentes + Timer + Trailing        |
//+------------------------------------------------------------------+
#property copyright "LEVERAGE INVEST"
#property link      ""
#property version   "2.00"

//--- Inputs Configuraveis
input group "=== ORDENS PENDENTES ==="
input double   Lot = 0.01;                    // Lote
input int      EntryDistance = 2500;          // Distancia entrada (pontos)
input int      Slippage = 30;                // Slippage

input group "=== STOP LOSS / TAKE PROFIT ==="
input int      StopLoss = 1000;              // Stop Loss (pontos)
input int      TakeProfit = 0;               // Take Profit (pontos, 0 = desabilitado)

input group "=== TRAILING STOP ==="
input bool     UseTrailing = true;           // Ativar Trailing Stop
input int      TrailActivate = 700;          // Ativar apos (pontos de lucro)
input int      TrailDistance = 500;          // Distancia do Trailing (pontos)

input group "=== TEMPO ==="
input int      CancelSeconds = 300;          // Cancelar apos (segundos) = 5 min
input int      WaitSeconds = 120;            // Esperar antes de nova tentativa (segundos) = 2 min

input group "=== GERAL ==="
input int      MagicNumber = 777777;         // Magic Number
input int      MaxSpread = 3000;             // Spread maximo permitido (pontos)

//--- Globals
ulong buyTicket = 0;
ulong sellTicket = 0;
datetime ordersPlacedAt = 0;
bool inCooldown = false;
datetime cooldownEnd = 0;
int cycleCount = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   EventSetTimer(1);
   cycleCount = 0;

   Print("===========================================");
   Print("LEVERAGE INVEST - BTC Scalper v2.0");
   Print("Entrada: ", EntryDistance, " pontos | SL: ", StopLoss, " pontos");
   Print("Trailing: ", UseTrailing ? "SIM" : "NAO",
         UseTrailing ? (" ativar apos " + IntegerToString(TrailActivate) + " pontos") : "");
   Print("Timer: cancela ", CancelSeconds, "s | espera ", WaitSeconds, "s");
   Print("===========================================");

   PlaceOrders();
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("EA encerrado. Ciclos: ", cycleCount);
}

//+------------------------------------------------------------------+
void OnTimer()
{
   //--- Em cooldown, aguardar
   if(inCooldown)
   {
      if(TimeCurrent() >= cooldownEnd)
      {
         inCooldown = false;
         Print("Cooldown finalizado. Colocando novas ordens...");
         PlaceOrders();
      }
      return;
   }

   //--- Verificar se posicao esta aberta
   if(HasOpenPosition())
   {
      if(UseTrailing)
         ManageTrailing();
      return;
   }

   //--- Verificar se ordens pendentes existem
   if(!HasPendingOrders())
   {
      //--- Sem ordens e sem posicao = colocar novas
      PlaceOrders();
      return;
   }

   //--- Verificar tempo das ordens pendentes
   if(ordersPlacedAt > 0)
   {
      int elapsed = (int)(TimeCurrent() - ordersPlacedAt);
      if(elapsed >= CancelSeconds)
      {
         Print("Tempo esgotou (", elapsed, "s). Cancelando ordens...");
         CancelAllPending();
         inCooldown = true;
         cooldownEnd = TimeCurrent() + WaitSeconds;
         Print("Cooldown: ", WaitSeconds, " segundos...");
      }
   }
}

//+------------------------------------------------------------------+
void OnTrade()
{
   //--- Verificar se posicao foi aberta
   if(HasOpenPosition() && !HasPendingOrders())
   {
      Print("Posicao aberta! Cancelando pendentes restantes...");
      CancelAllPending();
   }
}

//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
bool HasPendingOrders()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0) continue;
      if(OrderGetInteger(ORDER_MAGIC) != MagicNumber) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol) continue;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
void PlaceOrders()
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int spread = (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);

   if(ask <= 0 || bid <= 0)
   {
      Print("Preco invalido");
      return;
   }

   if(spread > MaxSpread)
   {
      Print("Spread alto: ", spread, " > ", MaxSpread, ". Aguardando...");
      return;
   }

   double buyPrice = NormalizeDouble(ask + EntryDistance * point, _Digits);
   double sellPrice = NormalizeDouble(bid - EntryDistance * point, _Digits);

   double buySL = 0, buyTP = 0;
   double sellSL = 0, sellTP = 0;

   if(StopLoss > 0)
   {
      buySL = NormalizeDouble(buyPrice - StopLoss * point, _Digits);
      sellSL = NormalizeDouble(sellPrice + StopLoss * point, _Digits);
   }
   if(TakeProfit > 0)
   {
      buyTP = NormalizeDouble(buyPrice + TakeProfit * point, _Digits);
      sellTP = NormalizeDouble(sellPrice - TakeProfit * point, _Digits);
   }

   cycleCount++;

   //--- BUY STOP
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
   req.comment = "BTC_BUY_" + IntegerToString(cycleCount);

   if(OrderSend(req, res))
   {
      buyTicket = res.order;
      Print("[", cycleCount, "] BUY STOP @ ", buyPrice,
            " | SL: ", buySL, " | TP: ", buyTP > 0 ? DoubleToString(buyTP, _Digits) : "NONE");
   }
   else
   {
      Print("[", cycleCount, "] ERRO BUY: ", res.retcode, " - ", res.comment,
            " | Preco: ", buyPrice, " | Ask: ", ask);
   }

   //--- SELL STOP
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
   req.comment = "BTC_SELL_" + IntegerToString(cycleCount);

   if(OrderSend(req, res))
   {
      sellTicket = res.order;
      Print("[", cycleCount, "] SELL STOP @ ", sellPrice,
            " | SL: ", sellSL, " | TP: ", sellTP > 0 ? DoubleToString(sellTP, _Digits) : "NONE");
   }
   else
   {
      Print("[", cycleCount, "] ERRO SELL: ", res.retcode, " - ", res.comment,
            " | Preco: ", sellPrice, " | Bid: ", bid);
   }

   ordersPlacedAt = TimeCurrent();
   Print("[", cycleCount, "] Ordens colocadas. Preco medio: ",
         DoubleToString((buyPrice + sellPrice) / 2, _Digits));
}

//+------------------------------------------------------------------+
void CancelAllPending()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0) continue;
      if(OrderGetInteger(ORDER_MAGIC) != MagicNumber) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol) continue;

      MqlTradeRequest req = {};
      MqlTradeResult res = {};
      req.action = TRADE_ACTION_REMOVE;
      req.order = ticket;

      if(OrderSend(req, res))
         Print("Ordem ", ticket, " cancelada");
   }
   buyTicket = 0;
   sellTicket = 0;
   ordersPlacedAt = 0;
}

//+------------------------------------------------------------------+
void ManageTrailing()
{
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;

      double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      double currentSL = PositionGetDouble(POSITION_SL);
      double currentTP = PositionGetDouble(POSITION_TP);
      long posType = PositionGetInteger(POSITION_TYPE);

      if(posType == POSITION_TYPE_BUY)
      {
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double profitPoints = (bid - openPrice) / point;

         if(profitPoints >= TrailActivate)
         {
            double newSL = NormalizeDouble(bid - TrailDistance * point, _Digits);
            if(newSL > currentSL + point)
            {
               MqlTradeRequest req = {};
               MqlTradeResult res = {};
               req.action = TRADE_ACTION_SLTP;
               req.position = ticket;
               req.symbol = _Symbol;
               req.sl = newSL;
               req.tp = currentTP;

               if(OrderSend(req, res))
                  Print("Trailing BUY: SL movido para ", newSL,
                        " | Lucro: ", DoubleToString(profitPoints, 0), " pts");
            }
         }
      }
      else if(posType == POSITION_TYPE_SELL)
      {
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double profitPoints = (openPrice - ask) / point;

         if(profitPoints >= TrailActivate)
         {
            double newSL = NormalizeDouble(ask + TrailDistance * point, _Digits);
            if(newSL < currentSL - point || currentSL == 0)
            {
               MqlTradeRequest req = {};
               MqlTradeResult res = {};
               req.action = TRADE_ACTION_SLTP;
               req.position = ticket;
               req.symbol = _Symbol;
               req.sl = newSL;
               req.tp = currentTP;

               if(OrderSend(req, res))
                  Print("Trailing SELL: SL movido para ", newSL,
                        " | Lucro: ", DoubleToString(profitPoints, 0), " pts");
            }
         }
      }
   }
}
//+------------------------------------------------------------------+
