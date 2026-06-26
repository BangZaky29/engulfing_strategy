//+------------------------------------------------------------------+
//|                                                   TF_Monitor.mq5  |
//|               H1 Bias + M15 Confirmation + M5 Trigger Monitor    |
//|               Notification only. No chart objects.               |
//+------------------------------------------------------------------+
#property strict
#property version   "1.41"
#property indicator_chart_window
#property indicator_plots   0
#property indicator_buffers 0

#include <TF_Monitor/Config.mqh>
#include <TF_Monitor/Utils.mqh>
#include <TF_Monitor/TriggerLogic.mqh>
#include <TF_Monitor/BiasLogic.mqh>
#include <TF_Monitor/Notification.mqh>

bool TFM_DataReady()
{
   for(int i = 0; i < TFM_TF_COUNT; i++)
   {
      int bars = Bars(_Symbol, TFM_TFList[i]);

      if(bars < 50)
         return false;

      if(!TFM_EMAReady(i, 1))
         return false;
   }

   return true;
}

void TFM_Run()
{
   if(TFM_IsRunning)
      return;

   TFM_IsRunning = true;

   if(FirstLoadDelaySeconds > 0 && TFM_StartTime > 0)
   {
      if((TimeLocal() - TFM_StartTime) < FirstLoadDelaySeconds)
      {
         TFM_IsRunning = false;
         return;
      }
   }

   if(!TFM_DataReady())
   {
      if(PrintLoadStatus && PrintToExperts && !TFM_WaitDataPrinted)
      {
         Print("TF Monitor | WAIT DATA | loading history/EMA | ", _Symbol);
         TFM_WaitDataPrinted = true;
      }

      TFM_IsRunning = false;
      return;
   }

   TFM_WaitDataPrinted = false;

   if(!TFM_UpdateAllStates())
   {
      TFM_IsRunning = false;
      return;
   }

   TFM_ProcessNotification();
   TFM_IsRunning = false;
}

int OnInit()
{
   TFM_ResetState();
   TFM_InitEMAHandles();

   int timerSeconds = MonitorTimerSeconds;

   if(timerSeconds < 1)
      timerSeconds = 1;

   TFM_StartTime = TimeLocal();

   EventSetTimer(timerSeconds);

   if(PrintLoadStatus && PrintToExperts)
   {
      Print("TF Monitor | LOADED | first snapshot in ", FirstLoadDelaySeconds, " sec | ", _Symbol);
      TFM_LoadPrinted = true;
   }

   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   TFM_ReleaseEMAHandles();
}

void OnTimer()
{
   TFM_Run();
}

int OnCalculate(
   const int rates_total,
   const int prev_calculated,
   const datetime &time[],
   const double &open[],
   const double &high[],
   const double &low[],
   const double &close[],
   const long &tick_volume[],
   const long &volume[],
   const int &spread[]
)
{
   // Semua proses monitor dijalankan oleh OnTimer saja.
   // OnCalculate tidak scan agar indikator tidak berat di chart aktif.
   return(rates_total);
}
//+------------------------------------------------------------------+