//+------------------------------------------------------------------+
//|                                        FlexScalper.mq5           |
//|                        LEVERAGE INVEST - Robo Configuravel        |
//|                        Cercar Mercado + Trailing + Timer          |
//+------------------------------------------------------------------+
#property copyright "LEVERAGE INVEST"
#property link      ""
#property version   "3.00"

//+------------------------------------------------------------------+
//| INPUTS CONFIGURAVEIS                                              |
//+------------------------------------------------------------------+
input group "=== SIMBOLO ==="
input string   InpSymbol        = "BTCUSD";      // Symbol (deixe vazio = grafico atual)
input double   InpLot           = 0.01;           // Lote
input int      InpMagic         = 777777;         // Magic Number

input group "=== ENTRADA (ORDENS PENDENTES) ==="
input int      InpEntryPoints   = 25000;          // Distancia entrada (pontos)
input int      InpSpreadLimit   = 3000;           // Spread maximo permitido (pontos)

input group "=== STOP LOSS ==="
input int      InpSLPoints      = 15000;          // Stop Loss (pontos, 0 = desabilitado)

input group "=== TAKE PROFIT ==="
input int      InpTPPoints      = 0;              // Take Profit (pontos, 0 = desabilitado)

input group "=== TRAILING STOP ==="
input bool     InpUseTrail      = true;           // Usar Trailing Stop
input int      InpTrailStart    = 15000;           // Trailing ativar apos (pontos de lucro)
input int      InpTrailStep     = 7000;            // Trailing distance (pontos)

input group "=== TIMER (CANCELAR SE NAO PEGAR) ==="
input int      InpCancelSec     = 300;            // Cancelar apos (segundos)
input int      InpWaitSec       = 120;            // Esperar antes de nova tentativa (segundos)

input group "=== GERENCIAMENTO DE RISCO ==="
input double   InpMaxLot        = 1.0;            // Lote maximo
input double   InpMinLot        = 0.01;           // Lote minimo
input int      InpSlippage      = 30;             // Slippage
input bool     InpAutoRefresh   = true;           // Auto-refresh pending orders

input group "=== FILTROS ==="
input bool     InpFilterHour    = false;          // Usar filtro de horario
input int      InpStartHour     = 8;              // Hora inicio (servidor)
input int      InpEndHour       = 20;             // Hora fim (servidor)
input bool     InpFilterFriday  = false;          // Fechar sexta-feira
input int      InpFridayHour    = 18;             // Hora fechar sexta

//+------------------------------------------------------------------+
//| GLOBALS                                                           |
//+------------------------------------------------------------------+
ulong buyTicket = 0;
ulong sellTicket = 0;
datetime ordersPlacedAt = 0;
bool inCooldown = false;
datetime cooldownEnd = 0;
int cycleCount = 0;
string sym;
double pt;
int dig;
double contractSize;

//+------------------------------------------------------------------+
int OnInit()
{
   sym = InpSymbol;
   if(sym == "") sym = _Symbol;

   pt = SymbolInfoDouble(sym, SYMBOL_POINT);
   dig = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   contractSize = SymbolInfoDouble(sym, SYMBOL_TRADE_CONTRACT_SIZE);

   EventSetTimer(1);

   Print("===========================================");
   Print("LEVERAGE INVEST - FlexScalper v3.0");
   Print("Symbol: ", sym, " | Lot: ", InpLot);
   Print("Entry: ", InpEntryPoints, " pts | SL: ", InpSLPoints, " pts");
   Print("Trail: ", InpUseTrail ? "SIM" : "NAO",
         InpUseTrail ? (" (" + IntegerToString(InpTrailStart) + "/" + IntegerToString(InpTrailStep) + ")") : "");
   Print("Timer: cancela ", InpCancelSec, "s | espera ", InpWaitSec, "s");
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
   if(InpFilterHour && IsOutsideHours()) return;
   if(InpFilterFriday && IsFridayClose()) { CloseAllAndCancel(); return; }

   if(inCooldown)
   {
      if(TimeCurrent() >= cooldownEnd)
      {
         inCooldown = false;
         Print("Cooldown fim. Novas ordens...");
         PlaceOrders();
      }
      return;
   }

   if(HasOpenPosition())
   {
      if(InpUseTrail) ManageTrailing();
      return;
   }

   if(!HasPendingOrders())
   {
      PlaceOrders();
      return;
   }

   if(ordersPlacedAt > 0)
   {
      int elapsed = (int)(TimeCurrent() - ordersPlacedAt);
      if(elapsed >= InpCancelSec)
      {
         Print("Timer ", elapsed, "s. Cancelando...");
         CancelAllPending();
         inCooldown = true;
         cooldownEnd = TimeCurrent() + InpWaitSec;
         Print("Cooldown: ", InpWaitSec, "s");
      }
   }
}

