#ifndef TFM_TRIGGERLOGIC_MQH
#define TFM_TRIGGERLOGIC_MQH

//+------------------------------------------------------------------+
//| Trigger 01 - Engulfing                                           |
//| Master logic mengikuti Scanner terakhir:                         |
//| Buy  = C2 bearish, C1 bullish, Close C1 >= Open C2               |
//| Sell = C2 bullish, C1 bearish, Close C1 <= Open C2               |
//+------------------------------------------------------------------+
bool TFM_IsBullishEngulfing(int tfIndex, int shift)
{
   ENUM_TIMEFRAMES tf = TFM_TFList[tfIndex];

   double c1Open  = iOpen(_Symbol, tf, shift);
   double c1Close = iClose(_Symbol, tf, shift);

   double c2Open  = iOpen(_Symbol, tf, shift + 1);
   double c2Close = iClose(_Symbol, tf, shift + 1);

   bool c2Bearish = (c2Close < c2Open);
   bool c1Bullish = (c1Close > c1Open);
   bool engulf    = (c1Close >= c2Open);

   if(!c2Bearish)
      return false;

   if(!c1Bullish)
      return false;

   if(!engulf)
      return false;

   if(!TFM_PassEMAFilter(tfIndex, true, c1Close, shift))
      return false;

   return true;
}

bool TFM_IsBearishEngulfing(int tfIndex, int shift)
{
   ENUM_TIMEFRAMES tf = TFM_TFList[tfIndex];

   double c1Open  = iOpen(_Symbol, tf, shift);
   double c1Close = iClose(_Symbol, tf, shift);

   double c2Open  = iOpen(_Symbol, tf, shift + 1);
   double c2Close = iClose(_Symbol, tf, shift + 1);

   bool c2Bullish = (c2Close > c2Open);
   bool c1Bearish = (c1Close < c1Open);
   bool engulf    = (c1Close <= c2Open);

   if(!c2Bullish)
      return false;

   if(!c1Bearish)
      return false;

   if(!engulf)
      return false;

   if(!TFM_PassEMAFilter(tfIndex, false, c1Close, shift))
      return false;

   return true;
}

//+------------------------------------------------------------------+
//| Trigger 02 - Marubozu                                            |
//+------------------------------------------------------------------+
bool TFM_GetAveragePreviousRange(int tfIndex, int shift, double &avgRangePoints)
{
   avgRangePoints = 0.0;

   int count = MarubozuCompareCandles;

   if(count <= 0)
      count = 1;

   int bars = Bars(_Symbol, TFM_TFList[tfIndex]);

   if(bars <= shift + count)
      return false;

   double sum = 0.0;

   for(int i = 1; i <= count; i++)
   {
      double r = TFM_GetRangePoints(tfIndex, shift + i);

      if(r <= 0.0)
         return false;

      sum += r;
   }

   avgRangePoints = sum / count;

   return true;
}

bool TFM_IsBullishMarubozu(int tfIndex, int shift)
{
   ENUM_TIMEFRAMES tf = TFM_TFList[tfIndex];

   double c1Open  = iOpen(_Symbol, tf, shift);
   double c1Close = iClose(_Symbol, tf, shift);

   if(c1Close <= c1Open)
      return false;

   double rangePoints = TFM_GetRangePoints(tfIndex, shift);
   double upperWick   = TFM_GetUpperWickPoints(tfIndex, shift);
   double lowerWick   = TFM_GetLowerWickPoints(tfIndex, shift);

   if(upperWick > MarubozuWickBufferPoints)
      return false;

   if(lowerWick > MarubozuWickBufferPoints)
      return false;

   double avgRange = 0.0;

   if(!TFM_GetAveragePreviousRange(tfIndex, shift, avgRange))
      return false;

   if(rangePoints < (avgRange * MarubozuRangeMultiplier))
      return false;

   if(!TFM_PassEMAFilter(tfIndex, true, c1Close, shift))
      return false;

   return true;
}

