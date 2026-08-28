//+------------------------------------------------------------------+
//|                                     CopyDemoToReal.mq5           |
//|                        LEVERAGE INVEST - Copiador de Sinais       |
//|                        Copia trades da conta Demo para Real       |
//+------------------------------------------------------------------+
#property copyright "LEVERAGE INVEST"
#property link      ""
#property version   "1.00"
#property strict

//--- Input parameters
input int      MasterAccount = 26006210;        // Conta Master (Demo)
input double   LotMultiplier = 1.0;             // Multiplicador de Lote
input double   MaxLot = 1.0;                    // Lote Maximo
input double   MinLot = 0.01;                   // Lote Minimo
input int      ScanInterval = 5;                // Intervalo de verificacao (segundos)
input int      MagicNumber = 999999;            // Magic Number para trades copiados
input bool     CopySL = true;                   // Copiar Stop Loss
input bool     CopyTP = true;                   // Copiar Take Profit
input bool     CloseCopiedOnClose = true;       // Fechar copia quando master fechar

//--- Global variables
datetime lastCheck = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                     |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("=== LEVERAGE INVEST Copy Trade Iniciado ===");
   Print("Conta Master (Demo): ", MasterAccount);
   Print("Conta Follower (Real): ", AccountInfoInteger(ACCOUNT_LOGIN));
   Print("Multiplicador: ", LotMultiplier);
   Print("Intervalo: ", ScanInterval, "s");
   EventSetTimer(ScanInterval);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                   |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("=== Copy Trade Encerrado ===");
}

//+------------------------------------------------------------------+
//| Timer function                                                     |
//+------------------------------------------------------------------+
void OnTimer()
{
   CopyTrades();
}

