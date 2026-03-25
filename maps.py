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

    current_zone = None
    seg_coords = []
    for lat, lon, spd in zip(df['lat'], df['lon'], df['speed_kmh']):
        z = zone_idx(spd)
        if current_zone is None:
            current_zone = z
        if z != current_zone:
            if len(seg_coords) >= 2:
                folium.PolyLine(
                    seg_coords,
                    color=SPEED_ZONE_COLORS[current_zone],
                    weight=4,
                    opacity=0.85,
                    tooltip=SPEED_ZONE_LABELS[current_zone],
                ).add_to(m)
            seg_coords = [seg_coords[-1]] if seg_coords else []
            current_zone = z
        seg_coords.append([lat, lon])

    if len(seg_coords) >= 2 and current_zone is not None:
        folium.PolyLine(seg_coords, color=SPEED_ZONE_COLORS[current_zone],
                        weight=4, opacity=0.85).add_to(m)

    # ── LAYER 2: Heatmaps ────────────────────────────────────────────────────
    # Canvas-based overlays rendered above the lines.
    # Convention: show=False so each heatmap is toggled on exclusively,
    # avoiding competition with the track. New heatmap layers go here.

    # Coverage — uniform weight, shows where time was spent
    coverage_data = [[row['lat'], row['lon'], 1.0] for _, row in df.iterrows()]
    HeatMap(coverage_data, radius=16, blur=20, max_zoom=20,
            name='Coverage Heatmap', show=False,
            gradient={0.2: '#ffffb2', 0.4: '#fecc5c',
                      0.6: '#fd8d3c', 0.8: '#f03b20', 1.0: '#bd0026'},
            ).add_to(m)

    # Speed — weighted by km/h, shows where you moved fast
    max_spd = df['speed_kmh'].max()
    if max_spd > 0:
        heat_data = [
            [row['lat'], row['lon'], row['speed_kmh'] / max_spd]
            for _, row in df.iterrows()
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
