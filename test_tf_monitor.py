import sys
import os
from datetime import datetime, timezone, timedelta

# Add workspace directory to python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from config.filter_c_config import FilterCConfig
from strategies.engulfing.filters_C.f4_state_manager import TFMState, DIR_BUY, DIR_SELL
from strategies.engulfing.filters_C.f2_bias_logic import validity_status

def create_candles(count: int, start_time: datetime, tf_minutes: int) -> list[dict]:
    candles = []
    for i in range(count):
        t = start_time + timedelta(minutes=i * tf_minutes)
        candles.append({
            "open": 2000.0,
            "high": 2010.0,
            "low": 1990.0,
            "close": 2005.0 if i % 2 == 0 else 1995.0,
            "time": t
        })
    return candles

def main():
    cfg = FilterCConfig()
    cfg.strong_h1_max_age = 0
    cfg.strong_m15_max_age = 3
    cfg.use_ema_filter = True

    base_time = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)
    
    h1_candles = create_candles(10, base_time, 60)
    m15_candles = create_candles(10, base_time, 15)
    m5_candles = create_candles(10, base_time, 5)

    h1_ema = [1900.0] * 10
    m15_ema = [1900.0] * 10

    # Test Case 1: H1 age = 0, M15 age = 1, M5 age = 0 (All BUY, all Trend)
    h1_state = TFMState(direction=DIR_BUY, source="Engulfing", time=h1_candles[-1]["time"])
    m15_state = TFMState(direction=DIR_BUY, source="Engulfing", time=m15_candles[-2]["time"])
    m5_state = TFMState(direction=DIR_BUY, source="Engulfing", time=m5_candles[-1]["time"])

    status = validity_status(
        h1_state, m15_state, m5_state,
        h1_candles, m15_candles, m5_candles,
        h1_ema, m15_ema,
        cfg
    )
    print(f"Test Case 1 (H1=0, M15=1, M5=0): expected 'STRONG', got '{status}'")
    assert status == "STRONG", f"Expected STRONG, got {status}"

    # Test Case 2: H1 age = 0, M15 age = 1, M5 age = 1 (All BUY, all Trend)
    m5_state_old = TFMState(direction=DIR_BUY, source="Engulfing", time=m5_candles[-2]["time"])
    
    status_2 = validity_status(
        h1_state, m15_state, m5_state_old,
        h1_candles, m15_candles, m5_candles,
        h1_ema, m15_ema,
        cfg
    )
    print(f"Test Case 2 (H1=0, M15=1, M5=1): expected 'VALID', got '{status_2}'")
    assert status_2 == "VALID", f"Expected VALID, got {status_2}"

    # Test Case 3: H1 age = 0, M15 age = 4, M5 age = 0 (All BUY, all Trend)
    m15_state_old = TFMState(direction=DIR_BUY, source="Engulfing", time=m15_candles[-5]["time"])
    status_3 = validity_status(
        h1_state, m15_state_old, m5_state,
        h1_candles, m15_candles, m5_candles,
        h1_ema, m15_ema,
        cfg
    )
    print(f"Test Case 3 (H1=0, M15=4, M5=0): expected 'VALID', got '{status_3}'")
    assert status_3 == "VALID", f"Expected VALID, got {status_3}"

    # Test Case 4: H1 age = 1, M15 age = 1, M5 age = 0 (All BUY, all Trend)
    h1_state_old = TFMState(direction=DIR_BUY, source="Engulfing", time=h1_candles[-2]["time"])
    status_4 = validity_status(
        h1_state_old, m15_state, m5_state,
        h1_candles, m15_candles, m5_candles,
        h1_ema, m15_ema,
        cfg
    )
    print(f"Test Case 4 (H1=1, M15=1, M5=0): expected 'VALID', got '{status_4}'")
    assert status_4 == "VALID", f"Expected VALID, got {status_4}"

    # Test Case 5: H1 age = 0, M15 age = 1, M5 age = 0 but M5 is SELL (opposite direction)
    m5_state_opposite = TFMState(direction=DIR_SELL, source="Engulfing", time=m5_candles[-1]["time"])
    status_5 = validity_status(
        h1_state, m15_state, m5_state_opposite,
        h1_candles, m15_candles, m5_candles,
        h1_ema, m15_ema,
        cfg
    )
    print(f"Test Case 5 (H1=0, M15=1, M5=0 opposite): expected 'VALID', got '{status_5}'")
    assert status_5 == "VALID", f"Expected VALID, got {status_5}"

    print("All test cases passed successfully!")

if __name__ == "__main__":
    main()
