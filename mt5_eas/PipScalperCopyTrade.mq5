//+------------------------------------------------------------------+
//| PipScalper Copy Trade EA                                          |
//| Copia trades da conta master para conta follower                  |
//+------------------------------------------------------------------+
#property copyright "LEVERAGE INVEST"
#property version   "1.00"
#property strict

input string MasterServer = "Vantage-Demo";
input int    MasterAccount = 0;
input double LotMultiplier = 1.0;
input double MaxLot = 1.0;
input double MinLot = 0.01;
input bool   CopySL = true;
input bool   CopyTP = true;
input int    MagicNumber = 999999;
input int    ScanDelay = 1;

datetime lastScan = 0;

int OnInit()
{
   Print("PipScalper Copy Trade EA iniciado!");
   Print("Master Account: ", MasterAccount);
   Print("Lot Multiplier: ", LotMultiplier);
   return(INIT_SUCCEEDED);
}

void OnTick()
{
   if(TimeCurrent() - lastScan < ScanDelay) return;
   lastScan = TimeCurrent();
   
   CopyTrades();
}

void CopyTrades()
{
   int totalOrders = OrdersTotal();
   
   for(int i = 0; i < totalOrders; i++)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      
      if(OrderMagicNumber() == MagicNumber) continue;
      
      if(OrderType() > OP_SELL) continue;
      
      if(!IsOrderAlreadyCopied(OrderTicket()))
      {
         OpenCopiedOrder();
      }
   }
}

bool IsOrderAlreadyCopied(int originalTicket)
{
   int totalOrders = OrdersTotal();
   
   for(int i = 0; i < totalOrders; i++)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      
      if(OrderMagicNumber() == MagicNumber)
      {
         if(OrderComment() == IntegerToString(originalTicket))
         {
            return true;
         }
      }
   }
   
   return false;
}

void OpenCopiedOrder()
{
   double originalLot = OrderLots();
   double newLot = originalLot * LotMultiplier;
   
   newLot = MathMax(MinLot, MathMin(newLot, MaxLot));
   
   int type = OrderType();
   double price = 0;
   double sl = 0;
   double tp = 0;
   
   if(type == OP_BUY)
   {
      price = MarketInfo(OrderSymbol(), MODE_ASK);
      if(CopySL && OrderStopLoss() > 0) sl = price - (OrderOpenPrice() - OrderStopLoss());
      if(CopyTP && OrderTakeProfit() > 0) tp = price + (OrderTakeProfit() - OrderOpenPrice());
   }
   else if(type == OP_SELL)
   {
      price = MarketInfo(OrderSymbol(), MODE_BID);
      if(CopySL && OrderStopLoss() > 0) sl = price + (OrderStopLoss() - OrderOpenPrice());
      if(CopyTP && OrderTakeProfit() > 0) tp = price - (OrderOpenPrice() - OrderTakeProfit());
   }
   
   if(price == 0) return;
   
   int ticket = OrderSend(
      OrderSymbol(),
      type,
      newLot,
      price,
      3,
      sl,
      tp,
      IntegerToString(OrderTicket()),
      MagicNumber,
      0,
      clrNONE
   );
   
   if(ticket > 0)
   {
      Print("Trade copiado! Ticket: ", ticket, " | Original: ", OrderTicket());
   }
   else
   {
      Print("Erro ao copiar trade: ", GetLastError());
   }
}
//+------------------------------------------------------------------+