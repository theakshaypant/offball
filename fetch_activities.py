#!/usr/bin/env python3
"""
Fetch new Strava football sessions and save them as GPX files.

First run: opens browser for OAuth, spins up a local server to catch the
redirect, saves the refresh token to .strava_cache.json automatically.
Subsequent runs: uses the cached token, no manual steps needed.

Usage:
  python fetch_activities.py

Requires STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in your environment
(or .env file). Everything else is handled automatically.
"""

import http.server
import json
import os
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


STRAVA_AUTH_URL    = 'https://www.strava.com/oauth/authorize'
STRAVA_TOKEN_URL   = 'https://www.strava.com/oauth/token'
STRAVA_API         = 'https://www.strava.com/api/v3'
FOOTBALL_TYPES     = {'soccer', 'football'}
CACHE_FILE         = Path('.strava_cache.json')
REDIRECT_PORT      = 8765
REDIRECT_URI       = f'http://localhost:{REDIRECT_PORT}'


# ── OAuth ─────────────────────────────────────────────────────────────────────

def oauth_flow(client_id, client_secret):
    """Open browser, catch redirect, return fresh tokens dict."""
    auth_url = (
        f'{STRAVA_AUTH_URL}?client_id={client_id}'
        f'&response_type=code'
        f'&redirect_uri={REDIRECT_URI}'
        f'&scope=activity:read_all'
        f'&approval_prompt=force'
    )

    code_holder = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            if 'code' in params:
                code_holder.append(params['code'][0])
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'<h2>Authorised. You can close this tab.</h2>')

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(('localhost', REDIRECT_PORT), Handler)
    t = threading.Thread(target=server.handle_request)
    t.start()

    print(f'Opening Strava authorisation in your browser...')
    webbrowser.open(auth_url)
    t.join(timeout=120)
    server.server_close()

    if not code_holder:
        print('Timed out waiting for authorisation.')
        sys.exit(1)

    return exchange_code(client_id, client_secret, code_holder[0])


def exchange_code(client_id, client_secret, code):
    return _post_token(client_id, client_secret, grant_type='authorization_code', code=code)


def refresh_access_token(client_id, client_secret, refresh_token):
    return _post_token(client_id, client_secret, grant_type='refresh_token', refresh_token=refresh_token)


def _post_token(client_id, client_secret, **fields):
    payload = urllib.parse.urlencode({'client_id': client_id, 'client_secret': client_secret, **fields}).encode()
    req = urllib.request.Request(STRAVA_TOKEN_URL, data=payload, method='POST')
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}


def save_cache(data):
    CACHE_FILE.write_text(json.dumps(data, indent=2))


def get_token(client_id, client_secret):
    cache = load_cache()

    # Access token still valid
    if cache.get('access_token') and cache.get('expires_at', 0) > datetime.now(timezone.utc).timestamp() + 60:
        return cache['access_token']

    # Refresh if we have a refresh token
    if cache.get('refresh_token'):
        print('Refreshing access token...')
        tokens = refresh_access_token(client_id, client_secret, cache['refresh_token'])
        cache.update(tokens)
        save_cache(cache)
        return cache['access_token']

    # Full OAuth flow
    tokens = oauth_flow(client_id, client_secret)
    save_cache(tokens)
    return tokens['access_token']


# ── Strava API ────────────────────────────────────────────────────────────────

def api_get(path, token, params=None):
    url = f'{STRAVA_API}{path}'
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f'API error {e.code}: {e.read().decode()}')
        sys.exit(1)


def fetch_all_activities(token):
    activities, page = [], 1
    while True:
        batch = api_get('/athlete/activities', token, {'per_page': 200, 'page': page})
        if not batch:
            break
        activities.extend(batch)
        page += 1
    return activities


def fetch_streams(activity_id, token):
    keys = 'latlng,time,altitude,heartrate'
    data = api_get(f'/activities/{activity_id}/streams', token, {'keys': keys, 'key_by_type': 'true'})
    return data


