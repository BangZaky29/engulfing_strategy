import pandas as pd
import numpy as np
import os

def detect_bullish_engulfing(df):
    c1_open, c1_close = df['open'], df['close']
    c2_open, c2_close = df['open'].shift(1), df['close'].shift(1)
    
    is_bullish_engulf = (
        (c2_close < c2_open) & # previous was bearish
        (c1_close > c1_open) & # current is bullish
        (c1_close > c2_open) & # current close above prev open
        (c1_open < c2_close)   # current open below prev close
    )
    return is_bullish_engulf

def detect_bearish_engulfing(df):
    c1_open, c1_close = df['open'], df['close']
    c2_open, c2_close = df['open'].shift(1), df['close'].shift(1)
    
    is_bearish_engulf = (
        (c2_close > c2_open) & # previous was bullish
        (c1_close < c1_open) & # current is bearish
        (c1_close < c2_open) & # current close below prev open
        (c1_open > c2_close)   # current open above prev close
    )
    return is_bearish_engulf

def detect_pinbar(df):
    body = abs(df['close'] - df['open'])
    total_range = df['high'] - df['low']
    
    # Avoid division by zero
    total_range = total_range.replace(0, 0.00001)
    
    upper_wick = df['high'] - df[['open', 'close']].max(axis=1)
    lower_wick = df[['open', 'close']].min(axis=1) - df['low']
    
    # bullish pinbar: long lower wick, small body
    bullish_pinbar = (lower_wick > 2 * body) & (upper_wick < body)
    # bearish pinbar: long upper wick, small body
    bearish_pinbar = (upper_wick > 2 * body) & (lower_wick < body)
    
    return bullish_pinbar, bearish_pinbar

def calculate_future_outcome(df, index, signal_type, distance):
    """
    Check if price reaches 1x and 2x distance before hitting SL (1x distance).
    Returns (hit_1x, hit_2x) as 1 or 0.
    """
    if distance <= 0.00001:
        return 0, 0
        
    entry_price = df.loc[index, 'close'] # Enter on close of trigger candle
    
    tp_1x = distance * 1.0
    tp_2x = distance * 2.0
    sl_dist = distance * 1.0 # Set SL to 1x distance
    
    if signal_type == 1: # Buy
        target_1x = entry_price + tp_1x
        target_2x = entry_price + tp_2x
        sl = entry_price - sl_dist
    else: # Sell
        target_1x = entry_price - tp_1x
        target_2x = entry_price - tp_2x
        sl = entry_price + sl_dist
        
    # Look ahead up to 120 hours (5 days)
    lookahead = min(120, len(df) - index - 1)
    if lookahead <= 0:
        return 0, 0
        
    future_data = df.iloc[index+1 : index+1+lookahead]
    
    hit_1x = 0
    hit_2x = 0
    
    for _, row in future_data.iterrows():
        high = row['high']
        low = row['low']
        
        if signal_type == 1: # Buy logic
            if low <= sl: 
                break # SL hit first
            if high >= target_1x: 
                hit_1x = 1
            if high >= target_2x: 
                hit_2x = 1
                break # Both targets hit, stop looking
        else: # Sell logic
            if high >= sl: 
                break # SL hit first
            if low <= target_1x: 
                hit_1x = 1
            if low <= target_2x: 
                hit_2x = 1
                break # Both targets hit, stop looking
            
    return hit_1x, hit_2x

def analyze_symbol(df, symbol):
    df = df.copy()
    df['dist_to_ema'] = abs(df['open'] - df['ema_20'])
    
    bull_eng = detect_bullish_engulfing(df)
    bear_eng = detect_bearish_engulfing(df)
    bull_pin, bear_pin = detect_pinbar(df)
    
    print(f"\n{'='*60}")
    print(f"=== Analysis for {symbol} ===")
    print(f"{'='*60}")
    print(f"Rincian Trigger yang Ditemukan:")
    print(f"  - Bullish Engulfing : {bull_eng.sum()} kali")
    print(f"  - Bearish Engulfing : {bear_eng.sum()} kali")
    print(f"  - Bullish Pinbar    : {bull_pin.sum()} kali")
    print(f"  - Bearish Pinbar    : {bear_pin.sum()} kali")
    
    df['signal'] = 0
    df.loc[bull_eng | bull_pin, 'signal'] = 1
    df.loc[bear_eng | bear_pin, 'signal'] = -1
    
    results = []
    
    for i in range(1, len(df)-1):
        if df.loc[i, 'signal'] != 0:
            sig = df.loc[i, 'signal']
            dist = df.loc[i, 'dist_to_ema']
            
            trigger_name = "Unknown"
            if bull_eng.iloc[i]: trigger_name = "Bullish Engulfing"
            elif bear_eng.iloc[i]: trigger_name = "Bearish Engulfing"
            elif bull_pin.iloc[i]: trigger_name = "Bullish Pinbar"
            elif bear_pin.iloc[i]: trigger_name = "Bearish Pinbar"
            
            w1x, w2x = calculate_future_outcome(df, i, sig, dist)
            results.append({
                'distance': dist, 
                'trigger_type': trigger_name,
                'win_1x': w1x,
                'win_2x': w2x
            })
                
    if not results:
        print(f"Tidak ada trigger yang ditemukan untuk {symbol}")
        return
        
    res_df = pd.DataFrame(results)
    
    try:
        # Group into 10 buckets
        res_df['dist_bucket'] = pd.qcut(res_df['distance'], q=10, duplicates='drop')
        
        # Calculate summary
        summary = pd.DataFrame()
        summary['Total_Triggers'] = res_df.groupby('dist_bucket', observed=True).size()
        summary['Win_1x_Count'] = res_df.groupby('dist_bucket', observed=True)['win_1x'].sum()
        summary['Win_1x_%'] = (res_df.groupby('dist_bucket', observed=True)['win_1x'].mean() * 100).round(2)
        summary['Win_2x_Count'] = res_df.groupby('dist_bucket', observed=True)['win_2x'].sum()
        summary['Win_2x_%'] = (res_df.groupby('dist_bucket', observed=True)['win_2x'].mean() * 100).round(2)
        
        print("\nDetail Probabilitas Berdasarkan Jarak (TP 1x dan TP 2x dari Jarak):")
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 1000)
        print(summary)
        
    except ValueError as e:
        print(f"Could not calculate quantiles for {symbol}: {e}")

def main():
    csv_path = os.path.join(os.path.dirname(__file__), "historical_data_H1.csv")
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"File {csv_path} not found.")
        return
        
    print("Dataset loaded successfully. Analyzing...")
    symbols = df['symbol'].unique()
    for sym in symbols:
        analyze_symbol(df[df['symbol'] == sym].reset_index(drop=True), sym)

if __name__ == "__main__":
    main()
