import math

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


_CHART_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color='#e0e0e0', size=14, family='-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'),
    hoverlabel=dict(bgcolor='#1a1a2e', bordercolor='#444', font=dict(color='#e0e0e0', size=13)),
)


def make_speed_zone_chart(zones_df):
    fig = go.Figure(go.Pie(
        labels=zones_df['zone_label'].tolist(),
        values=zones_df['time_s'].tolist(),
        hole=0.52,
        marker=dict(colors=zones_df['color'].tolist(), line=dict(color='#1a1a2e', width=2)),
        textinfo='percent',
        hovertemplate='%{label}<br>%{customdata}<extra></extra>',
        customdata=zones_df['time_formatted'].tolist(),
        sort=False,
    ))
    fig.update_layout(
        **_CHART_LAYOUT,
        showlegend=False,
        height=260,
        margin=dict(l=10, r=10, t=10, b=10),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)



def make_work_rate_chart(work_df, max_hr, sprints_df=None):
    fig = make_subplots(specs=[[{'secondary_y': True}]])

    fig.add_trace(go.Scatter(
        x=work_df['elapsed_min'],
        y=work_df['rolling_speed'],
        name='Speed',
        line=dict(color='#64B5F6', width=2.5),
        hovertemplate='%{y:.1f} km/h',
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=work_df['elapsed_min'],
        y=work_df['rolling_hr'],
        name='Heart Rate',
        line=dict(color='#EF5350', width=2.5),
        hovertemplate='%{y:.0f} bpm',
    ), secondary_y=True)

    z4_bpm = int(max_hr * 0.80)
    fig.add_hline(
        y=z4_bpm, secondary_y=True,
        line=dict(color='rgba(255,107,53,0.4)', width=1, dash='dot'),
        annotation_text=f'Z4 · {z4_bpm} bpm',
        annotation_position='right',
        annotation_font=dict(color='#ff6b35', size=11),
    )

    spd = work_df['rolling_speed'].dropna()
    hr  = work_df['rolling_hr'].dropna()
    spd_pad = (spd.max() - spd.min()) * 0.15 or 1
    hr_pad  = (hr.max()  - hr.min())  * 0.15 or 5

    fig.update_layout(
        **_CHART_LAYOUT,
        height=300,
        hovermode='x unified',
        legend=dict(orientation='h', y=1.06, x=0, font=dict(size=14)),
        margin=dict(l=10, r=80, t=10, b=40),
    )
    fig.update_xaxes(title_text='Elapsed (min)', gridcolor='#222', zeroline=False,
                     range=[float(work_df['elapsed_min'].min()), float(work_df['elapsed_min'].max())],
                     fixedrange=True)
    fig.update_yaxes(title_text='Speed (km/h)', secondary_y=False,
                     gridcolor='#222', zeroline=False,
                     range=[float(spd.min() - spd_pad), float(spd.max() + spd_pad)],
                     fixedrange=True)
    fig.update_yaxes(title_text='HR (bpm)', secondary_y=True,
                     showgrid=False, zeroline=False,
                     range=[float(hr.min() - hr_pad), float(hr.max() + hr_pad)],
                     fixedrange=True)

    # Shade sprint intervals
    if sprints_df is not None and not sprints_df.empty:
        for _, sprint in sprints_df.iterrows():
            start = sprint['start_elapsed_min']
            end   = start + sprint['duration_s'] / 60
            fig.add_vrect(x0=start, x1=end,
                          fillcolor='rgba(156,39,176,0.18)',
                          line_width=0, layer='below')

    return fig.to_html(full_html=False, include_plotlyjs=False)


