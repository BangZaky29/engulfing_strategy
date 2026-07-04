from config.execution_config import ExecutionConfig


def test_sl_percentage_places_at_tail_for_buy():
    cfg = ExecutionConfig(sl_pct=100.0)
    sl_price = cfg.calculate_sl_price(
        entry_price=100.0,
        current_close=90.0,
        current_low=80.0,
        current_high=100.0,
        action_str="BUY",
    )
    assert sl_price == 80.0


def test_tp_percentage_uses_distance_to_sl():
    cfg = ExecutionConfig(tp_pct=50.0)
    tp_price = cfg.calculate_tp_price(
        entry_price=100.0,
        sl_price=80.0,
        action_str="BUY",
    )
    assert tp_price == 90.0
