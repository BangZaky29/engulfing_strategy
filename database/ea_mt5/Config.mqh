#ifndef TFM_CONFIG_MQH
#define TFM_CONFIG_MQH

#define TFM_TF_COUNT 3
#define TFM_INDEX_H1  0
#define TFM_INDEX_M15 1
#define TFM_INDEX_M5  2

#define TFM_DIR_NONE  0
#define TFM_DIR_BUY   1
#define TFM_DIR_SELL -1
#define TFM_DIR_MIXED 2

ENUM_TIMEFRAMES TFM_TFList[TFM_TF_COUNT] =
{
   PERIOD_H1,
   PERIOD_M15,
   PERIOD_M5
};

int TFM_EMAHandle[TFM_TF_COUNT];

struct TFM_State
{
   int      direction;
   string   source;
   datetime time;
   double   rangePoints;
};

TFM_State TFM_H1State;
TFM_State TFM_M15State;
TFM_State TFM_M5State;

TFM_State TFM_LastNotifiedH1State;
TFM_State TFM_LastNotifiedM15State;
TFM_State TFM_LastNotifiedM5State;

string TFM_LastSnapshot = "";
string TFM_LastEventKey = "";
bool   TFM_HasSnapshot  = false;
bool   TFM_IsRunning    = false;
datetime TFM_StartTime  = 0;
datetime TFM_LastClosedTime[TFM_TF_COUNT];
bool   TFM_StateReady[TFM_TF_COUNT];
bool   TFM_LoadPrinted = false;
bool   TFM_WaitDataPrinted = false;

bool   TFM_H1NewMarker  = false;
bool   TFM_M15NewMarker = false;
bool   TFM_M5NewMarker  = false;

// =====================================================
// TF MONITOR
// =====================================================
input group "=== TF MONITOR ===";
input int  MonitorTimerSeconds = 3;
input int  TriggerLookbackBars = 200;
input bool NotifyOnFirstLoad   = true;
input int  FirstLoadDelaySeconds = 3;
input bool PushOnFirstLoad      = false;
input bool PrintLoadStatus      = true;

// =====================================================
// EMA FILTER GLOBAL
// =====================================================
input group "=== EMA FILTER GLOBAL ===";
input bool UseEMAFilter = true;
input int  EMAPeriod = 20;

// =====================================================
// NOTIFICATION GLOBAL
// =====================================================
input group "=== NOTIFICATION GLOBAL ===";
input bool EnablePushNotification = true;
input bool PrintToExperts = true;

// =====================================================
// H1 BIAS
// =====================================================
// H1 sekarang memakai trigger yang sama dengan M15 dan M5.
// LBC H1 dihapus agar semua timeframe memakai aturan sinyal yang sama.

// =====================================================
// MULTI TRIGGER
// =====================================================
input group "=== MULTI TRIGGER ===";
input bool UseMultiTrigger = true;

// =====================================================
// TRIGGER 01 - ENGULFING
// Master logic mengikuti Scanner terakhir.
// =====================================================
input group "=== TRIGGER 01 - ENGULFING ===";
input bool UseTrigger01_Engulfing = true;

// =====================================================
// TRIGGER 02 - MARUBOZU
// Default mengikuti Scanner terakhir.
// =====================================================
input group "=== TRIGGER 02 - MARUBOZU ===";
input bool   UseTrigger02_Marubozu = true;
input int    MarubozuWickBufferPoints = 150;
input int    MarubozuCompareCandles = 3;
input double MarubozuRangeMultiplier = 2.0;

// =====================================================
// TRIGGER 03 - ICT
// =====================================================
input group "=== TRIGGER 03 - ICT ===";
input bool UseTrigger03_ICT = true;

// =====================================================
// TRIGGER 04 - PINBAR
// Default mengikuti Scanner terakhir.
// =====================================================
input group "=== TRIGGER 04 - PINBAR ===";
input bool   UseTrigger04_Pinbar = true;
input double PinbarWickBodyMultiplier = 4.0;
input int    PinbarMinRangePoints = 600;

// =====================================================
// TRIGGER 05 - DOMINAN BREAK
// DB = candle close/body break High/Low candle Master.
// Break valid minimal candle ke-3 setelah Master.
// Default Max = 20.
// =====================================================
input group "=== TRIGGER 05 - DOMINAN BREAK ===";
input bool UseTrigger05_DominanBreak = true;
input int  DominanBreakMinCandles = 3;
input int  DominanBreakMaxCandles = 20;
input int  DominanBreakBufferPoints = 0;

#endif