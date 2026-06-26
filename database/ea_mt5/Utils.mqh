#ifndef TFM_UTILS_MQH
#define TFM_UTILS_MQH

string TFM_TimeframeToString(ENUM_TIMEFRAMES tf)
{
   switch(tf)
   {
      case PERIOD_M1:   return "M1";
      case PERIOD_M2:   return "M2";
      case PERIOD_M3:   return "M3";
      case PERIOD_M4:   return "M4";
      case PERIOD_M5:   return "M5";
      case PERIOD_M6:   return "M6";
      case PERIOD_M10:  return "M10";
      case PERIOD_M12:  return "M12";
      case PERIOD_M15:  return "M15";
      case PERIOD_M20:  return "M20";
      case PERIOD_M30:  return "M30";
      case PERIOD_H1:   return "H1";
      case PERIOD_H2:   return "H2";
      case PERIOD_H3:   return "H3";
      case PERIOD_H4:   return "H4";
      case PERIOD_H6:   return "H6";
      case PERIOD_H8:   return "H8";
      case PERIOD_H12:  return "H12";
      case PERIOD_D1:   return "D1";
      case PERIOD_W1:   return "W1";
      case PERIOD_MN1:  return "MN1";
      default:          return EnumToString(tf);
   }
}

string TFM_DirectionToString(int direction)
{
   if(direction == TFM_DIR_BUY)
      return "Buy";

   if(direction == TFM_DIR_SELL)
      return "Sell";

   if(direction == TFM_DIR_MIXED)
      return "Mixed";

   return "Wait";
}

void TFM_ClearState(TFM_State &state)
{
   state.direction   = TFM_DIR_NONE;
   state.source      = "Wait";
   state.time        = 0;
   state.rangePoints = 0.0;
}

void TFM_SetState(TFM_State &state, int direction, string source, datetime timeValue, double rangePoints)
{
   state.direction   = direction;
   state.source      = source;
   state.time        = timeValue;
   state.rangePoints = rangePoints;
}

bool TFM_StateEquals(TFM_State &leftState, TFM_State &rightState)
{
   if(leftState.direction != rightState.direction)
      return false;

   if(leftState.source != rightState.source)
      return false;

   if(leftState.time != rightState.time)
      return false;

   return true;
}

string TFM_StateKey(TFM_State &state)
{
   return IntegerToString(state.direction) + ":" + state.source + ":" + IntegerToString((long)state.time);
}

string TFM_TimeHHMM(datetime timeValue)
{
   if(timeValue <= 0)
      return "--:--";

   return TimeToString(timeValue, TIME_MINUTES);
}

int TFM_StateAgeCandles(int tfIndex, TFM_State &state)
{
   if(state.time <= 0)
      return 0;

   if(tfIndex < 0 || tfIndex >= TFM_TF_COUNT)
      return 0;

   int shift = iBarShift(_Symbol, TFM_TFList[tfIndex], state.time, true);

   if(shift < 0)
      shift = iBarShift(_Symbol, TFM_TFList[tfIndex], state.time, false);

   if(shift < 0)
      return 0;

   int age = shift - 1;

   if(age < 0)
      age = 0;

   return age;
}

string TFM_EMARelationText(int tfIndex, TFM_State &state)
{
   if(state.direction != TFM_DIR_BUY && state.direction != TFM_DIR_SELL)
      return "";

   // Jika EMA filter ON, trigger yang lolos pasti searah EMA.
   // Jadi info ditampilkan sebagai Trend.
   if(UseEMAFilter)
      return "Trend";

   if(tfIndex < 0 || tfIndex >= TFM_TF_COUNT)
      return "";

   if(state.time <= 0)
      return "";

   int shift = iBarShift(_Symbol, TFM_TFList[tfIndex], state.time, true);

   if(shift < 0)
      shift = iBarShift(_Symbol, TFM_TFList[tfIndex], state.time, false);

   if(shift < 0)
      return "";

   double closePrice = iClose(_Symbol, TFM_TFList[tfIndex], shift);

   if(closePrice <= 0.0)
      return "";

   double emaValue = TFM_GetEMAValue(tfIndex, shift);

   if(emaValue <= 0.0)
      return "";

   bool isTrend = false;

   if(state.direction == TFM_DIR_BUY)
      isTrend = (closePrice > emaValue);
   else if(state.direction == TFM_DIR_SELL)
      isTrend = (closePrice < emaValue);

   if(isTrend)
      return "Trend";

   return "Rev";
}

string TFM_StateMarkerText(int tfIndex, TFM_State &state, bool isNew)
{
   if(state.direction == TFM_DIR_NONE || state.time <= 0)
      return "";

   string triggerTime = TFM_TimeHHMM(state.time);
   int age = TFM_StateAgeCandles(tfIndex, state);

   // Trigger yang benar-benar baru dan menyebabkan notif.
   // Tampil: (N) 19:50 (Trend/Rev)
   if(isNew)
   {
      string marker = " (N) " + triggerTime;
      string emaRelation = TFM_EMARelationText(tfIndex, state);

      if(emaRelation != "")
         marker += " (" + emaRelation + ")";

      return marker;
   }

   // Jika age masih 0, artinya trigger masih berada di candle closed terakhir.
   // Jadi tetap tampil sebagai (N), bukan (0).
   // Karena tampil (N), tetap berikan Trend/Rev agar tidak membingungkan.
   if(age <= 0)
   {
      string marker = " (N) " + triggerTime;
      string emaRelation = TFM_EMARelationText(tfIndex, state);

      if(emaRelation != "")
         marker += " (" + emaRelation + ")";

      return marker;
   }

   return " (" + IntegerToString(age) + ") " + triggerTime;
}

