"""Plain-language presentation of existing, verified decisions."""
from collections import Counter
from datetime import datetime

CLASS_NAMES = {'cpu_bound': 'CPU busy', 'io_bound': 'Waiting for I/O',
               'idle': 'Mostly idle', 'mixed': 'Mixed activity'}


def session_label(metadata):
    try:
        date = datetime.fromisoformat(metadata.get('started_utc', '').replace('Z', '+00:00'))
        stamp = date.strftime('%d %b %Y, %H:%M:%S %Z').strip()
    except (ValueError, TypeError):
        stamp = 'Date unavailable'
    count = metadata.get('actual_sample_count')
    samples = f'{count} samples' if isinstance(count, int) else 'Sample count unavailable'
    quality = {'clean': 'Timing clean', 'degraded': 'Timing degraded'}.get(
        metadata.get('timing_quality'), 'Timing not recorded')
    return f'{stamp} · {samples} · {quality}'


def what_happened(replay):
    frames = replay.frames
    counts = Counter(f.predicted_class for f in frames)
    classes = ', '.join(f'{CLASS_NAMES.get(name, name)} ({count})' for name, count in counts.items())
    text = f'The governor saw {len(frames)} samples and predicted: {classes}. '
    events = [f.transition for f in frames if f.transition]
    if events:
        event = events[0]
        text += (f'Its first simulated frequency change was {event.previous_khz / 1e6:.3f} to '
                 f'{event.new_khz / 1e6:.3f} GHz at sample {event.tick}, after '
                 f'{replay.metadata["k"]} matching predictions. '
                 f'There were {len(events)} changes in the full session; initialization is excluded.')
    else:
        text += (f'The simulated frequency stayed at {frames[0].applied_khz / 1e6:.3f} GHz. '
                 f'No different target was accepted by the {replay.metadata["k"]}-sample persistence rule. '
                 'Zero changes is a valid result.')
    return text