//+------------------------------------------------------------------+
void OnTrade()
{
   if(HasOpenPosition() && !HasPendingOrders())
   {
      Print("Posicao aberta. Cancelando pendentes...");
      CancelAllPending();
   }
}

//+------------------------------------------------------------------+
//| VERIFICACOES                                                      |
//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagic
         && PositionGetString(POSITION_SYMBOL) == sym)
         return true;
   }
   return false;
}

bool HasPendingOrders()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket > 0 && OrderGetInteger(ORDER_MAGIC) == InpMagic
         && OrderGetString(ORDER_SYMBOL) == sym)
         return true;
   }
   return false;
}

bool IsOutsideHours()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   return (dt.hour < InpStartHour || dt.hour >= InpEndHour);
}

bool IsFridayClose()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   return (dt.day_of_week == 5 && dt.hour >= InpFridayHour);
}

//+------------------------------------------------------------------+
//| ORDENS                                                            |
//+------------------------------------------------------------------+
void PlaceOrders()
{
   double ask = SymbolInfoDouble(sym, SYMBOL_ASK);
   double bid = SymbolInfoDouble(sym, SYMBOL_BID);
   int spread = (int)SymbolInfoInteger(sym, SYMBOL_SPREAD);

   if(ask <= 0 || bid <= 0) return;

   if(spread > InpSpreadLimit)
   {
      Print("Spread alto: ", spread, " > ", InpSpreadLimit);
      return;
   }

   double buyPrice = NormalizeDouble(ask + InpEntryPoints * pt, dig);
   double sellPrice = NormalizeDouble(bid - InpEntryPoints * pt, dig);

   double buySL = 0, buyTP = 0;
   double sellSL = 0, sellTP = 0;

   if(InpSLPoints > 0)
   {
      buySL = NormalizeDouble(buyPrice - InpSLPoints * pt, dig);
      sellSL = NormalizeDouble(sellPrice + InpSLPoints * pt, dig);
   }
   if(InpTPPoints > 0)
   {
      buyTP = NormalizeDouble(buyPrice + InpTPPoints * pt, dig);
      sellTP = NormalizeDouble(sellPrice - InpTPPoints * pt, dig);
   }

   cycleCount++;

   //--- BUY STOP
   MqlTradeRequest req = {};
   MqlTradeResult res = {};
   req.action = TRADE_ACTION_PENDING;
   req.symbol = sym;
   req.volume = CalcLot();
   req.type = ORDER_TYPE_BUY_STOP;
   req.price = buyPrice;
   req.sl = buySL;
   req.tp = buyTP;
   req.deviation = InpSlippage;
   req.magic = InpMagic;
   req.comment = "BUY_" + IntegerToString(cycleCount);

   if(OrderSend(req, res))
   {
      buyTicket = res.order;
      Print("[", cycleCount, "] BUY STOP @ ", buyPrice,
            " | SL: ", buySL, " | TP: ", buyTP > 0 ? DoubleToString(buyTP, dig) : "NONE",
            " | Lot: ", req.volume);
   }
   else
      Print("[", cycleCount, "] ERRO BUY: ", res.retcode, " - ", res.comment);

   //--- SELL STOP
   req = {};
   res = {};
   req.action = TRADE_ACTION_PENDING;
   req.symbol = sym;
   req.volume = CalcLot();
   req.type = ORDER_TYPE_SELL_STOP;
   req.price = sellPrice;
   req.sl = sellSL;
   req.tp = sellTP;
   req.deviation = InpSlippage;
   req.magic = InpMagic;
   req.comment = "SELL_" + IntegerToString(cycleCount);

   if(OrderSend(req, res))
   {
      sellTicket = res.order;
      Print("[", cycleCount, "] SELL STOP @ ", sellPrice,
            " | SL: ", sellSL, " | TP: ", sellTP > 0 ? DoubleToString(sellTP, dig) : "NONE",
            " | Lot: ", req.volume);
   }
   else
      Print("[", cycleCount, "] ERRO SELL: ", res.retcode, " - ", res.comment);

   ordersPlacedAt = TimeCurrent();
   Print("[", cycleCount, "] Ordens colocadas. Mid: ",
         DoubleToString((buyPrice + sellPrice) / 2, dig));
}

