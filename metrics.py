import math

import numpy as np
import pandas as pd

from constants import SPEED_ZONE_BINS, SPEED_ZONE_LABELS, SPEED_ZONE_COLORS
from constants import HR_ZONE_LABELS, HR_ZONE_COLORS, HR_ZONE_MULTIPLIERS
from utils import fmt_time, fmt_pace


def compute_summary(df, gpx, max_hr):
    dt = df['elapsed_s'].diff().fillna(1.0).clip(lower=0.1)
    moving_mask = df['speed_kmh'] >= 1.5

    total_dist_km  = df['cum_dist_m'].iloc[-1] / 1000
    elapsed_time_s = df['elapsed_s'].iloc[-1]
    moving_time_s  = dt[moving_mask].sum()
    avg_speed_kmh  = total_dist_km / (moving_time_s / 3600) if moving_time_s > 0 else 0
    max_speed_kmh  = df['speed_kmh'].max()
    avg_pace       = (moving_time_s / 60) / total_dist_km if total_dist_km > 0 else float('nan')
    best_pace      = df.loc[df['speed_kmh'] > 1.5, 'pace_min_per_km'].min()

    ele_diff    = df['ele'].diff().fillna(0)
    elev_gain_m = ele_diff[ele_diff > 1.0].sum()
    elev_loss_m = abs(ele_diff[ele_diff < -1.0].sum())

    hr_valid      = df['hr'].dropna()
    avg_hr        = int(hr_valid.mean()) if len(hr_valid) > 0 else 0
    max_hr_actual = int(hr_valid.max())  if len(hr_valid) > 0 else 0

    return {
        'activity_name':  gpx.tracks[0].name or 'Football Session',
        'start_time':     df['timestamp'].iloc[0].strftime('%a %d %b %Y · %H:%M UTC'),
        'total_dist_km':  round(total_dist_km, 2),
        'elapsed_time_s': elapsed_time_s,
        'elapsed_time':   fmt_time(elapsed_time_s),
        'moving_time_s':  moving_time_s,
        'moving_time':    fmt_time(moving_time_s),
        'avg_speed_kmh':  round(avg_speed_kmh, 1),
        'max_speed_kmh':  round(max_speed_kmh, 1),
        'avg_pace':       fmt_pace(avg_pace),
        'best_pace':      fmt_pace(best_pace),
        'elev_gain_m':    round(elev_gain_m, 1),
        'elev_loss_m':    round(elev_loss_m, 1),
        'avg_hr':         avg_hr,
        'max_hr':         max_hr_actual,
        'max_hr_setting': max_hr,
        'relative_effort': 0,   # filled in after compute_relative_effort
    }


def compute_speed_zones(df):
    dt = df['elapsed_s'].diff().fillna(1.0).clip(lower=0.1)
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
    dt        = df['elapsed_s'].diff().fillna(1.0).clip(lower=0.1)
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
    dt          = df['elapsed_s'].diff().fillna(1.0).clip(lower=0.1)
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
    df = df.copy()
    df['km_bucket'] = (df['cum_dist_m'] // 1000).astype(int) + 1
    dt = df['elapsed_s'].diff().fillna(1.0).clip(lower=0.1)
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
    df_ts = df.set_index('timestamp')[['speed_kmh', 'hr', 'elapsed_s']].copy()
    df_ts['hr'] = df_ts['hr'].astype(float)

    df_1s = df_ts.resample('1s').mean().interpolate('linear')
    df_1s['rolling_speed'] = df_1s['speed_kmh'].rolling(window=window_s, min_periods=10).mean()
    df_1s['rolling_hr']    = df_1s['hr'].rolling(window=window_s, min_periods=10).mean()
    df_1s['elapsed_s']     = df_1s['elapsed_s'].interpolate('linear')

    df_down = df_1s.iloc[::10].copy()
    df_down['elapsed_min'] = df_down['elapsed_s'] / 60
    return df_down.dropna(subset=['rolling_speed', 'rolling_hr'])