def make_hr_zone_donut(hr_zones_df, avg_hr):
    fig = go.Figure(go.Pie(
        labels=hr_zones_df['zone_label'].tolist(),
        values=hr_zones_df['time_s'].tolist(),
        hole=0.52,
        marker=dict(colors=hr_zones_df['color'].tolist(), line=dict(color='#1a1a2e', width=2)),
        textinfo='percent',
        hovertemplate='%{label}<br>%{customdata}<extra></extra>',
        customdata=hr_zones_df['time_formatted'].tolist(),
        sort=False,
    ))
    fig.add_annotation(
        text=f'<b>{avg_hr}</b><br>avg bpm',
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=16, color='#e0e0e0'),
    )
    fig.update_layout(
        **_CHART_LAYOUT,
        showlegend=True,
        legend=dict(orientation='v', x=1.0, font=dict(size=14)),
        height=260,
        margin=dict(l=10, r=140, t=10, b=10),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


def make_pace_chart(splits_df):
    if splits_df.empty:
        return '<p style="color:#888">No split data available.</p>'

    valid = splits_df[splits_df['pace'].apply(lambda p: math.isfinite(p) and p > 0)].copy()
    if valid.empty:
        return '<p style="color:#888">No split data available.</p>'

    fig = make_subplots(specs=[[{'secondary_y': True}]])

    min_pace   = valid['pace'].min()
    max_pace   = valid['pace'].max()
    pace_range = max(max_pace - min_pace, 0.01)

    bar_colors = []
    for _, row in valid.iterrows():
        ratio = (row['pace'] - min_pace) / pace_range
        bar_colors.append(f'rgb({int(255 * ratio)},{int(255 * (1 - ratio))},80)')

    has_hr = valid['avg_hr'].notna().any()
    hr_vals = valid['avg_hr'].fillna(0).astype(int)
    labels  = valid['km'].astype(str).apply(lambda k: f'Km {k}')

    # Encode both metrics in customdata for a single unified tooltip
    custom = np.column_stack([valid['pace_formatted'], hr_vals if has_hr else ['—'] * len(valid)])
    hr_tpl = '<br>Avg HR: %{customdata[1]} bpm' if has_hr else ''

    fig.add_trace(go.Bar(
        x=labels,
        y=valid['pace'],
        name='Pace',
        marker_color=bar_colors,
        marker_line_width=0,
        customdata=custom,
        hovertemplate='<b>%{x}</b><br>Pace: %{customdata[0]} /km' + hr_tpl + '<extra></extra>',
    ), secondary_y=False)

    if has_hr:
        fig.add_trace(go.Scatter(
            x=labels,
            y=valid['avg_hr'],
            name='Avg HR',
            mode='lines+markers',
            line=dict(color='#EF5350', width=2),
            marker=dict(size=6),
            hoverinfo='skip',   # tooltip handled by bar customdata
        ), secondary_y=True)

    # Show formatted pace as Y-axis tick labels; invert so faster = taller bar
    tick_vals = sorted(valid['pace'].tolist())
    tick_map  = dict(zip(valid['pace'].tolist(), valid['pace_formatted'].tolist()))
    tick_text = [tick_map.get(v, '') for v in tick_vals]

    # Pad the inverted range so bars don't touch the top
    pace_pad = (max_pace - min_pace) * 0.25 or 0.5
    y_range  = [max_pace + pace_pad, min_pace - pace_pad]   # inverted

    fig.update_layout(
        **_CHART_LAYOUT,
        height=220,
        hovermode='x',
        showlegend=bool(has_hr),
        legend=dict(orientation='h', y=1.12, x=0, font=dict(size=12)),
        margin=dict(l=55, r=50, t=10, b=30),
    )
    fig.update_yaxes(range=y_range, gridcolor='#2a2a2a', zeroline=False,
                     tickvals=tick_vals, ticktext=tick_text,
                     tickfont=dict(size=11), fixedrange=True, secondary_y=False)
    fig.update_yaxes(title_text='HR (bpm)', showgrid=False, zeroline=False,
                     tickfont=dict(size=11), fixedrange=True, secondary_y=True)
    fig.update_xaxes(fixedrange=True)
    return fig.to_html(full_html=False, include_plotlyjs=False)


def make_player_radar_chart(profile):
    arch_name = profile['archetype']
    arch_data = profile['archetype_data']
    attrs     = profile['attrs']

    categories = ['Pace', 'Physical', 'Stamina', 'Explosiveness', 'Work Rate']
    attr_keys  = ['pace', 'physical', 'stamina', 'explosiveness', 'work_rate']

    player_vals = [attrs[k] for k in attr_keys]
    arch_vals   = [arch_data[k] for k in attr_keys]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=arch_vals + [arch_vals[0]],
        theta=categories + [categories[0]],
        fill='toself',
        name=arch_name,
        fillcolor='rgba(255,255,255,0.05)',
        line=dict(color=arch_data['color'], width=2, dash='dot'),
    ))
    fig.add_trace(go.Scatterpolar(
        r=player_vals + [player_vals[0]],
        theta=categories + [categories[0]],
        fill='toself',
        name='You',
        fillcolor='rgba(100,181,246,0.25)',
        line=dict(color='#64B5F6', width=3),
    ))
    fig.update_layout(
        **_CHART_LAYOUT,
        polar=dict(
            radialaxis=dict(range=[0, 99], visible=True, showticklabels=False,
                            gridcolor='#333', linecolor='#444'),
            angularaxis=dict(gridcolor='#333', linecolor='#444'),
            bgcolor='rgba(0,0,0,0)',
        ),
        showlegend=True,
        legend=dict(orientation='h', y=-0.15, font=dict(size=14)),
        height=300,
        margin=dict(l=40, r=40, t=20, b=50),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)