//+------------------------------------------------------------------+
//| Main copy function                                                 |
//+------------------------------------------------------------------+
void CopyTrades()
{
   //--- Get master positions
   if(!HistorySelect(0, TimeCurrent()))
      return;

   //--- Check current open positions on master
   int masterPositions = GetMasterPositionsCount();

   //--- Scan for master trades using deal history
   datetime from = lastCheck;
   datetime to = TimeCurrent();

   if(!HistorySelect(from, to))
      return;

   int deals = HistoryDealsTotal();

   for(int i = 0; i < deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;

      long dealMagic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
      long dealEntry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      long dealAccount = HistoryDealGetInteger(ticket, DEAL_LOGIN);
      string dealSymbol = HistoryDealGetString(ticket, DEAL_SYMBOL);

      //--- Only copy trades from master account
      if(dealAccount != MasterAccount) continue;

      //--- Only copy entry trades (not exits)
      if(dealEntry != DEAL_ENTRY_IN && dealEntry != DEAL_ENTRY_IN_BY) continue;

      //--- Skip if already copied
      string copyTicket = "COPY_" + IntegerToString(ticket);
      if(IsAlreadyCopied(copyTicket)) continue;

      //--- Get trade details
      double dealVolume = HistoryDealGetDouble(ticket, DEAL_VOLUME);
      double dealPrice = HistoryDealGetDouble(ticket, DEAL_PRICE);
      long dealType = HistoryDealGetInteger(ticket, DEAL_TYPE);
      long dealTime = HistoryDealGetInteger(ticket, DEAL_TIME);

      //--- Calculate lot
      double copyLot = dealVolume * LotMultiplier;
      copyLot = MathMax(MinLot, MathMin(copyLot, MaxLot));

      //--- Normalize lot
      double minVolume = SymbolInfoDouble(dealSymbol, SYMBOL_VOLUME_MIN);
      double maxVolume = SymbolInfoDouble(dealSymbol, SYMBOL_VOLUME_MAX);
      double volumeStep = SymbolInfoDouble(dealSymbol, SYMBOL_VOLUME_STEP);

      if(volumeStep > 0)
         copyLot = MathFloor(copyLot / volumeStep) * volumeStep;

      copyLot = MathMax(copyLot, minVolume);
      copyLot = MathMin(copyLot, maxVolume);

      //--- Open copy trade
      int orderType = (dealType == DEAL_TYPE_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;

      MqlTradeRequest request = {};
      MqlTradeResult result = {};

      request.action = TRADE_ACTION_DEAL;
      request.symbol = dealSymbol;
      request.volume = copyLot;
      request.type = orderType;
      request.price = (orderType == ORDER_TYPE_BUY) ?
         SymbolInfoDouble(dealSymbol, SYMBOL_ASK) :
         SymbolInfoDouble(dealSymbol, SYMBOL_BID);
      request.deviation = 30;
      request.magic = MagicNumber;
      request.comment = copyTicket;

      //--- Send order
      if(OrderSend(request, result))
      {
         if(result.retcode == TRADE_RETCODE_DONE || result.retcode == TRADE_RETCODE_PLACED)
         {
            Print("Trade copiado! Master #", ticket, " -> Filiar #", result.order,
                  " | ", dealSymbol, " ", copyLot, " ", (dealType == DEAL_TYPE_BUY ? "BUY" : "SELL"));
         }
         else
         {
            Print("Erro ao copiar: ", result.retcode, " - ", result.comment);
         }
      }
      else
      {
         Print("OrderSend erro: ", GetLastError());
      }
   }

   //--- Check for closed master trades and close copies
   if(CloseCopiedOnClose)
   {
      CheckClosedMasterTrades();
   }

   lastCheck = TimeCurrent();
}

//+------------------------------------------------------------------+
//| Get master positions count                                         |
//+------------------------------------------------------------------+
int GetMasterPositionsCount()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0)
      {
         long posMagic = PositionGetInteger(POSITION_MAGIC);
         if(posMagic == MagicNumber)
            count++;
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//| Check if already copied                                            |
//+------------------------------------------------------------------+
bool IsAlreadyCopied(string copyTicket)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0)
      {
         string comment = PositionGetString(POSITION_COMMENT);
         if(comment == copyTicket)
            return true;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| Check closed master trades                                         |
//+------------------------------------------------------------------+
void CheckClosedMasterTrades()
{
   datetime from = lastCheck;
   datetime to = TimeCurrent();

   if(!HistorySelect(from, to))
      return;

   int deals = HistoryDealsTotal();

   for(int i = 0; i < deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;

      long dealAccount = HistoryDealGetInteger(ticket, DEAL_LOGIN);
      long dealEntry = HistoryDealGetInteger(ticket, DEAL_ENTRY);

      if(dealAccount != MasterAccount) continue;
      if(dealEntry != DEAL_ENTRY_OUT && dealEntry != DEAL_ENTRY_OUT_BY) continue;

      //--- Find and close matching copied position
      string copyComment = "COPY_" + IntegerToString(ticket);

      for(int j = PositionsTotal() - 1; j >= 0; j--)
      {
         ulong posTicket = PositionGetTicket(j);
         if(posTicket > 0)
         {
            string comment = PositionGetString(POSITION_COMMENT);
            if(comment == copyComment)
            {
               //--- Close position
               MqlTradeRequest request = {};
               MqlTradeResult result = {};

               request.action = TRADE_ACTION_DEAL;
               request.position = posTicket;
               request.symbol = PositionGetString(POSITION_SYMBOL);
               request.volume = PositionGetDouble(POSITION_VOLUME);
               request.deviation = 30;
               request.magic = MagicNumber;
               request.comment = "COPY_CLOSE";

               long posType = PositionGetInteger(POSITION_TYPE);
               request.type = (posType == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
               request.price = (request.type == ORDER_TYPE_BUY) ?
                  SymbolInfoDouble(request.symbol, SYMBOL_ASK) :
                  SymbolInfoDouble(request.symbol, SYMBOL_BID);

               OrderSend(request, result);
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| OnTrade event                                                      |
//+------------------------------------------------------------------+
void OnTrade()
{
   //--- Extra safety check on trade events
   CopyTrades();
}
//+------------------------------------------------------------------+
