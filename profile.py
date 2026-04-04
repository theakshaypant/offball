import collections
from datetime import datetime

import numpy as np
import pandas as pd

from constants import ARCHETYPES

ATTR_KEYS = ['pace', 'physical', 'stamina', 'explosiveness', 'work_rate']


def classify_archetype(attrs):
    """Return (name, icon) of the closest archetype by Euclidean distance."""
    player_vec = np.array([attrs[k] for k in ATTR_KEYS], dtype=float)
    best_name, best_dist = None, float('inf')
    for name, arch in ARCHETYPES.items():
        d = float(np.linalg.norm(player_vec - np.array([arch[k] for k in ATTR_KEYS], dtype=float)))
        if d < best_dist:
            best_dist, best_name = d, name
    return best_name, ARCHETYPES[best_name]['icon']


def compute_player_profile(df, summary, zones_df, sprints_df, max_hr=190):
    """Derive EA FC-style attributes and classify the player's archetype."""
    zones_dict = zones_df.set_index('zone_label')['pct_time'].to_dict()

    dist_km    = summary['total_dist_km']
    max_spd    = summary['max_speed_kmh']
    total_s    = summary['elapsed_time_s']
    moving_s   = summary['moving_time_s']
    moving_pct = moving_s / total_s if total_s > 0 else 0

    hsr_pct    = zones_dict.get('High-Speed Running', 0)
    sprint_pct = zones_dict.get('Sprinting', 0)
    run_pct    = zones_dict.get('Running', 0)
    jog_pct    = zones_dict.get('Jogging', 0)
    active_pct = jog_pct + run_pct + hsr_pct + sprint_pct

    # Pace — normalised max speed with high-speed bonus
    pace_raw       = np.clip((max_spd - 10) / 28 * 79 + 20, 20, 99)
    pace           = int(min(99, pace_raw + min(12, (hsr_pct + sprint_pct) * 1.5)))

    # Physical — distance covered + relative effort bonus
    physical_raw   = np.clip((dist_km - 2) / 8 * 55 + 40, 20, 99)
    physical       = int(min(99, physical_raw + min(8, summary.get('relative_effort', 0) / 35)))

    # Stamina — 1st vs 2nd half fade in speed + running intensity, in-play only
    df_play_s      = df[df['is_in_play']].copy() if 'is_in_play' in df.columns else df
    game_s         = summary.get('game_time_s', total_s)
    half_s         = game_s / 2
    f_half         = df_play_s[df_play_s['elapsed_s'] <= half_s]
    s_half         = df_play_s[df_play_s['elapsed_s'] >  half_s]
    f_spd          = f_half['speed_kmh'].mean() if len(f_half) > 0 else 0.0
    s_spd          = s_half['speed_kmh'].mean() if len(s_half) > 0 else 0.0
    speed_drop     = max(0.0, (f_spd - s_spd) / f_spd) if f_spd > 0.1 else 0.0
    f_run          = (f_half['speed_kmh'] >= 7.0).mean() if len(f_half) > 0 else 0.0
    s_run          = (s_half['speed_kmh'] >= 7.0).mean() if len(s_half) > 0 else 0.0
    run_drop       = max(0.0, (f_run - s_run) / f_run) if f_run > 0.01 else 0.0
    composite_drop = 0.5 * speed_drop + 0.5 * run_drop
    stamina        = int(max(20, min(99, round(99 - composite_drop * 150))))

    # Explosiveness — sprint frequency + speed ratio
    elapsed_min    = total_s / 60
    sprints_per_10 = len(sprints_df) / elapsed_min * 10 if elapsed_min > 0 else 0
    avg_moving_spd = df.loc[df['speed_kmh'] > 1.5, 'speed_kmh'].mean()
    spd_ratio      = (max_spd / avg_moving_spd) if pd.notna(avg_moving_spd) and avg_moving_spd > 0 else 1.0
    explosiveness  = int(min(99, max(20, min(sprints_per_10 / 5, 1) * 50 + min((spd_ratio - 1) / 3, 1) * 40 + 15)))

    # Work rate — moving % + active zone %
    work_rate      = int(max(20, min(99, moving_pct * 75 + active_pct * 1.0)))

    attrs   = dict(pace=pace, physical=physical, stamina=stamina,
                   explosiveness=explosiveness, work_rate=work_rate)
    overall = int(round(np.mean(list(attrs.values()))))
    rarity  = 'gold' if overall >= 80 else 'silver' if overall >= 70 else 'bronze' if overall >= 60 else 'trash'

    # Archetype classification
    player_vec      = np.array([attrs[k] for k in ATTR_KEYS], dtype=float)
    distances       = {name: float(np.linalg.norm(player_vec - np.array([arch[k] for k in ATTR_KEYS], dtype=float)))
                       for name, arch in ARCHETYPES.items()}
    sorted_archs    = sorted(distances.items(), key=lambda x: x[1])
    best_archetype  = sorted_archs[0][0]

    return {
        'attrs':           attrs,
        'overall':         overall,
        'rarity':          rarity,
        'archetype':       best_archetype,
        'archetype_data':  ARCHETYPES[best_archetype],
        'top3_archetypes': sorted_archs[:3],
    }


