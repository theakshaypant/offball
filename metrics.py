import math

import numpy as np
import pandas as pd

from constants import SPEED_ZONE_BINS, SPEED_ZONE_LABELS, SPEED_ZONE_COLORS
from constants import HR_ZONE_LABELS, HR_ZONE_COLORS, HR_ZONE_MULTIPLIERS
from constants import (
    STOPPAGE_MAX_DURATION_S,
    STOPPAGE_MIN_EXTENT_M, STOPPAGE_DISPLACEMENT_RATIO,
    STOPPAGE_HULL_MARGIN_M, STOPPAGE_OUTER_THRESHOLD,
)
from utils import fmt_time, fmt_pace


def detect_stoppages(df):
    """
    Detect ball-retrieval stoppages using V-shape + convex hull spatial analysis.

    A stoppage is detected when the player makes an out-and-back trip to the
    edge of the session GPS footprint (convex hull boundary). Speed is
    irrelevant — only the spatial V-shape pattern matters.

    Algorithm:
    1. Project GPS to local metres and compute the session convex hull.
    2. Find contiguous near-edge runs (signed distance to hull > -HULL_MARGIN).
       Each run's peak (closest point to the hull) is the candidate V-shape tip.
    3. Walk backward from each run's start (and forward from its end) until the
       player is clearly back inside the hull (signed_dist < -OUTER_THRESHOLD *
       HULL_MARGIN_M). This bounds the V-shape geometrically with no fixed window.
    4. If the segment is an out-and-back (low displacement/distance ratio) and
       the tip is far enough from the start (≥ MIN_EXTENT_M), mark as stoppage.

    Adds 'is_in_play' boolean column (False = out-of-play). Returns modified df.
    """
    try:
        from scipy.spatial import ConvexHull
    except ImportError:
        df = df.copy()
        df['is_in_play'] = True
        return df

    df = df.copy()
    df['is_in_play'] = True

    if len(df) < 50:
        return df

    # Project lat/lon to local metres (equirectangular approximation)
    mean_lat = df['lat'].mean()
    m_per_deg_lon = 111320.0 * math.cos(math.radians(mean_lat))
    x = (df['lon'].values - df['lon'].mean()) * m_per_deg_lon
    y = (df['lat'].values - df['lat'].mean()) * 111320.0
    coords_m = np.column_stack([x, y])

    try:
        hull = ConvexHull(coords_m)
    except Exception:
        return df

    # Signed distance to hull boundary for each point.
    # hull.equations rows: [a, b, c] with a·x + b·y + c ≤ 0 for interior.
    # Taking max over all faces: ~0 = on boundary, negative = inside hull.
    signed_dists = (hull.equations[:, :2] @ coords_m.T + hull.equations[:, 2:3]).max(axis=0)

    elapsed   = df['elapsed_s'].values
    dist_m    = df['dist_m'].values
    near_edge = signed_dists > -STOPPAGE_HULL_MARGIN_M

    if not near_edge.any():
        return df

    # Find each contiguous near-edge run independently.
    # Each run = one candidate episode (centred on the run's peak).
    transitions = np.diff(near_edge.astype(int), prepend=0, append=0)
    run_starts  = np.where(transitions ==  1)[0]
    run_ends    = np.where(transitions == -1)[0]

    marked = np.zeros(len(df), dtype=bool)
    outer_thresh = -STOPPAGE_OUTER_THRESHOLD * STOPPAGE_HULL_MARGIN_M
    n = len(df)

    for rs, re in zip(run_starts, run_ends):
        # Walk backward from the run's start to find where the player was
        # clearly inside the hull before this near-edge excursion
        v_start = rs
        for j in range(rs - 1, max(0, rs - 600), -1):
            if signed_dists[j] < outer_thresh:
                v_start = j + 1
                break

        # Walk forward from the run's end to find where the player returns
        # clearly inside the hull after this near-edge excursion
        v_end = re - 1
        for j in range(re, min(n, re + 600)):
            if signed_dists[j] < outer_thresh:
                v_end = j - 1
                break

        if v_end <= v_start or (v_end - v_start) < 4:
            continue

        seg_mask = np.zeros(n, dtype=bool)
        seg_mask[v_start:v_end + 1] = True

        duration = elapsed[v_end] - elapsed[v_start]
        if duration > STOPPAGE_MAX_DURATION_S:
            continue

        seg_x = x[seg_mask]
        seg_y = y[seg_mask]

        # V-shape check: displacement from start to end vs total distance
        displacement = math.sqrt((seg_x[-1] - seg_x[0])**2 + (seg_y[-1] - seg_y[0])**2)
        total_dist   = dist_m[seg_mask].sum()
        if total_dist < 1 or displacement / total_dist > STOPPAGE_DISPLACEMENT_RATIO:
            continue

        # Minimum extent: the tip must be at least STOPPAGE_MIN_EXTENT_M from start
        dists_from_start = np.sqrt((seg_x - seg_x[0])**2 + (seg_y - seg_y[0])**2)
        if dists_from_start.max() < STOPPAGE_MIN_EXTENT_M:
            continue

        marked[seg_mask] = True

    df.loc[df.index[marked], 'is_in_play'] = False
    return df


