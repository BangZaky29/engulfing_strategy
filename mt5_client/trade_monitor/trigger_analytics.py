# =====================================================
# mt5_client/trade_monitor/trigger_analytics.py
# Agregasi trigger analytics dari floating snapshots.
# =====================================================

from datetime import datetime, timezone

from database.supabase_client import get_supabase


def build_and_upsert_trigger_analytics(
    ticket: int,
    info: dict,
    exit_time,
    total_profit: float,
    result_str: str,
    trigger_type: str,
) -> dict:
    """
    Agregasi trigger analytics dari floating snapshots, upsert ke Supabase.
    Returns dict dengan floating metrics yang dibutuhkan analytics dashboard.
    """
    trade_date = datetime.now(timezone.utc).date().isoformat()

    # ambil max & sum negatif floating sebelum profit terjadi:
    # definisi awal (tanpa exit_time phase join): gunakan window sampai exit_time selesai.
    # floating snapshots disimpan dengan snapshot_time; exit_time bisa berupa epoch seconds dari deals.
    # jadi kita filter snapshot_time <= exit_time_utc.
    exit_dt = None
    if exit_time:
        try:
            exit_dt = datetime.fromtimestamp(exit_time, tz=timezone.utc)
        except:
            exit_dt = None

    max_neg = None
    sum_neg = None
    max_neg_pct = None
    max_neg_distance_points = None
    max_neg_distance_price_points = None
    sum_neg_distance_points = 0.0

    # MFE positif (mirror dari MAE negatif)
    max_pos = None
    sum_pos = None
    max_pos_pct = None
    max_pos_distance_points = None
    max_pos_distance_price_points = None
    sum_pos_distance_points = 0.0

    if exit_dt:
        # query langsung dari Supabase (lebih sederhana di tahap awal)
        try:
            supabase = get_supabase()
            resp = (
                supabase.table("trade_floating_snapshots")
                .select(
                    "floating_profit_usd,floating_pct_from_entry,snapshot_time,entry_price,current_price,point,distance_price_units"
                )
                .eq("ticket_id", ticket)
                .lte("snapshot_time", exit_dt.isoformat())
                .execute()
            )
            rows = resp.data or []
            neg_rows = [r for r in rows if float(r.get("floating_profit_usd") or 0.0) < 0.0]
            pos_rows = [r for r in rows if float(r.get("floating_profit_usd") or 0.0) > 0.0]

            max_neg_distance_points = None
            max_neg_distance_price_points = None
            sum_neg_distance_points = 0.0

            if neg_rows:
                neg_vals = [float(r.get("floating_profit_usd") or 0.0) for r in neg_rows]
                neg_pcts = [float(r.get("floating_pct_from_entry") or 0.0) for r in neg_rows]
                max_neg_val = min(neg_vals)
                max_neg = abs(max_neg_val)
                sum_neg = sum(abs(v) for v in neg_vals)
                max_neg_pct = max(neg_pcts) if neg_pcts else None


                dist_points_list: list[float] = []
                for r in neg_rows:
                    try:
                        ep = r.get("entry_price")
                        cp = r.get("current_price")
                        pt = r.get("point")
                        if ep is None or cp is None or pt in (None, 0):
                            continue
                        ep_f = float(ep)
                        cp_f = float(cp)
                        pt_f = float(pt)
                        if pt_f == 0:
                            continue
                        d_price = abs(cp_f - ep_f)
                        d_points = d_price / pt_f
                        dist_points_list.append(d_points)
                    except:
                        continue

                if dist_points_list:
                    max_neg_distance_points = max(dist_points_list)
                    sum_neg_distance_points = sum(dist_points_list)

                    # "distance price points" diset sebagai distance price (bukan points)
                    # supaya nama kolomnya jelas: max distance price dalam harga units.
                    max_neg_distance_price_points = max(
                        (abs(float(r.get("current_price")) - float(r.get("entry_price"))))
                        for r in neg_rows
                        if r.get("entry_price") is not None and r.get("current_price") is not None
                    )

            # ─── BARU: mirror logic buat floating positif (MFE) ───
            max_pos = None
            sum_pos = None
            max_pos_pct = None
            max_pos_distance_points = None
            max_pos_distance_price_points = None
            sum_pos_distance_points = 0.0

            if pos_rows:
                pos_vals = [float(r.get("floating_profit_usd") or 0.0) for r in pos_rows]
                pos_pcts = [float(r.get("floating_pct_from_entry") or 0.0) for r in pos_rows]
                max_pos = max(pos_vals)
                sum_pos = sum(pos_vals)
                max_pos_pct = max(pos_pcts) if pos_pcts else None

                dist_points_list_pos: list[float] = []
                for r in pos_rows:
                    try:
                        ep = r.get("entry_price")
                        cp = r.get("current_price")
                        pt = r.get("point")
                        if ep is None or cp is None or pt in (None, 0):
                            continue
                        d_price = abs(float(cp) - float(ep))
                        dist_points_list_pos.append(d_price / float(pt))
                    except:
                        continue

                if dist_points_list_pos:
                    max_pos_distance_points = max(dist_points_list_pos)
                    sum_pos_distance_points = sum(dist_points_list_pos)
                    max_pos_distance_price_points = max(
                        abs(float(r.get("current_price")) - float(r.get("entry_price")))
                        for r in pos_rows
                        if r.get("entry_price") is not None and r.get("current_price") is not None
                    )
            # ─────────────────────────────────────────────────────

        except Exception as ex:
            print(f"⚠️ Gagal query trade_floating_snapshots untuk #{ticket}: {ex}")

    # insert/update agregat (UPSERT per day+symbol+trigger+mode)
    # Ambil tf_execute dan tf_monitor dari tracker info
    agg_tf_execute = info.get("tf", "M5")
    agg_tf_monitor = info.get("tf_monitor", "M15")
    try:
        supabase = get_supabase()

        # Baca row existing untuk akumulasi (bukan overwrite)
        existing_row = None
        try:
            resp = (
                supabase.table("trade_trigger_analytics")
                .select("total_trades,total_profit_count,total_loss_count,total_profit_usd,total_loss_usd,max_negative_floating_before_profit_usd,max_negative_floating_before_profit_pct,sum_negative_floating_before_profit_usd,max_negative_distance_points,max_negative_distance_price_points,sum_negative_distance_points,max_positive_floating_before_loss_usd,max_positive_floating_before_loss_pct,sum_positive_floating_before_loss_usd,max_positive_distance_points,max_positive_distance_price_points,sum_positive_distance_points")
                .eq("trade_date", trade_date)
                .eq("symbol", info["symbol"])
                .eq("trigger_type", trigger_type)
                .eq("mode", info["mode"])
                .eq("tf_execute", agg_tf_execute)
                .eq("tf_monitor", agg_tf_monitor)
                .limit(1)
                .execute()
            )
            if resp.data and len(resp.data) > 0:
                existing_row = resp.data[0]
        except Exception:
            existing_row = None

        # Akumulasi dari row existing + trade baru
        prev_total = int(existing_row.get("total_trades") or 0) if existing_row else 0
        prev_profit_count = int(existing_row.get("total_profit_count") or 0) if existing_row else 0
        prev_loss_count = int(existing_row.get("total_loss_count") or 0) if existing_row else 0
        prev_profit_usd = float(existing_row.get("total_profit_usd") or 0.0) if existing_row else 0.0
        prev_loss_usd = float(existing_row.get("total_loss_usd") or 0.0) if existing_row else 0.0

        total_trades = prev_total + 1
        total_profit_count = prev_profit_count + (1 if result_str == "PROFIT" else 0)
        total_loss_count = prev_loss_count + (1 if result_str == "LOSS" else 0)
        total_profit_usd = prev_profit_usd + (float(total_profit) if result_str == "PROFIT" else 0.0)
        total_loss_usd = prev_loss_usd + (abs(float(total_profit)) if result_str == "LOSS" else 0.0)

        probability_profit = float(total_profit_count) / float(total_trades) if total_trades > 0 else 0.0

        # Untuk floating metrics, ambil max/sum terbesar dari existing vs current
        prev_max_neg_usd = float(existing_row.get("max_negative_floating_before_profit_usd") or 0.0) if existing_row else 0.0
        prev_max_neg_pct = float(existing_row.get("max_negative_floating_before_profit_pct") or 0.0) if existing_row else 0.0
        prev_sum_neg_usd = float(existing_row.get("sum_negative_floating_before_profit_usd") or 0.0) if existing_row else 0.0
        prev_max_dist_pts = float(existing_row.get("max_negative_distance_points") or 0.0) if existing_row else 0.0
        prev_max_dist_price = float(existing_row.get("max_negative_distance_price_points") or 0.0) if existing_row else 0.0
        prev_sum_dist_pts = float(existing_row.get("sum_negative_distance_points") or 0.0) if existing_row else 0.0

        # ─── BARU: prev untuk positif (MFE) ───
        prev_max_pos_usd = float(existing_row.get("max_positive_floating_before_loss_usd") or 0.0) if existing_row else 0.0
        prev_max_pos_pct = float(existing_row.get("max_positive_floating_before_loss_pct") or 0.0) if existing_row else 0.0
        prev_sum_pos_usd = float(existing_row.get("sum_positive_floating_before_loss_usd") or 0.0) if existing_row else 0.0
        prev_max_pos_dist_pts = float(existing_row.get("max_positive_distance_points") or 0.0) if existing_row else 0.0
        prev_max_pos_dist_price = float(existing_row.get("max_positive_distance_price_points") or 0.0) if existing_row else 0.0
        prev_sum_pos_dist_pts = float(existing_row.get("sum_positive_distance_points") or 0.0) if existing_row else 0.0

        cur_max_neg = float(max_neg) if max_neg is not None else 0.0
        cur_max_neg_pct = float(max_neg_pct) if max_neg_pct is not None else 0.0
        cur_sum_neg = float(sum_neg) if sum_neg is not None else 0.0
        cur_max_dist_pts = float(max_neg_distance_points) if max_neg_distance_points is not None else 0.0
        cur_max_dist_price = float(max_neg_distance_price_points) if max_neg_distance_price_points is not None else 0.0
        cur_sum_dist_pts = float(sum_neg_distance_points) if sum_neg_distance_points is not None else 0.0

        # ─── BARU: current untuk positif (MFE) ───
        cur_max_pos = float(max_pos) if max_pos is not None else 0.0
        cur_max_pos_pct = float(max_pos_pct) if max_pos_pct is not None else 0.0
        cur_sum_pos = float(sum_pos) if sum_pos is not None else 0.0
        cur_max_pos_dist_pts = float(max_pos_distance_points) if max_pos_distance_points is not None else 0.0
        cur_max_pos_dist_price = float(max_pos_distance_price_points) if max_pos_distance_price_points is not None else 0.0
        cur_sum_pos_dist_pts = float(sum_pos_distance_points) if sum_pos_distance_points is not None else 0.0

        agg_payload = {
            "trade_date": trade_date,
            "symbol": info["symbol"],
            "trigger_type": trigger_type,
            "mode": info["mode"],
            "tf_execute": agg_tf_execute,
            "tf_monitor": agg_tf_monitor,
            "total_trades": total_trades,
            "total_profit_count": total_profit_count,
            "total_loss_count": total_loss_count,
            "total_profit_usd": total_profit_usd,
            "total_loss_usd": total_loss_usd,
            "max_negative_floating_before_profit_usd": max(prev_max_neg_usd, cur_max_neg) if (prev_max_neg_usd or cur_max_neg) else None,
            "max_negative_floating_before_profit_pct": max(prev_max_neg_pct, cur_max_neg_pct) if (prev_max_neg_pct or cur_max_neg_pct) else None,
            "sum_negative_floating_before_profit_usd": prev_sum_neg_usd + cur_sum_neg,

            "max_negative_distance_points": max(prev_max_dist_pts, cur_max_dist_pts) if (prev_max_dist_pts or cur_max_dist_pts) else None,
            "max_negative_distance_price_points": max(prev_max_dist_price, cur_max_dist_price) if (prev_max_dist_price or cur_max_dist_price) else None,
            "sum_negative_distance_points": prev_sum_dist_pts + cur_sum_dist_pts,

            # ─── BARU: field positif (MFE) ───
            "max_positive_floating_before_loss_usd": max(prev_max_pos_usd, cur_max_pos) if (prev_max_pos_usd or cur_max_pos) else None,
            "max_positive_floating_before_loss_pct": max(prev_max_pos_pct, cur_max_pos_pct) if (prev_max_pos_pct or cur_max_pos_pct) else None,
            "sum_positive_floating_before_loss_usd": prev_sum_pos_usd + cur_sum_pos,
            "max_positive_distance_points": max(prev_max_pos_dist_pts, cur_max_pos_dist_pts) if (prev_max_pos_dist_pts or cur_max_pos_dist_pts) else None,
            "max_positive_distance_price_points": max(prev_max_pos_dist_price, cur_max_pos_dist_price) if (prev_max_pos_dist_price or cur_max_pos_dist_price) else None,
            "sum_positive_distance_points": prev_sum_pos_dist_pts + cur_sum_pos_dist_pts,

            "probability_profit": probability_profit,
        }

        supabase.table("trade_trigger_analytics").upsert(
            agg_payload,
            on_conflict="trade_date,symbol,trigger_type,mode,tf_execute,tf_monitor",
        ).execute()
    except Exception as ex:
        print(f"⚠️ Gagal insert trade_trigger_analytics untuk #{ticket}: {ex}")

    return {
        "max_neg": max_neg,
        "sum_neg": sum_neg,
        "max_neg_pct": max_neg_pct,
        "max_neg_distance_points": max_neg_distance_points,
        "max_neg_distance_price_points": max_neg_distance_price_points,
        "sum_neg_distance_points": sum_neg_distance_points,
        "max_pos": max_pos,
        "sum_pos": sum_pos,
        "max_pos_pct": max_pos_pct,
        "max_pos_distance_points": max_pos_distance_points,
        "max_pos_distance_price_points": max_pos_distance_price_points,
        "sum_pos_distance_points": sum_pos_distance_points,
    }