void CancelAllPending()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket > 0 && OrderGetInteger(ORDER_MAGIC) == InpMagic
         && OrderGetString(ORDER_SYMBOL) == sym)
      {
         MqlTradeRequest req = {};
         MqlTradeResult res = {};
         req.action = TRADE_ACTION_REMOVE;
         req.order = ticket;
         OrderSend(req, res);
      }
   }
   buyTicket = 0;
   sellTicket = 0;
   ordersPlacedAt = 0;
}

void CloseAllAndCancel()
{
   CancelAllPending();
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagic
         && PositionGetString(POSITION_SYMBOL) == sym)
      {
         MqlTradeRequest req = {};
         MqlTradeResult res = {};
         req.action = TRADE_ACTION_DEAL;
         req.position = ticket;
         req.symbol = sym;
         req.volume = PositionGetDouble(POSITION_VOLUME);
         req.deviation = InpSlippage;
         req.magic = InpMagic;
         req.comment = "FRIDAY_CLOSE";

         long posType = PositionGetInteger(POSITION_TYPE);
         req.type = (posType == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
         req.price = (req.type == ORDER_TYPE_BUY) ?
            SymbolInfoDouble(sym, SYMBOL_ASK) : SymbolInfoDouble(sym, SYMBOL_BID);

         OrderSend(req, res);
         Print("Posicao ", ticket, " fechada (sexta)");
      }
   }
}

//+------------------------------------------------------------------+
//| TRAILING STOP                                                     |
//+------------------------------------------------------------------+
void ManageTrailing()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetInteger(POSITION_MAGIC) == InpMagic
         && PositionGetString(POSITION_SYMBOL) == sym)
      {
         double openP = PositionGetDouble(POSITION_PRICE_OPEN);
         double curSL = PositionGetDouble(POSITION_SL);
         double curTP = PositionGetDouble(POSITION_TP);
         long posType = PositionGetInteger(POSITION_TYPE);

         if(posType == POSITION_TYPE_BUY)
         {
            double bid = SymbolInfoDouble(sym, SYMBOL_BID);
            double profit = (bid - openP) / pt;

            if(profit >= InpTrailStart)
            {
               double newSL = NormalizeDouble(bid - InpTrailStep * pt, dig);
               if(newSL > curSL + pt)
               {
                  MqlTradeRequest req = {};
                  MqlTradeResult res = {};
                  req.action = TRADE_ACTION_SLTP;
                  req.position = ticket;
                  req.symbol = sym;
                  req.sl = newSL;
                  req.tp = curTP;
                  if(OrderSend(req, res))
                     Print("Trailing BUY SL->", newSL, " | Lucro: ", DoubleToString(profit, 0), " pts");
               }
            }
         }
         else if(posType == POSITION_TYPE_SELL)
         {
            double ask = SymbolInfoDouble(sym, SYMBOL_ASK);
            double profit = (openP - ask) / pt;

            if(profit >= InpTrailStart)
            {
               double newSL = NormalizeDouble(ask + InpTrailStep * pt, dig);
               if(newSL < curSL - pt || curSL == 0)
               {
                  MqlTradeRequest req = {};
                  MqlTradeResult res = {};
                  req.action = TRADE_ACTION_SLTP;
                  req.position = ticket;
                  req.symbol = sym;
                  req.sl = newSL;
                  req.tp = curTP;
                  if(OrderSend(req, res))
                     Print("Trailing SELL SL->", newSL, " | Lucro: ", DoubleToString(profit, 0), " pts");
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| CALCULO DE LOTE                                                   |
//+------------------------------------------------------------------+
double CalcLot()
{
   double lot = InpLot;
   double step = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
   double minV = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   double maxV = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);

   if(step > 0)
      lot = MathFloor(lot / step) * step;

   lot = MathMax(lot, MathMax(minV, InpMinLot));
   lot = MathMin(lot, MathMin(maxV, InpMaxLot));

   return NormalizeDouble(lot, 2);
}
//+------------------------------------------------------------------+
