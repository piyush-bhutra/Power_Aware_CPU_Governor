"""Offline Plotly figures; values come only from verified presentation data."""
import plotly.graph_objects as go
from plotly.subplots import make_subplots

VIOLET = '#7057cf'
BLUE = '#4389ba'
AMBER = '#c28a42'
CLASS_COLORS = {'cpu_bound': VIOLET, 'io_bound': AMBER, 'idle': '#8aa48f', 'mixed': '#bba9d9'}
POLICY_COLORS = {'ours': VIOLET, 'performance': '#a9adb9', 'powersave': '#97ad9a',
                 'ondemand': BLUE, 'conservative': '#d3a170'}


def style(figure, height=360):
    figure.update_layout(template='plotly_white', height=height, paper_bgcolor='rgba(0,0,0,0)',
                         plot_bgcolor='rgba(0,0,0,0)', font=dict(family='Segoe UI, Arial', color='#3e3b48', size=12),
                         margin=dict(l=50, r=20, t=40, b=45),
                         legend=dict(orientation='h', y=-.23, x=0), hovermode='x unified')
    figure.update_xaxes(gridcolor='#eeeaf0', zeroline=False)
    figure.update_yaxes(gridcolor='#eeeaf0', zeroline=False)
    return figure


def replay_figure(replay, tick):
    frames = replay.frames[:tick]
    if not frames:
        raise ValueError('Replay chart requires a selected sample')
    ticks = [f.tick for f in frames]
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=.13,
                        row_heights=[.40, .16, .44],
                        subplot_titles=('CPU utilization (%)', 'Predicted workload', 'Simulated frequency (GHz)'))
    fig.add_trace(go.Scatter(x=ticks, y=[f.util_pct for f in frames], mode='lines+markers',
                            name='CPU utilization', line=dict(color=VIOLET, width=2),
                            marker=dict(size=4), fill='tozeroy', fillcolor='rgba(112,87,207,.09)',
                            hovertemplate='%{y:.2f}%<extra>CPU utilization</extra>'), row=1, col=1)
    fig.add_trace(go.Scatter(x=ticks, y=[1] * len(frames), mode='markers', name='Predicted workload',
                            marker=dict(symbol='square', size=17, color=[CLASS_COLORS[f.predicted_class] for f in frames]),
                            text=[f.predicted_class for f in frames], showlegend=False,
                            hovertemplate='%{text}<extra>Provisional rule output</extra>'), row=2, col=1)
    for field, name, color, dash in (
        ('candidate_khz', 'Candidate simulated frequency (derived)', VIOLET, 'dash'),
        ('applied_khz', 'Applied simulated frequency', BLUE, 'solid')):
        fig.add_trace(go.Scatter(x=ticks, y=[getattr(f, field) / 1e6 if getattr(f, field) is not None else None for f in frames],
                                mode='lines+markers', name=name, marker=dict(size=4),
                                line=dict(color=color, width=2.5, dash=dash, shape='hv'),
                                hovertemplate='%{y:.6f} GHz<extra>' + name + '</extra>'), row=3, col=1)
    fig.update_yaxes(range=[0, 103], row=1, col=1)
    fig.update_yaxes(range=[.5, 1.5], showticklabels=False, showgrid=False, row=2, col=1)
    ladder = replay.metadata['ladder_khz']
    fig.update_yaxes(range=[ladder[0] / 1e6 - .12, ladder[-1] / 1e6 + .12], row=3, col=1)
    for row in (1, 2, 3):
        fig.add_vline(x=tick, line_dash='dot', line_color='#b7b0c3', row=row, col=1)
    fig.update_xaxes(range=[.5, len(replay.frames) + .5], dtick=5)
    synthetic = replay.frames[0].source_kind == 'synthetic'
    fig.update_xaxes(title_text='Synthetic tick · nominal one-second intervals' if synthetic else 'Saved observation tick · measured intervals in inspector', row=3, col=1)
    events = [f.transition for f in frames if f.transition]
    if events:
        fig.add_trace(go.Scatter(x=[e.tick for e in events], y=[e.new_khz / 1e6 for e in events],
                                mode='markers', name='Applied simulated transitions',
                                marker=dict(symbol='diamond', size=11, color=AMBER),
                                text=[e.reason for e in events], hovertemplate='%{text}<extra>Simulated transition</extra>'), row=3, col=1)
    for annotation in fig.layout.annotations:
        annotation.update(font=dict(size=12, color='#716a7c'), x=0, xanchor='left')
    return style(fig, 420)


def energy_figure(comparison):
    names = list(comparison.summaries)
    fig = go.Figure(go.Bar(x=[comparison.summaries[n]['total_energy_j'] for n in names],
                           y=names, orientation='h', marker_color=[POLICY_COLORS[n] for n in names],
                           text=[f"{comparison.summaries[n]['total_energy_j']:.2f} J" for n in names],
                           textposition='auto', hovertemplate='%{y}: %{x:.3f} J<extra>Uncalibrated model estimate</extra>'))
    fig.update_xaxes(title='Modelled energy (J) · uncalibrated estimate')
    fig.update_layout(showlegend=False)
    return style(fig, 300)


def comparison_figure(comparison, names):
    fig = go.Figure()
    for name in names:
        rows = comparison.policies[name]
        fig.add_trace(go.Scatter(x=list(range(1, len(rows) + 1)), y=[r['target_khz'] / 1e6 for r in rows],
                                name=name, mode='lines', line=dict(color=POLICY_COLORS[name], shape='hv', width=2)))
    fig.update_xaxes(title='Synthetic tick')
    fig.update_yaxes(title='Simulated frequency (GHz)')
    return style(fig)


def evidence_figure(observations):
    frames = observations.frames
    fig = go.Figure(go.Scatter(x=[f.tick for f in frames], y=[f.util_pct for f in frames],
                              mode='lines+markers', line=dict(color='#718e78', width=2),
                              name='Recorded CPU utilization'))
    fig.update_xaxes(title='Archived observation number', dtick=1)
    fig.update_yaxes(title='Measured guest CPU utilization (%)')
    return style(fig, 270)
