import json
from datetime import datetime, timezone
from pathlib import Path

import jinja2

from constants import SPEED_ZONE_LABELS, SPEED_ZONE_COLORS
from data import load_gpx, build_dataframe
from metrics import (
    compute_summary, compute_speed_zones, detect_sprints,
    compute_hr_zones, compute_relative_effort, compute_km_splits, compute_work_rate,
    detect_stoppages, compute_stoppages,
)
from profile import compute_player_profile
from charts import (
    make_speed_zone_chart, make_work_rate_chart, make_hr_zone_donut,
    make_pace_chart, make_player_radar_chart,
)
from maps import make_map
from utils import fmt_time


def _make_jinja_env():
    template_dir = Path(__file__).parent / 'templates'
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template_dir)),
        autoescape=False,
    )
    env.filters['fmt_time'] = fmt_time
    return env


def render_report(**kwargs):
    return _make_jinja_env().get_template('report.html').render(**kwargs)


def render_index(**kwargs):
    return _make_jinja_env().get_template('index.html').render(**kwargs)


def process_one(gpx_path, out_path, args, prefix=''):
    """Process a single GPX file and write its HTML report. Returns index card data."""
    p = lambda msg: print(f'{prefix}{msg}')

    p(f'  Loading {gpx_path.name} ...')
    gpx = load_gpx(str(gpx_path))

    p('  Building time-series data ...')
    df = build_dataframe(gpx, smooth_window=args.smooth_window)

    p('  Detecting out-of-play stoppages ...')
    df = detect_stoppages(df)

    p('  Computing metrics ...')
    summary     = compute_summary(df, gpx, args.max_hr)
    zones_df    = compute_speed_zones(df)
    sprints_df  = detect_sprints(df, threshold_kmh=args.sprint_threshold)
    hr_zones_df = compute_hr_zones(df, max_hr=args.max_hr)
    summary['relative_effort'] = compute_relative_effort(df, hr_zones_df)
    splits_df   = compute_km_splits(df)
    work_df     = compute_work_rate(df)
    stoppages   = compute_stoppages(df)
    profile     = compute_player_profile(df, summary, zones_df, sprints_df, max_hr=args.max_hr)

    p('  Generating charts ...')
    speed_zone_chart = make_speed_zone_chart(zones_df)
    work_rate_chart  = make_work_rate_chart(work_df, args.max_hr, sprints_df=sprints_df)
    hr_donut_chart   = make_hr_zone_donut(hr_zones_df, summary['avg_hr'])
    pace_chart       = make_pace_chart(splits_df)
    radar_chart      = make_player_radar_chart(profile)

    p('  Generating interactive map ...')
    map_b64 = make_map(df)

    p('  Rendering HTML report ...')
    generated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    output_html = render_report(
        summary=summary,
        zones_df=zones_df.to_dict('records'),
        hr_zones_df=hr_zones_df.to_dict('records'),
        sprints_df=sprints_df.to_dict('records') if not sprints_df.empty else [],
        splits_df=splits_df.to_dict('records'),
        profile=profile,
        sprint_threshold=args.sprint_threshold,
        speed_zone_chart=speed_zone_chart,
        work_rate_chart=work_rate_chart,
        hr_donut_chart=hr_donut_chart,
        pace_chart=pace_chart,
        radar_chart=radar_chart,
        map_b64=map_b64,
        generated_at=generated_at,
        speed_zone_colors=dict(zip(SPEED_ZONE_LABELS, SPEED_ZONE_COLORS)),
        stoppages=stoppages,
    )
    Path(out_path).write_text(output_html, encoding='utf-8')

    # Card data for the index
    start_dt = df['timestamp'].iloc[0]
    card = {
        'report_path':     str(out_path),
        'activity_name':   summary['activity_name'],
        'start_time_iso':  start_dt.isoformat(),
        'start_time_fmt':  summary['start_time'],
        'total_dist_km':   summary['total_dist_km'],
        'elapsed_time':    summary['elapsed_time'],
        'moving_time':     summary['moving_time'],
        'avg_hr':          summary['avg_hr'],
        'max_speed_kmh':   summary['max_speed_kmh'],
        'relative_effort': summary['relative_effort'],
        'overall':         profile['overall'],
        'rarity':          profile['rarity'],
        'archetype':       profile['archetype'],
        'position':        profile['archetype_data']['position'],
        'icon':            profile['archetype_data']['icon'],
        'attrs':           profile['attrs'],
    }

    # Persist sidecar so --new can skip already-processed files
    Path(out_path).with_suffix('.json').write_text(
        json.dumps(card, indent=2), encoding='utf-8'
    )

    card['start_time'] = start_dt  # raw datetime for in-memory sorting
    return card