def compute_stoppages(df):
    """Return list of stoppage event dicts from a df with 'is_in_play' column."""
    if 'is_in_play' not in df.columns:
        return []

    in_play  = df['is_in_play'].values.astype(int)
    elapsed  = df['elapsed_s'].values
    timestamps = df['timestamp'].values

    transitions = np.diff(in_play, prepend=1)  # 1 = assume in-play before session
    starts = np.where(transitions == -1)[0]
    ends   = np.where(transitions ==  1)[0]

    if len(starts) > len(ends):
        ends = np.append(ends, len(df) - 1)

    stoppages = []
    for i, (s, e) in enumerate(zip(starts, ends)):
        duration_s = float(elapsed[e] - elapsed[s])
        stoppages.append({
            'index':             i + 1,
            'start_elapsed_min': round(float(elapsed[s]) / 60, 1),
            'duration_s':        round(duration_s),
            'duration_fmt':      fmt_time(duration_s),
        })

    return stoppages


def compute_summary(df, gpx, max_hr):
    elapsed_time_s = df['elapsed_s'].iloc[-1]

    # Game time = in-play rows only; use full-df dt so boundary rows count correctly
    dt_all = df['elapsed_s'].diff().fillna(1.0).clip(lower=0.1)
    if 'is_in_play' in df.columns:
        game_time_s     = float(dt_all[df['is_in_play']].sum())
        stoppage_time_s = elapsed_time_s - game_time_s
        transitions     = df['is_in_play'].astype(int).diff().fillna(0)
        n_stoppages     = int((transitions == -1).sum())
        df_play         = df[df['is_in_play']].copy()
    else:
        game_time_s     = elapsed_time_s
        stoppage_time_s = 0.0
        n_stoppages     = 0
        df_play         = df

    dt          = df_play['elapsed_s'].diff().fillna(1.0).clip(lower=0.1, upper=5.0)
    moving_mask = df_play['speed_kmh'] >= 1.5

    # Use dist_m sum (not cum_dist_m) so stoppage distances are excluded
    total_dist_km = df_play['dist_m'].sum() / 1000
    moving_time_s = dt[moving_mask].sum()
    avg_speed_kmh = total_dist_km / (moving_time_s / 3600) if moving_time_s > 0 else 0
    max_speed_kmh = df_play['speed_kmh'].max() if len(df_play) > 0 else 0.0
    avg_pace      = (moving_time_s / 60) / total_dist_km if total_dist_km > 0 else float('nan')
    best_pace     = (df_play.loc[df_play['speed_kmh'] > 1.5, 'pace_min_per_km'].min()
                     if len(df_play) > 0 else float('nan'))

    ele_diff    = df_play['ele'].diff().fillna(0)
    elev_gain_m = ele_diff[ele_diff > 1.0].sum()
    elev_loss_m = abs(ele_diff[ele_diff < -1.0].sum())

    hr_valid      = df_play['hr'].dropna()
    avg_hr        = int(hr_valid.mean()) if len(hr_valid) > 0 else 0
    max_hr_actual = int(hr_valid.max())  if len(hr_valid) > 0 else 0

    return {
        'activity_name':    gpx.tracks[0].name or 'Football Session',
        'start_time':       df['timestamp'].iloc[0].strftime('%a %d %b %Y · %H:%M UTC'),
        'total_dist_km':    round(total_dist_km, 2),
        'elapsed_time_s':   elapsed_time_s,
        'elapsed_time':     fmt_time(elapsed_time_s),
        'game_time_s':      game_time_s,
        'game_time':        fmt_time(game_time_s),
        'stoppage_time_s':  stoppage_time_s,
        'stoppage_time':    fmt_time(stoppage_time_s),
        'n_stoppages':      n_stoppages,
        'moving_time_s':    moving_time_s,
        'moving_time':      fmt_time(moving_time_s),
        'avg_speed_kmh':    round(avg_speed_kmh, 1),
        'max_speed_kmh':    round(max_speed_kmh, 1),
        'avg_pace':         fmt_pace(avg_pace),
        'best_pace':        fmt_pace(best_pace),
        'elev_gain_m':      round(elev_gain_m, 1),
        'elev_loss_m':      round(elev_loss_m, 1),
        'avg_hr':           avg_hr,
        'max_hr':           max_hr_actual,
        'max_hr_setting':   max_hr,
        'relative_effort':  0,   # filled in after compute_relative_effort
    }