bool TFM_IsBearishMarubozu(int tfIndex, int shift)
{
   ENUM_TIMEFRAMES tf = TFM_TFList[tfIndex];

   double c1Open  = iOpen(_Symbol, tf, shift);
   double c1Close = iClose(_Symbol, tf, shift);

   if(c1Close >= c1Open)
      return false;

   double rangePoints = TFM_GetRangePoints(tfIndex, shift);
   double upperWick   = TFM_GetUpperWickPoints(tfIndex, shift);
   double lowerWick   = TFM_GetLowerWickPoints(tfIndex, shift);

   if(upperWick > MarubozuWickBufferPoints)
      return false;

   if(lowerWick > MarubozuWickBufferPoints)
      return false;

   double avgRange = 0.0;

   if(!TFM_GetAveragePreviousRange(tfIndex, shift, avgRange))
      return false;

   if(rangePoints < (avgRange * MarubozuRangeMultiplier))
      return false;

   if(!TFM_PassEMAFilter(tfIndex, false, c1Close, shift))
      return false;

   return true;
}

//+------------------------------------------------------------------+
//| Trigger 03 - ICT Final                                           |
//+------------------------------------------------------------------+
bool TFM_IsBullishICT(int tfIndex, int shift)
{
   ENUM_TIMEFRAMES tf = TFM_TFList[tfIndex];

   double c1Low   = iLow(_Symbol, tf, shift);
   double c1Close = iClose(_Symbol, tf, shift);

   double c2Open  = iOpen(_Symbol, tf, shift + 1);
   double c2Low   = iLow(_Symbol, tf, shift + 1);
   double c2Close = iClose(_Symbol, tf, shift + 1);

   bool c2Bearish        = (c2Close < c2Open);
   bool lowBreakC2       = (c1Low < c2Low);
   bool closeAboveOpenC2 = (c1Close > c2Open);

   if(!c2Bearish)
      return false;

   if(!lowBreakC2)
      return false;

   if(!closeAboveOpenC2)
      return false;

   if(!TFM_PassEMAFilter(tfIndex, true, c1Close, shift))
      return false;

   return true;
}

bool TFM_IsBearishICT(int tfIndex, int shift)
{
   ENUM_TIMEFRAMES tf = TFM_TFList[tfIndex];

   double c1High  = iHigh(_Symbol, tf, shift);
   double c1Close = iClose(_Symbol, tf, shift);

   double c2Open  = iOpen(_Symbol, tf, shift + 1);
   double c2High  = iHigh(_Symbol, tf, shift + 1);
   double c2Close = iClose(_Symbol, tf, shift + 1);

   bool c2Bullish        = (c2Close > c2Open);
   bool highBreakC2      = (c1High > c2High);
   bool closeBelowOpenC2 = (c1Close < c2Open);

   if(!c2Bullish)
      return false;

   if(!highBreakC2)
      return false;

   if(!closeBelowOpenC2)
      return false;

   if(!TFM_PassEMAFilter(tfIndex, false, c1Close, shift))
      return false;

   return true;
}

//+------------------------------------------------------------------+
//| Trigger 04 - Pinbar Final                                        |
//+------------------------------------------------------------------+
bool TFM_IsBullishPinbar(int tfIndex, int shift)
{
   ENUM_TIMEFRAMES tf = TFM_TFList[tfIndex];

   double c1Close = iClose(_Symbol, tf, shift);

   double rangePoints     = TFM_GetRangePoints(tfIndex, shift);
   double bodyPoints      = TFM_NormalizedBodyPoints(TFM_GetBodyPoints(tfIndex, shift));
   double upperWickPoints = TFM_GetUpperWickPoints(tfIndex, shift);
   double lowerWickPoints = TFM_GetLowerWickPoints(tfIndex, shift);

   if(rangePoints < PinbarMinRangePoints)
      return false;

   if(lowerWickPoints < (bodyPoints * PinbarWickBodyMultiplier))
      return false;

   if(upperWickPoints > bodyPoints)
      return false;

   if(!TFM_PassEMAFilter(tfIndex, true, c1Close, shift))
      return false;

   return true;
}

bool TFM_IsBearishPinbar(int tfIndex, int shift)
{
   ENUM_TIMEFRAMES tf = TFM_TFList[tfIndex];

   double c1Close = iClose(_Symbol, tf, shift);

   double rangePoints     = TFM_GetRangePoints(tfIndex, shift);
   double bodyPoints      = TFM_NormalizedBodyPoints(TFM_GetBodyPoints(tfIndex, shift));
   double upperWickPoints = TFM_GetUpperWickPoints(tfIndex, shift);
   double lowerWickPoints = TFM_GetLowerWickPoints(tfIndex, shift);

   if(rangePoints < PinbarMinRangePoints)
      return false;

   if(upperWickPoints < (bodyPoints * PinbarWickBodyMultiplier))
      return false;

   if(lowerWickPoints > bodyPoints)
      return false;

   if(!TFM_PassEMAFilter(tfIndex, false, c1Close, shift))
      return false;

   return true;
}