def _bucket_stats(bucket):
    """Aggregate card data from a list of activity dicts (used for index overview)."""
    ovr_vals = [a['overall'] for a in bucket]
    re_vals  = [a['relative_effort'] for a in bucket]
    hr_vals  = [a['avg_hr'] for a in bucket if a.get('avg_hr')]
    dist     = sum(a['total_dist_km'] for a in bucket)

    rarity_c = collections.Counter(a['rarity'] for a in bucket)
    arch_c   = collections.Counter(a['archetype'] for a in bucket)
    top_arch, top_arch_count = arch_c.most_common(1)[0]

    total_moving_s = 0
    for a in bucket:
        try:
            p = a['moving_time'].split(':')
            total_moving_s += int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2])
        except Exception:
            pass

    avg_attrs = {}
    for k in ATTR_KEYS:
        vals = [a['attrs'][k] for a in bucket if 'attrs' in a and k in a['attrs']]
        avg_attrs[k] = round(sum(vals) / len(vals)) if vals else 0

    computed_arch, computed_icon = classify_archetype(avg_attrs)

    h, m = total_moving_s // 3600, (total_moving_s % 3600) // 60
    return {
        'sessions':               len(bucket),
        'total_dist_km':          round(dist, 1),
        'total_moving':           f'{h}h {m}m',
        'avg_hr':                 round(sum(hr_vals) / len(hr_vals)) if hr_vals else 0,
        'best_ovr':               max(ovr_vals),
        'avg_ovr':                round(sum(ovr_vals) / len(ovr_vals)),
        'best_re':                max(re_vals),
        'avg_re':                 round(sum(re_vals) / len(re_vals)),
        'top_archetype':          top_arch,
        'top_arch_icon':          ARCHETYPES[top_arch]['icon'],
        'top_arch_count':         top_arch_count,
        'gold_count':             rarity_c.get('gold', 0),
        'silver_count':           rarity_c.get('silver', 0),
        'bronze_count':           rarity_c.get('bronze', 0),
        'trash_count':            rarity_c.get('trash', 0),
        'avg_attrs':              avg_attrs,
        'archetype_computed':     computed_arch,
        'archetype_computed_icon': computed_icon,
    }


def compute_index_overview(activities):
    """Aggregate stats across all activity cards, broken down by month."""
    if not activities:
        return {}

    overview = _bucket_stats(activities)

    month_buckets = collections.defaultdict(list)
    for a in activities:
        month_buckets[a['start_time'].strftime('%Y-%m')].append(a)

    monthly = []
    for key in sorted(month_buckets.keys(), reverse=True):
        stats = _bucket_stats(month_buckets[key])
        stats['key']   = key
        stats['label'] = datetime.strptime(key, '%Y-%m').strftime('%b %Y')
        monthly.append(stats)

    overview['monthly'] = monthly
    return overview