def compute_speed_zones(df):
    if 'is_in_play' in df.columns:
        df = df[df['is_in_play']].copy()
    dt = df['elapsed_s'].diff().fillna(1.0).clip(lower=0.1, upper=5.0)
    df = df.copy()
    df['_dt']        = dt
    df['speed_zone'] = pd.cut(df['speed_kmh'], bins=SPEED_ZONE_BINS,
                               labels=SPEED_ZONE_LABELS, right=False)

    total_time = dt.sum()
    total_dist = df['dist_m'].sum()

    rows = []
    for label, color in zip(SPEED_ZONE_LABELS, SPEED_ZONE_COLORS):
        mask   = df['speed_zone'] == label
        time_s = df.loc[mask, '_dt'].sum()
        dist_m = df.loc[mask, 'dist_m'].sum()
        rows.append({
            'zone_label':     label,
            'color':          color,
            'time_s':         time_s,
            'time_formatted': fmt_time(time_s),
            'dist_m':         dist_m,
            'pct_time':       round(time_s / total_time * 100, 1) if total_time > 0 else 0,
            'pct_dist':       round(dist_m / total_dist * 100, 1) if total_dist > 0 else 0,
        })
    return pd.DataFrame(rows)


def detect_sprints(df, threshold_kmh=18.0, min_duration_s=5.0):
    if 'is_in_play' in df.columns:
        df = df[df['is_in_play']].copy()
    dt        = df['elapsed_s'].diff().fillna(1.0).clip(lower=0.1, upper=5.0)
    is_sprint = df['speed_kmh'] > threshold_kmh
    block_id  = (is_sprint != is_sprint.shift()).cumsum()

    rows = []
    for _, group in df.groupby(block_id):
        if not is_sprint.loc[group.index[0]]:
            continue
        duration = dt.loc[group.index].sum()
        if duration < min_duration_s:
            continue
        hr_vals = group['hr'].dropna()
        rows.append({
            'start_time':        group['timestamp'].iloc[0],
            'start_elapsed_min': round(group['elapsed_s'].iloc[0] / 60, 1),
            'duration_s':        round(duration, 1),
            'dist_m':            round(group['dist_m'].sum(), 1),
            'peak_speed_kmh':    round(group['speed_kmh'].max(), 1),
            'avg_speed_kmh':     round(group['speed_kmh'].mean(), 1),
            'avg_hr':            int(hr_vals.mean()) if len(hr_vals) > 0 else None,
        })
    return pd.DataFrame(rows)


