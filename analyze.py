#!/usr/bin/env python3
"""
Offball — Football GPX Analyser

Reads GPX files from data/ (football/soccer only), generates per-session HTML
reports in profile/, and writes a summary index.html.

Usage:
    python analyze.py [--new] [--data-dir data] [--max-hr 190]
                      [--sprint-threshold 18] [--smooth-window 5]
"""

import argparse
import collections
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from data import load_gpx
from profile import compute_index_overview
from report import process_one, render_index


def parse_args():
    parser = argparse.ArgumentParser(
        prog='offball',
        description='Analyse football GPX files from data/ and generate HTML reports in profile/.',
    )
    parser.add_argument('--data-dir', default='data',
                        help='Directory to search for .gpx files recursively (default: data/)')
    parser.add_argument('--new', action='store_true',
                        help='Only process GPX files not yet in profile/, then rebuild the index')
    parser.add_argument('--max-hr', type=int, default=190,
                        help='Max heart rate for zone calculations (default: 190)')
    parser.add_argument('--sprint-threshold', type=float, default=18.0,
                        help='Speed km/h threshold for sprint detection (default: 18)')
    parser.add_argument('--smooth-window', type=int, default=5,
                        help='Rolling median window in seconds for speed smoothing (default: 5)')
    return parser.parse_args()


def load_existing_cards(profile_dir):
    """Read JSON sidecars from profile_dir and return a list of card dicts."""
    cards = []
    for sidecar in profile_dir.glob('*.json'):
        try:
            card = json.loads(sidecar.read_text(encoding='utf-8'))
            card['start_time'] = datetime.fromisoformat(card['start_time_iso'])
            card['report_path'] = f'profile/{sidecar.stem}.html'
            cards.append(card)
        except Exception:
            pass
    return cards


def main():
    args = parse_args()
    data_dir = Path(args.data_dir)

    if not data_dir.is_dir():
        print(f'Error: data directory not found: {data_dir}', file=sys.stderr)
        sys.exit(1)

    all_gpx = sorted(data_dir.rglob('*.gpx'))
    if not all_gpx:
        print(f'No .gpx files found in {data_dir}', file=sys.stderr)
        sys.exit(1)

    # Filter to football/soccer only
    football_types = {'soccer', 'football'}
    gpx_files = []
    skipped_types = collections.Counter()
    for f in all_gpx:
        try:
            gpx = load_gpx(str(f))
            track_type = (gpx.tracks[0].type or '').strip().lower() if gpx.tracks else ''
            if track_type in football_types:
                gpx_files.append(f)
            else:
                skipped_types[track_type or 'unknown'] += 1
        except Exception:
            skipped_types['unreadable'] += 1

    if skipped_types:
        summary = ', '.join(f'{v} {k}' for k, v in sorted(skipped_types.items()))
        print(f'Skipped {sum(skipped_types.values())} non-football file(s): {summary}')

    if not gpx_files:
        print('No football/soccer GPX files found.', file=sys.stderr)
        sys.exit(1)

    profile_dir = Path('profile')
    profile_dir.mkdir(exist_ok=True)

    if args.new:
        already_done = {p.stem.replace('_report', '') for p in profile_dir.glob('*_report.html')}
        to_process   = [f for f in gpx_files if f.stem not in already_done]
        existing_cards = load_existing_cards(profile_dir)
        missing_sidecars = len(already_done) - len(existing_cards)
        if missing_sidecars > 0:
            print(f'Note: {missing_sidecars} existing report(s) have no metadata cache '
                  f'— run without --new once to rebuild them.')
        if not to_process:
            print(f'No new sessions to process ({len(already_done)} already in profile/).')
        else:
            print(f'{len(to_process)} new session(s) to process '
                  f'({len(already_done)} already done) → {profile_dir}/')
    else:
        to_process     = gpx_files
        existing_cards = []
        print(f'Processing {len(gpx_files)} football session(s) → {profile_dir}/ (index → index.html)')

    activities = list(existing_cards)
    for i, gpx_path in enumerate(to_process, 1):
        print(f'\n[{i}/{len(to_process)}] {gpx_path.name}')
        out_path = profile_dir / f'{gpx_path.stem}_report.html'
        try:
            card = process_one(gpx_path, out_path, args)
            card['report_path'] = f'profile/{out_path.name}'
            activities.append(card)
        except Exception as e:
            print(f'  Warning: skipped {gpx_path.name}: {e}', file=sys.stderr)

    if not activities:
        print('No activities to include in index.', file=sys.stderr)
        sys.exit(1)

    activities.sort(key=lambda a: a['start_time'], reverse=True)

    index_path = Path('index.html')
    print(f'\nGenerating index → {index_path}')
    generated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    overview     = compute_index_overview(activities)
    index_html   = render_index(activities=activities, overview=overview, generated_at=generated_at)
    index_path.write_text(index_html, encoding='utf-8')

    print(f'\nDone. Open {index_path} in a browser.')


if __name__ == '__main__':
    main()
