//+------------------------------------------------------------------+
//|                     Multi-Timeframe ZigZagColor                  |
//+------------------------------------------------------------------+
#property indicator_chart_window
#property indicator_buffers 3
#property indicator_plots   1
#property version "1.03"

#property indicator_label1  "ZigZag"
#property indicator_type1   DRAW_COLOR_ZIGZAG
#property indicator_color1  clrLightCyan, clrCrimson, clrNONE
#property indicator_width1  2

#resource "\\Indicators\\Examples\\ZigzagColor.ex5"

input ENUM_TIMEFRAMES CustomPeriod = PERIOD_CURRENT;
input int    Inp_NumberOfBars = 500;  // Max lookback
input int    InpDepth     = 12;
input int    InpDeviation = 5;
input int    InpBackstep  = 3;


double zigzaghigh[];
double zigzaglow[];
double zigzagcol[];
double zigzaghigh_data[];
double zigzaglow_data[];
double zigzagcol_data[];
datetime time_htf[];

int zz_handle = INVALID_HANDLE;

int ExtRecalc=3; // Number of recent bars to recalculate when the indicator updates

//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int OnInit()
  {
   SetIndexBuffer(0, zigzaghigh, INDICATOR_DATA);
   SetIndexBuffer(1, zigzaglow,  INDICATOR_DATA);
   SetIndexBuffer(2, zigzagcol, INDICATOR_COLOR_INDEX);

   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, 0.0);
   IndicatorSetString(INDICATOR_SHORTNAME, "MTF ZigZagColor");

   zz_handle = iCustom(_Symbol, CustomPeriod, "::Indicators\\Examples\\ZigzagColor", InpDepth, InpDeviation, InpBackstep);
   if(zz_handle == INVALID_HANDLE)
     {
      Print("Failed to create ZigZagColor handle: ", GetLastError());
      return INIT_FAILED;
     }

   // HTF buffers
   ArraySetAsSeries(time_htf, true);
   ArraySetAsSeries(zigzaghigh_data, true);
   ArraySetAsSeries(zigzaglow_data, true);

   ChartNavigate(0, CHART_END, 0);

   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| Custom indicator deinitialization function                        |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(zz_handle != INVALID_HANDLE)
      IndicatorRelease(zz_handle);

   Comment("");
  }

//+------------------------------------------------------------------+
//| Custom indicator iteration function                              |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
   if(rates_total < 1)
      return rates_total;

   if(CustomPeriod == PERIOD_CURRENT)
     {
      int start=0;
      int to_copy = 0;

      if(prev_calculated == 0)
        {
         ArrayInitialize(zigzaghigh, EMPTY_VALUE);
         ArrayInitialize(zigzaglow, EMPTY_VALUE);

         to_copy = rates_total;
         start = InpDepth-1;
        }
      else
        {
         int i = rates_total-1;
         start = i;
         while(i>0)
         {
            if(zigzaghigh[i] != 0 || zigzaglow[i] != 0)
              {
               break;
              }
            i--;
         }
        
         start = i; // idx of last established extremum
         to_copy = rates_total - start;
        }

      if(CopyBuffer(zz_handle, 0, 0, to_copy, zigzaghigh) <= 0)
        {
         Print("Error copying peak buffer: ", GetLastError());
         return rates_total;
        }

      if(CopyBuffer(zz_handle, 1, 0, to_copy, zigzaglow) <= 0)
        {
         Print("Error copying bottom buffer: ", GetLastError());
         return rates_total;
        }

      if(CopyBuffer(zz_handle, 2, 0, to_copy, zigzagcol) <= 0)
        {
         Print("Error copying color buffer: ", GetLastError());
         return rates_total;
        }

     }
   else if(CustomPeriod < ChartPeriod(ChartID()))
     {

      for(int i = 0; i < rates_total && !IsStopped(); i++)
        {
         zigzaghigh[i] = EMPTY_VALUE;
         zigzaglow[i] = EMPTY_VALUE;
        }

      Comment("Please use a higher timeframe than the chart timeframe in the input section");

     }
   else
     {
      int htf_bars = iBars(_Symbol, CustomPeriod);

      if(prev_calculated == 0)
        {
         ArrayInitialize(zigzaghigh, 0.0);
         ArrayInitialize(zigzaglow, 0.0);

         ArrayResize(zigzaghigh_data, htf_bars);
         ArrayResize(zigzaglow_data, htf_bars);
         ArrayResize(zigzagcol_data, htf_bars);
        }

      if(CopyBuffer(zz_handle, 0, 0, htf_bars, zigzaghigh_data) <= 0)
         return rates_total;
      if(CopyBuffer(zz_handle, 1, 0, htf_bars, zigzaglow_data) <= 0)
         return rates_total;
      if(CopyBuffer(zz_handle, 2, 0, htf_bars, zigzagcol_data) <= 0)
         return rates_total;

      int start = prev_calculated == 0 ? 0 : rates_total - Inp_NumberOfBars - 1;

      for(int i = start; i < rates_total; i++)
        {
         int shift = iBarShift(_Symbol, CustomPeriod, time[i], false);

         if(shift != -1)
           {
            zigzaghigh[i] = zigzaghigh_data[shift];
            zigzaglow[i] = zigzaglow_data[shift];
            zigzagcol[i] = zigzaghigh[i] > zigzaglow[i] ? 0 : 1;
           }
        }
     }

   return rates_total;
  }

  
  