def compute_hr_zones(df, max_hr=190):
    if 'is_in_play' in df.columns:
        df = df[df['is_in_play']].copy()
    dt          = df['elapsed_s'].diff().fillna(1.0).clip(lower=0.1, upper=5.0)
    hr_valid    = df['hr'].notna()
    bounds_bpm  = [int(max_hr * p) for p in [0, 0.60, 0.70, 0.80, 0.90, 1.01]]
    total_time  = dt[hr_valid].sum()

    rows = []
    for i, (label, color, mult) in enumerate(zip(HR_ZONE_LABELS, HR_ZONE_COLORS, HR_ZONE_MULTIPLIERS)):
        lo, hi = bounds_bpm[i], bounds_bpm[i + 1]
        mask   = hr_valid & (df['hr'] >= lo) & (df['hr'] < hi)
        time_s = dt[mask].sum()
        rows.append({
            'zone_label':     label,
            'color':          color,
            'multiplier':     mult,
            'bpm_lo':         lo,
            'bpm_hi':         hi if i < 4 else 999,
            'bpm_range':      f'{lo}–{hi - 1}' if i < 4 else f'{lo}+',
            'time_s':         time_s,
            'time_formatted': fmt_time(time_s),
            'pct_time':       round(time_s / total_time * 100, 1) if total_time > 0 else 0,
        })
    return pd.DataFrame(rows)


def compute_relative_effort(df, hr_zones_df):
    """Edwards TRIMP approximation of Strava Relative Effort."""
    return round(sum((row['time_s'] / 60) * row['multiplier']
                     for _, row in hr_zones_df.iterrows()))


def compute_km_splits(df):
    if 'is_in_play' in df.columns:
        df = df[df['is_in_play']].copy()
        df['cum_dist_m'] = df['dist_m'].cumsum()  # recompute for in-play rows only
    else:
        df = df.copy()
    df['km_bucket'] = (df['cum_dist_m'] // 1000).astype(int) + 1
    dt = df['elapsed_s'].diff().fillna(1.0).clip(lower=0.1, upper=5.0)
    df['_dt'] = dt

    rows = []
    fastest_pace = None
    for km, group in df.groupby('km_bucket'):
        avg_spd      = group['speed_kmh'].mean()
        pace         = 60.0 / avg_spd if avg_spd > 0.5 else float('nan')
        avg_hr_val   = group['hr'].dropna().mean()
        ele_diff     = group['ele'].diff().fillna(0)

        if math.isfinite(pace) and (fastest_pace is None or pace < fastest_pace):
            fastest_pace = pace

        rows.append({
            'km':            km,
            'split_time_s':  group['_dt'].sum(),
            'split_time':    fmt_time(group['_dt'].sum()),
            'dist_m':        round(group['dist_m'].sum(), 0),
            'avg_speed_kmh': round(avg_spd, 1),
            'pace':          pace,
            'pace_formatted': fmt_pace(pace),
            'avg_hr':        int(avg_hr_val) if pd.notna(avg_hr_val) else None,
            'elev_gain_m':   round(ele_diff[ele_diff > 1.0].sum(), 1),
            'is_fastest':    False,
        })

    result = pd.DataFrame(rows)
    if fastest_pace is not None:
        result['is_fastest'] = result['pace'].apply(
            lambda p: math.isfinite(p) and abs(p - fastest_pace) < 0.01
        )
    return result


def compute_work_rate(df, window_s=60):
    """Resample + smooth speed and HR for the work rate chart."""
    if 'is_in_play' in df.columns:
        df = df[df['is_in_play']].copy()
    df_ts = df.set_index('timestamp')[['speed_kmh', 'hr', 'elapsed_s']].copy()
    df_ts['hr'] = df_ts['hr'].astype(float)

    df_1s = df_ts.resample('1s').mean().interpolate('linear')
    df_1s['rolling_speed'] = df_1s['speed_kmh'].rolling(window=window_s, min_periods=10).mean()
    df_1s['rolling_hr']    = df_1s['hr'].rolling(window=window_s, min_periods=10).mean()
    df_1s['elapsed_s']     = df_1s['elapsed_s'].interpolate('linear')

    df_down = df_1s.iloc[::10].copy()
    df_down['elapsed_min'] = df_down['elapsed_s'] / 60
    return df_down.dropna(subset=['rolling_speed', 'rolling_hr'])
