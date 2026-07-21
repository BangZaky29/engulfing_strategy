import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone
import os

def get_data(symbol, timeframe, date_from, date_to):
    rates = mt5.copy_rates_range(symbol, timeframe, date_from, date_to)
    if rates is None or len(rates) == 0:
        print(f"Failed to get data for {symbol}, error code =", mt5.last_error())
        return None
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Calculate EMA 20 based on close price
    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['symbol'] = symbol
    return df

def main():
    print("Initializing MetaTrader 5 connection...")
    if not mt5.initialize():
        print("initialize() failed, error code =", mt5.last_error())
        return

    print("Connected to MT5:", mt5.terminal_info().name)
    
    symbols = ["XAUUSD", "NASDAQ-100", "BTC"]
    timeframe = mt5.TIMEFRAME_H1
    
    # Set date range: January 2025 to July 2026 to get a robust dataset
    timezone_utc = timezone.utc
    date_from = datetime(2025, 1, 1, tzinfo=timezone_utc)
    date_to = datetime.now(timezone_utc)
    
    all_data = []
    for symbol in symbols:
        # Check if symbol exists and is visible in Market Watch
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            print(f"{symbol} not found, can not call symbol_info()")
            continue
        
        if not symbol_info.visible:
            print(f"{symbol} is not visible, trying to switch on")
            if not mt5.symbol_select(symbol, True):
                print(f"symbol_select({symbol}) failed, error =", mt5.last_error())
                continue
                
        print(f"Fetching data for {symbol}...")
        df = get_data(symbol, timeframe, date_from, date_to)
        if df is not None:
            all_data.append(df)
            print(f"Got {len(df)} rows for {symbol}")
            
    mt5.shutdown()
    
    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        csv_path = os.path.join(os.path.dirname(__file__), "historical_data_H1.csv")
        final_df.to_csv(csv_path, index=False)
        print(f"Data successfully saved to {csv_path}")
    else:
        print("No data extracted.")

if __name__ == "__main__":
    main()