string TFM_StateText(string tfName, int tfIndex, TFM_State &state, bool isNew)
{
   if(state.direction == TFM_DIR_NONE)
      return tfName + " Wait";

   return tfName + " " + TFM_DirectionToString(state.direction) + "-" + state.source + TFM_StateMarkerText(tfIndex, state, isNew);
}

void TFM_ResetState()
{
   for(int i = 0; i < TFM_TF_COUNT; i++)
      TFM_EMAHandle[i] = INVALID_HANDLE;

   TFM_ClearState(TFM_H1State);
   TFM_ClearState(TFM_M15State);
   TFM_ClearState(TFM_M5State);

   TFM_ClearState(TFM_LastNotifiedH1State);
   TFM_ClearState(TFM_LastNotifiedM15State);
   TFM_ClearState(TFM_LastNotifiedM5State);

   TFM_LastSnapshot = "";
   TFM_LastEventKey = "";
   TFM_HasSnapshot  = false;
   TFM_IsRunning    = false;
   TFM_StartTime    = 0;
   TFM_LoadPrinted = false;
   TFM_WaitDataPrinted = false;

   TFM_H1NewMarker  = false;
   TFM_M15NewMarker = false;
   TFM_M5NewMarker  = false;

   for(int j = 0; j < TFM_TF_COUNT; j++)
   {
      TFM_LastClosedTime[j] = 0;
      TFM_StateReady[j] = false;
   }
}

void TFM_ReleaseEMAHandles()
{
   for(int i = 0; i < TFM_TF_COUNT; i++)
   {
      if(TFM_EMAHandle[i] != INVALID_HANDLE)
      {
         IndicatorRelease(TFM_EMAHandle[i]);
         TFM_EMAHandle[i] = INVALID_HANDLE;
      }
   }
}

bool TFM_InitEMAHandle(int tfIndex)
{
   if(tfIndex < 0 || tfIndex >= TFM_TF_COUNT)
      return false;

   if(TFM_EMAHandle[tfIndex] != INVALID_HANDLE)
      return true;

   ENUM_TIMEFRAMES tf = TFM_TFList[tfIndex];

   TFM_EMAHandle[tfIndex] = iMA(_Symbol, tf, EMAPeriod, 0, MODE_EMA, PRICE_CLOSE);

   if(TFM_EMAHandle[tfIndex] == INVALID_HANDLE)
      return false;

   return true;
}

void TFM_InitEMAHandles()
{
   for(int i = 0; i < TFM_TF_COUNT; i++)
      TFM_InitEMAHandle(i);
}

bool TFM_EMAReady(int tfIndex, int shift)
{
   if(!TFM_InitEMAHandle(tfIndex))
      return false;

   int calculated = BarsCalculated(TFM_EMAHandle[tfIndex]);

   if(calculated <= shift)
      return false;

   return true;
}

double TFM_GetEMAValue(int tfIndex, int shift)
{
   if(!TFM_EMAReady(tfIndex, shift))
      return 0.0;

   double buffer[];
   ArraySetAsSeries(buffer, true);

   ResetLastError();
   int copied = CopyBuffer(TFM_EMAHandle[tfIndex], 0, shift, 1, buffer);

   if(copied <= 0)
      return 0.0;

   return buffer[0];
}

bool TFM_PassEMAFilter(int tfIndex, bool isBuy, double closePrice, int shift)
{
   if(!UseEMAFilter)
      return true;

   double emaValue = TFM_GetEMAValue(tfIndex, shift);

   if(emaValue <= 0.0)
      return false;

   if(isBuy)
      return (closePrice > emaValue);

   return (closePrice < emaValue);
}

double TFM_GetRangePoints(int tfIndex, int shift)
{
   ENUM_TIMEFRAMES tf = TFM_TFList[tfIndex];

   double high = iHigh(_Symbol, tf, shift);
   double low  = iLow(_Symbol, tf, shift);

   return (high - low) / _Point;
}

double TFM_GetBodyPoints(int tfIndex, int shift)
{
   ENUM_TIMEFRAMES tf = TFM_TFList[tfIndex];

   double openPrice  = iOpen(_Symbol, tf, shift);
   double closePrice = iClose(_Symbol, tf, shift);

   return MathAbs(closePrice - openPrice) / _Point;
}

double TFM_GetUpperWickPoints(int tfIndex, int shift)
{
   ENUM_TIMEFRAMES tf = TFM_TFList[tfIndex];

   double openPrice  = iOpen(_Symbol, tf, shift);
   double closePrice = iClose(_Symbol, tf, shift);
   double highPrice  = iHigh(_Symbol, tf, shift);

   double bodyTop = MathMax(openPrice, closePrice);

   return (highPrice - bodyTop) / _Point;
}

double TFM_GetLowerWickPoints(int tfIndex, int shift)
{
   ENUM_TIMEFRAMES tf = TFM_TFList[tfIndex];

   double openPrice  = iOpen(_Symbol, tf, shift);
   double closePrice = iClose(_Symbol, tf, shift);
   double lowPrice   = iLow(_Symbol, tf, shift);

   double bodyBottom = MathMin(openPrice, closePrice);

   return (bodyBottom - lowPrice) / _Point;
}

double TFM_NormalizedBodyPoints(double bodyPoints)
{
   if(bodyPoints <= 0.0)
      return 1.0;

   return bodyPoints;
}

void TFM_AppendText(string &text, string addText)
{
   if(text != "")
      text += "+";

   text += addText;
}

int TFM_MinBarsRequired()
{
   int need = TriggerLookbackBars + MarubozuCompareCandles + 10;

   if(TriggerLookbackBars + DominanBreakMaxCandles + 10 > need)
      need = TriggerLookbackBars + DominanBreakMaxCandles + 10;

   if(need < 50)
      need = 50;

   return need;
}

#endif