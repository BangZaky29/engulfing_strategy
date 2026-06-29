## Plan: Strong-only M5 Execution with 4 Trigger Toggles

TL;DR - Keep the existing TF Monitor config toggles and update Filter C + detector logic so M5 execution only fires when H1+M15 show STRONG, while allowing any one enabled M5 trigger (Engulfing, ICT, DB, Pinbar) to shoot the order.

**Steps**
1. Confirm `.env` trigger toggles are the source of truth and stay enabled by default.
   - `.env` already contains `TFM_USE_ENGULFING`, `TFM_USE_MARUBOZU`, `TFM_USE_ICT`, `TFM_USE_PINBAR`, `TFM_USE_DOMINAN_BREAK`, `TFM_USE_MULTI_TRIGGER`.
   - No new per-timeframe env vars are needed because the same FilterCConfig is used for H1, M15, and M5.

2. Update `config/filter_c_config.py` defaults and comments if needed.
   - Ensure strong-age defaults reflect your requirement (H1 fresh/new and M15 max 3 bars after trigger).
   - Set `strong_m15_max_age` default to `3` if the requirement is max 3 candles after M15 trigger.
   - Keep the boolean toggles for all four triggers and `use_multi_trigger`.

3. Enforce STRONG-only execution in `strategies/engulfing/detector.py`.
   - In the Filter C section, block any M5 execution unless `tfm_result["status"] == "STRONG"`.
   - Keep H1/M15 info signal capture for DB/Pinbar/ICT/Engulfing, but require the strong status before setting `signal["is_confirmed"] = True` for M5.
   - If `cfg.filter_c_tfm_enabled` and `filter_c_blocking` are on, use `STRONG` as the gate; `VALID` / `EARLY` / `WAIT` / `LATE` should skip.

4. Use the existing trigger detection for M5 shooter signals.
   - `strategies/engulfing/filters_C/f1_triggers.py` already scans all enabled triggers and returns a combined source.
   - Confirm M5 execution uses `find_latest_trigger` output for M5, so any one enabled trigger is enough to shoot.
   - Do not require all four trigger types simultaneously on M5; allow minimal one enabled trigger to execute once H1+M15 are strong.

5. Keep H1/M15 monitoring logic in `strategies/engulfing/filters_C/f2_bias_logic.py`.
   - `validity_status()` already computes `STRONG` when H1/M15 are aligned and fresh.
   - Verify `h1_age <= strong_h1_max_age` and `m15_age <= strong_m15_max_age` are the correct fresh thresholds.
   - If needed, adjust `strong_m15_max_age` to `3`.

6. Validate the flow and save info signals.
   - `main.py` already stores H1/M15 info signals and executes only M5 target timeframe.
   - No major structural changes are needed there unless you want clearer logging around strong-only execution.

**Relevant files**
- `c:\codingVibes\mt5\engulfing\.env` — trigger toggle defaults and strong-age values.
- `c:\codingVibes\mt5\engulfing\config\filter_c_config.py` — filter toggle parsing and strong-age config.
- `c:\codingVibes\mt5\engulfing\strategies\engulfing\detector.py` — execution gating by TF monitor status.
- `c:\codingVibes\mt5\engulfing\strategies\engulfing\filters_C\f1_triggers.py` — trigger detection for Engulfing, ICT, DB, Pinbar.
- `c:\codingVibes\mt5\engulfing\strategies\engulfing\filters_C\f2_bias_logic.py` — H1/M15 strong/valid state logic.

**Verification**
1. Test with `.env` values all enabled and `FILTER_C_TFM_ENABLED=true`.
2. Confirm `check_tf_monitor()` returns `STRONG` only when H1/M15 are same direction and fresh.
3. Confirm `detect_engulfing()` on M5 only confirms a signal when `tfm_result["status"] == "STRONG"` and direction aligns.
4. Confirm M5 execution still happens when any one of the enabled triggers fires on M5.
5. Confirm H1/M15 info signals are still saved even when execution is blocked.

**Decisions**
- Keep global booleans and reuse existing env toggle flags for all TFs.
- Treat M5 trigger as the shooter: any one enabled trigger is enough, but H1+M15 must be STRONG.
- Use status `STRONG` as the execution gate, not `VALID` or `EARLY`.

**Further Considerations**
1. If you want separate H1/M15/M5 trigger toggle control later, add TF-specific env flags and pass them into `check_tf_monitor()`.
2. If you want M5 execution to require a “new” H1 signal rather than just fresh age, add explicit new-state checks in `TFMonitorStateManager`.
3. If you want the M5 shooter to also require `use_multi_trigger` on M5, that can be added as a second-stage rule in `get_trigger_state()`.
