import gpxpy
import pandas as pd

from constants import GARMIN_NS
from utils import haversine_m


def load_gpx(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return gpxpy.parse(f)


def build_dataframe(gpx, smooth_window=5):
    """Parse GPX track into a pandas DataFrame with speed, HR, and distance columns."""
    if not gpx.tracks or not gpx.tracks[0].segments or not gpx.tracks[0].segments[0].points:
        raise ValueError('GPX file has no track points')

    points = gpx.tracks[0].segments[0].points
    t0 = points[0].time

    rows = []
    for i, pt in enumerate(points):
        hr = None
        for ext in pt.extensions:
            hr_el = ext.find(f'{{{GARMIN_NS}}}hr')
            if hr_el is not None and hr_el.text:
                hr = int(hr_el.text)
                break

        elapsed_s = (pt.time - t0).total_seconds()

        if i == 0:
            dist_m, speed_ms = 0.0, 0.0
        else:
            prev = points[i - 1]
            raw_dist = haversine_m(prev.latitude, prev.longitude, pt.latitude, pt.longitude)
            dist_m = min(raw_dist, 50.0)          # cap GPS dropouts
            dt = (pt.time - prev.time).total_seconds()
            speed_ms = dist_m / max(dt, 0.1)

        rows.append({
            'timestamp': pt.time,
            'lat': pt.latitude,
            'lon': pt.longitude,
            'ele': pt.elevation or 0.0,
            'hr': hr,
            'elapsed_s': elapsed_s,
            'dist_m': dist_m,
            'speed_ms': speed_ms,
        })

    df = pd.DataFrame(rows)
    df['hr'] = pd.array(df['hr'], dtype='Int64')

    # Rolling median suppresses GPS jitter; hard cap handles outliers
    df['speed_kmh_raw'] = df['speed_ms'] * 3.6
    df['speed_kmh'] = (
        df['speed_kmh_raw']
        .rolling(window=smooth_window, center=True, min_periods=1)
        .median()
        .clip(upper=35.0)
    )
    df['speed_ms']       = df['speed_kmh'] / 3.6
    df['cum_dist_m']     = df['dist_m'].cumsum()
    df['pace_min_per_km'] = df['speed_kmh'].apply(
        lambda s: 60.0 / s if s > 0.5 else float('nan')
    )
    return df
