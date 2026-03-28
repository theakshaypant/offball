import base64

import folium
from folium.plugins import HeatMap

from constants import SPEED_ZONE_BINS, SPEED_ZONE_LABELS, SPEED_ZONE_COLORS


def make_map(df):
    m = folium.Map(
        location=[df['lat'].mean(), df['lon'].mean()],
        zoom_start=18,
        tiles='CartoDB positron',
        max_zoom=22,
    )

    # ── LAYER 1: Lines ───────────────────────────────────────────────────────
    # SVG polylines. Add all line/vector layers here.
    # New line layers: .add_to(m) in this section.

    def zone_idx(spd):
        for i in range(len(SPEED_ZONE_BINS) - 1):
            if spd < SPEED_ZONE_BINS[i + 1]:
                return i
        return len(SPEED_ZONE_BINS) - 2

    df_track = df[df['is_in_play']].copy() if 'is_in_play' in df.columns else df

    def flush_seg(coords, zone):
        if len(coords) >= 2:
            folium.PolyLine(
                coords,
                color=SPEED_ZONE_COLORS[zone],
                weight=4,
                opacity=0.85,
                tooltip=SPEED_ZONE_LABELS[zone],
            ).add_to(m)

    current_zone = None
    seg_coords = []
    prev_idx = None
    for idx, row in df_track.iterrows():
        z = zone_idx(row['speed_kmh'])
        # Break segment at a stoppage gap (non-contiguous index) or zone change
        gap = prev_idx is not None and idx != prev_idx + 1
        if gap or (current_zone is not None and z != current_zone):
            flush_seg(seg_coords, current_zone)
            seg_coords = [seg_coords[-1]] if seg_coords and not gap else []
            current_zone = z
        if current_zone is None:
            current_zone = z
        seg_coords.append([row['lat'], row['lon']])
        prev_idx = idx

    flush_seg(seg_coords, current_zone)

    # ── LAYER 2: Heatmaps ────────────────────────────────────────────────────
    # Canvas-based overlays rendered above the lines.
    # Convention: show=False so each heatmap is toggled on exclusively,
    # avoiding competition with the track. New heatmap layers go here.

    # Coverage — uniform weight, shows where time was spent
    coverage_data = [[row['lat'], row['lon'], 1.0] for _, row in df_track.iterrows()]
    HeatMap(coverage_data, radius=16, blur=20, max_zoom=20,
            name='Coverage Heatmap', show=False,
            gradient={0.2: '#ffffb2', 0.4: '#fecc5c',
                      0.6: '#fd8d3c', 0.8: '#f03b20', 1.0: '#bd0026'},
            ).add_to(m)

    # Speed — weighted by km/h, shows where you moved fast
    max_spd = df_track['speed_kmh'].max() if len(df_track) > 0 else 0
    if max_spd > 0:
        heat_data = [
            [row['lat'], row['lon'], row['speed_kmh'] / max_spd]
            for _, row in df_track.iterrows()
            if row['speed_kmh'] > 1.0
        ]
        if heat_data:
            HeatMap(heat_data, radius=14, blur=18, max_zoom=20,
                    name='Speed Heatmap', show=False).add_to(m)

    # ── LAYER 3: Markers ─────────────────────────────────────────────────────
    # Always on top (Leaflet markerPane sits above overlayPane).
    # New point markers go here.

    folium.Marker(
        [df['lat'].iloc[0], df['lon'].iloc[0]],
        icon=folium.Icon(color='green', icon='play', prefix='fa'),
        tooltip='Start',
    ).add_to(m)
    folium.Marker(
        [df['lat'].iloc[-1], df['lon'].iloc[-1]],
        icon=folium.Icon(color='red', icon='stop', prefix='fa'),
        tooltip='End',
    ).add_to(m)

    folium.LayerControl().add_to(m)

    return base64.b64encode(m._repr_html_().encode('utf-8')).decode('ascii')