//+------------------------------------------------------------------+
//| Trigger 05 - Dominan Break                                       |
//| M = Master candle.                                               |
//| Buy  = close break > High M                                      |
//| Sell = close break < Low M                                       |
//| Break valid minimal candle ke-3 setelah M.                       |
//| Break candle ke-2 tidak valid.                                   |
//| Break memakai close/body candle yang sudah close.                 |
//+------------------------------------------------------------------+
bool TFM_CheckDominanBreak(int tfIndex, int shift, int &direction, int &breakNumber)
{
   direction   = TFM_DIR_NONE;
   breakNumber = 0;

   if(!UseTrigger05_DominanBreak)
      return false;

   ENUM_TIMEFRAMES tf = TFM_TFList[tfIndex];

   int minCandles = DominanBreakMinCandles;
   int maxCandles = DominanBreakMaxCandles;

   if(minCandles < 3)
      minCandles = 3;

   if(maxCandles < minCandles)
      maxCandles = minCandles;

   int bars = Bars(_Symbol, tf);

   if(bars <= shift + maxCandles + 2)
      maxCandles = bars - shift - 3;

   if(maxCandles < minCandles)
      return false;

   double buffer = DominanBreakBufferPoints * _Point;
   double breakClose = iClose(_Symbol, tf, shift);

   if(breakClose <= 0.0)
      return false;

   // Dicari dari Max ke Min agar jika ada beberapa Master yang valid,
   // yang dipilih adalah base paling panjang / paling solid.
   for(int count = maxCandles; count >= minCandles; count--)
   {
      int masterShift = shift + count;

      double masterHigh = iHigh(_Symbol, tf, masterShift);
      double masterLow  = iLow(_Symbol, tf, masterShift);

      if(masterHigh <= 0.0 || masterLow <= 0.0)
         continue;

      bool buyBreak  = (breakClose > (masterHigh + buffer));
      bool sellBreak = (breakClose < (masterLow - buffer));

      if(!buyBreak && !sellBreak)
         continue;

      bool previousClosesInside = true;

      // Candle 1 sampai candle sebelum break harus belum close keluar range Master.
      // Wick boleh keluar, tapi body close tidak boleh break.
      for(int i = 1; i < count; i++)
      {
         double c = iClose(_Symbol, tf, shift + i);

         if(c <= 0.0)
         {
            previousClosesInside = false;
            break;
         }

         if(c > (masterHigh + buffer) || c < (masterLow - buffer))
         {
            previousClosesInside = false;
            break;
         }
      }

      if(!previousClosesInside)
         continue;

      if(buyBreak)
      {
         if(!TFM_PassEMAFilter(tfIndex, true, breakClose, shift))
            continue;

         direction = TFM_DIR_BUY;
         breakNumber = count;
         return true;
      }

      if(sellBreak)
      {
         if(!TFM_PassEMAFilter(tfIndex, false, breakClose, shift))
            continue;

         direction = TFM_DIR_SELL;
         breakNumber = count;
         return true;
      }
   }

   return false;
}