# ── GPX construction ──────────────────────────────────────────────────────────

def build_gpx(activity, streams):
    start_dt = datetime.fromisoformat(activity['start_date'].replace('Z', '+00:00'))

    latlng    = streams.get('latlng', {}).get('data', [])
    times     = streams.get('time', {}).get('data', [])
    altitudes = streams.get('altitude', {}).get('data', [])
    heartrates = streams.get('heartrate', {}).get('data', [])

    if not latlng or not times:
        return None

    ET.register_namespace('', 'http://www.topografix.com/GPX/1/1')
    ET.register_namespace('gpxtpx', 'http://www.garmin.com/xmlschemas/TrackPointExtension/v1')

    gpx = ET.Element('gpx', {
        'version': '1.1',
        'creator': 'offball',
        'xmlns':      'http://www.topografix.com/GPX/1/1',
        'xmlns:gpxtpx': 'http://www.garmin.com/xmlschemas/TrackPointExtension/v1',
    })
    trk  = ET.SubElement(gpx, 'trk')
    ET.SubElement(trk, 'name').text = activity.get('name', 'Football')
    ET.SubElement(trk, 'type').text = 'soccer'
    seg  = ET.SubElement(trk, 'trkseg')

    for i, (lat, lon) in enumerate(latlng):
        pt = ET.SubElement(seg, 'trkpt', {'lat': str(lat), 'lon': str(lon)})

        if i < len(altitudes):
            ET.SubElement(pt, 'ele').text = str(altitudes[i])

        offset_s = times[i] if i < len(times) else i
        ts = start_dt.timestamp() + offset_s
        ET.SubElement(pt, 'time').text = datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        if i < len(heartrates) and heartrates[i]:
            ext    = ET.SubElement(pt, 'extensions')
            tpx    = ET.SubElement(ext, 'gpxtpx:TrackPointExtension')
            ET.SubElement(tpx, 'gpxtpx:hr').text = str(int(heartrates[i]))

    return ET.tostring(gpx, encoding='unicode', xml_declaration=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def existing_ids(data_dir):
    return {p.stem for p in Path(data_dir).rglob('*.gpx')}


def load_env():
    env_file = Path('.env')
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())


def main():
    load_env()

    client_id     = os.environ.get('STRAVA_CLIENT_ID')
    client_secret = os.environ.get('STRAVA_CLIENT_SECRET')

    if not client_id or not client_secret:
        print('Set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in your environment or .env file.')
        sys.exit(1)

    token = get_token(client_id, client_secret)

    print('Fetching activity list...')
    activities = fetch_all_activities(token)
    football   = [a for a in activities if (a.get('sport_type') or a.get('type') or '').lower() in FOOTBALL_TYPES]
    print(f'{len(activities)} total activities, {len(football)} football session(s) on Strava.')

    done = existing_ids('data')
    new  = [a for a in football if str(a['id']) not in done]
    print(f'{len(done)} GPX file(s) already downloaded, {len(new)} new.')

    if not new:
        print('Nothing new — you are up to date.')
        return

    out_dir = Path('data/activities')
    out_dir.mkdir(parents=True, exist_ok=True)

    for a in sorted(new, key=lambda x: x['start_date']):
        name = a.get('name', 'Unnamed')
        date = a['start_date'][:10]
        print(f'  Downloading {date} — {name} ...', end=' ', flush=True)

        streams = fetch_streams(a['id'], token)
        gpx_str = build_gpx(a, streams)

        if gpx_str is None:
            print('skipped (no GPS data)')
            continue

        out_path = out_dir / f'{a["id"]}.gpx'
        out_path.write_text(gpx_str, encoding='utf-8')
        print('done')

    print(f'\nAll done. Run: python analyze.py --new')


if __name__ == '__main__':
    main()
