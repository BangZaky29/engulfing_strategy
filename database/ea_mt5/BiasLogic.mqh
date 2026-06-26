#ifndef TFM_BIASLOGIC_MQH
#define TFM_BIASLOGIC_MQH

bool TFM_FindLatestH1State(TFM_State &outState)
{
   TFM_ClearState(outState);

   int bars = Bars(_Symbol, PERIOD_H1);

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

   // H1 sekarang memakai trigger yang sama dengan M15 dan M5:
   // Engulfing, Marubozu, ICT, Pinbar, Dominan Break.
   // LBC dan Candle fallback dihapus supaya H1 tidak punya aturan khusus.
   // Jika H1 mixed, H1 tidak dipakai sebagai bias baru karena kolom utama harus Buy/Sell.
   for(int shift = maxShift; shift >= 1; shift--)
   {
      if(TFM_GetTriggerStateOnShift(TFM_INDEX_H1, shift, temp))
      {
         if(temp.direction == TFM_DIR_BUY || temp.direction == TFM_DIR_SELL)
         {
            outState = temp;
            found = true;
         }
      }
   }

   return found;
}

bool TFM_UpdateStateByIndex(int tfIndex)
{
   datetime closedTime = iTime(_Symbol, TFM_TFList[tfIndex], 1);

   if(closedTime <= 0)
      return false;

   // Scan hanya saat pertama kali atau ketika candle close TF tersebut berubah.
   // Ini mencegah MT5 berat/hang karena scan lookback berulang setiap tick.
   if(TFM_StateReady[tfIndex] && TFM_LastClosedTime[tfIndex] == closedTime)
      return true;

   TFM_State newState;
   bool found = false;

   if(tfIndex == TFM_INDEX_H1)
   {
      found = TFM_FindLatestH1State(newState);

      if(found)
         TFM_H1State = newState;
      else if(!TFM_StateReady[tfIndex])
         TFM_ClearState(TFM_H1State);
   }
   else if(tfIndex == TFM_INDEX_M15)
   {
      found = TFM_FindLatestTriggerState(TFM_INDEX_M15, newState);

      if(found)
         TFM_M15State = newState;
      else if(!TFM_StateReady[tfIndex])
         TFM_ClearState(TFM_M15State);
   }
   else if(tfIndex == TFM_INDEX_M5)
   {
      found = TFM_FindLatestTriggerState(TFM_INDEX_M5, newState);

      if(found)
         TFM_M5State = newState;
      else if(!TFM_StateReady[tfIndex])
         TFM_ClearState(TFM_M5State);
   }

   // Walaupun tidak menemukan trigger pertama kali, tetap tandai siap agar tidak scan terus tanpa henti.
   // Nanti akan scan lagi kalau candle closed TF tersebut berubah.
   TFM_LastClosedTime[tfIndex] = closedTime;
   TFM_StateReady[tfIndex] = true;

   return true;
}

bool TFM_UpdateAllStates()
{
   if(!TFM_UpdateStateByIndex(TFM_INDEX_H1))
      return false;

   TFM_UpdateStateByIndex(TFM_INDEX_M15);
   TFM_UpdateStateByIndex(TFM_INDEX_M5);

   return true;
}

string TFM_MainBiasColumn()
{
   string mainDirection = TFM_DirectionToString(TFM_H1State.direction);

   if(TFM_H1State.direction == TFM_DIR_BUY && TFM_M15State.direction == TFM_DIR_BUY)
      return "Buy+";

   if(TFM_H1State.direction == TFM_DIR_SELL && TFM_M15State.direction == TFM_DIR_SELL)
      return "Sell+";

   return mainDirection;
}

bool TFM_H1M15Aligned()
{
   if(TFM_H1State.direction != TFM_DIR_BUY && TFM_H1State.direction != TFM_DIR_SELL)
      return false;

   if(TFM_M15State.direction != TFM_DIR_BUY && TFM_M15State.direction != TFM_DIR_SELL)
      return false;

   return (TFM_H1State.direction == TFM_M15State.direction);
}

string TFM_ValidityStatus()
{
   if(!TFM_H1M15Aligned())
      return "WAIT";

   int h1Age  = TFM_StateAgeCandles(TFM_INDEX_H1, TFM_H1State);
   int m15Age = TFM_StateAgeCandles(TFM_INDEX_M15, TFM_M15State);

   string h1EMA  = TFM_EMARelationText(TFM_INDEX_H1, TFM_H1State);
   string m15EMA = TFM_EMARelationText(TFM_INDEX_M15, TFM_M15State);

   bool h1Trend  = (h1EMA == "Trend");
   bool m15Trend = (m15EMA == "Trend");

   bool h1Rev  = (h1EMA == "Rev");
   bool m15Rev = (m15EMA == "Rev");

   // LATE: H1 sudah terlalu jauh dari trigger awal.
   // Sesuai keputusan awal: H1 age >= 5 = no OP baru.
   if(h1Age >= 5)
      return "LATE";

   // STRONG: H1 dan M15 searah, sama-sama Trend, H1 belum tua, M15 masih fresh.
   if(h1Trend && m15Trend && h1Age <= 3 && m15Age <= 2)
      return "STRONG";

   // EARLY: H1 dan M15 searah, tapi ada unsur Rev/reversal awal, dan masih fresh.
   if((h1Rev || m15Rev) && h1Age <= 3 && m15Age <= 2)
      return "EARLY";

   // VALID: H1 dan M15 searah, bukan LATE, tapi tidak memenuhi STRONG/EARLY.
   return "VALID";
}

string TFM_BuildEventKey()
{
   string key = TFM_MainBiasColumn();

   key += "|STATUS=" + TFM_ValidityStatus();
   key += "|H1=" + TFM_StateKey(TFM_H1State);
   key += "|M15=" + TFM_StateKey(TFM_M15State);
   key += "|M5=" + TFM_StateKey(TFM_M5State);

   return key;
}

string TFM_BuildSnapshot()
{
   string msg = "TF Monitor | " + TFM_ValidityStatus() + " | " + TFM_MainBiasColumn();

   msg += " | " + TFM_StateText("H1", TFM_INDEX_H1, TFM_H1State, TFM_H1NewMarker);
   msg += " | " + TFM_StateText("M15", TFM_INDEX_M15, TFM_M15State, TFM_M15NewMarker);
   msg += " | " + TFM_StateText("M5", TFM_INDEX_M5, TFM_M5State, TFM_M5NewMarker);
   msg += " | " + _Symbol;

   return msg;
}

#endif