bool TFM_GetTriggerStateOnShift(int tfIndex, int shift, TFM_State &outState)
{
   TFM_ClearState(outState);

   datetime signalTime = iTime(_Symbol, TFM_TFList[tfIndex], shift);

   if(signalTime <= 0)
      return false;

   bool engulfBuy  = false;
   bool engulfSell = false;

   bool marubozuBuy  = false;
   bool marubozuSell = false;

   bool ictBuy  = false;
   bool ictSell = false;

   bool pinbarBuy  = false;
   bool pinbarSell = false;

   bool dbBuy  = false;
   bool dbSell = false;
   int  dbDirection = TFM_DIR_NONE;
   int  dbNumber = 0;

   if(UseTrigger01_Engulfing)
   {
      engulfBuy  = TFM_IsBullishEngulfing(tfIndex, shift);
      engulfSell = TFM_IsBearishEngulfing(tfIndex, shift);
   }

   if(UseTrigger02_Marubozu)
   {
      marubozuBuy  = TFM_IsBullishMarubozu(tfIndex, shift);
      marubozuSell = TFM_IsBearishMarubozu(tfIndex, shift);
   }

   if(UseTrigger03_ICT)
   {
      ictBuy  = TFM_IsBullishICT(tfIndex, shift);
      ictSell = TFM_IsBearishICT(tfIndex, shift);
   }

   if(UseTrigger04_Pinbar)
   {
      pinbarBuy  = TFM_IsBullishPinbar(tfIndex, shift);
      pinbarSell = TFM_IsBearishPinbar(tfIndex, shift);
   }

   if(UseTrigger05_DominanBreak)
   {
      if(TFM_CheckDominanBreak(tfIndex, shift, dbDirection, dbNumber))
      {
         dbBuy  = (dbDirection == TFM_DIR_BUY);
         dbSell = (dbDirection == TFM_DIR_SELL);
      }
   }

   int totalValid = 0;

   if(engulfBuy || engulfSell)
      totalValid++;

   if(marubozuBuy || marubozuSell)
      totalValid++;

   if(ictBuy || ictSell)
      totalValid++;

   if(pinbarBuy || pinbarSell)
      totalValid++;

   if(dbBuy || dbSell)
      totalValid++;

   if(totalValid <= 0)
      return false;

   bool anyBuy  = (engulfBuy || marubozuBuy || ictBuy || pinbarBuy || dbBuy);
   bool anySell = (engulfSell || marubozuSell || ictSell || pinbarSell || dbSell);

   int direction = TFM_DIR_MIXED;

   if(anyBuy && !anySell)
      direction = TFM_DIR_BUY;
   else if(anySell && !anyBuy)
      direction = TFM_DIR_SELL;

   string triggerList = "";

   if(engulfBuy || engulfSell)
      TFM_AppendText(triggerList, "Engulfing");

   if(marubozuBuy || marubozuSell)
      TFM_AppendText(triggerList, "Marubozu");

   if(ictBuy || ictSell)
      TFM_AppendText(triggerList, "ICT");

   if(pinbarBuy || pinbarSell)
      TFM_AppendText(triggerList, "Pinbar");

   if(dbBuy || dbSell)
      TFM_AppendText(triggerList, "DB-" + IntegerToString(dbNumber));

   string source = triggerList;

   if(totalValid > 1)
   {
      if(UseMultiTrigger)
         source = "Multi:" + triggerList;
      else
      {
         if(engulfBuy || engulfSell)
         {
            source = "Engulfing";
            direction = engulfBuy ? TFM_DIR_BUY : TFM_DIR_SELL;
         }
         else if(marubozuBuy || marubozuSell)
         {
            source = "Marubozu";
            direction = marubozuBuy ? TFM_DIR_BUY : TFM_DIR_SELL;
         }
         else if(ictBuy || ictSell)
         {
            source = "ICT";
            direction = ictBuy ? TFM_DIR_BUY : TFM_DIR_SELL;
         }
         else if(pinbarBuy || pinbarSell)
         {
            source = "Pinbar";
            direction = pinbarBuy ? TFM_DIR_BUY : TFM_DIR_SELL;
         }
         else if(dbBuy || dbSell)
         {
            source = "DB-" + IntegerToString(dbNumber);
            direction = dbBuy ? TFM_DIR_BUY : TFM_DIR_SELL;
         }
      }
   }

   TFM_SetState(outState, direction, source, signalTime, TFM_GetRangePoints(tfIndex, shift));

   return true;
}

bool TFM_FindLatestTriggerState(int tfIndex, TFM_State &outState)
{
   TFM_ClearState(outState);

   int bars = Bars(_Symbol, TFM_TFList[tfIndex]);

   if(bars < 10)
      return false;

   int maxShift = TriggerLookbackBars;

   int extraLookback = MarubozuCompareCandles;

   if(DominanBreakMaxCandles > extraLookback)
      extraLookback = DominanBreakMaxCandles;

   int maxAllowed = bars - extraLookback - 2;

   if(maxShift > maxAllowed)
      maxShift = maxAllowed;

   if(maxShift < 1)
      return false;

   bool found = false;
   TFM_State temp;

   for(int shift = maxShift; shift >= 1; shift--)
   {
      if(TFM_GetTriggerStateOnShift(tfIndex, shift, temp))
      {
         outState = temp;
         found = true;
      }
   }

   return found;
}

#endif