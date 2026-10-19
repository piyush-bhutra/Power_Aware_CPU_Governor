"""Shared presentation colours and dimensions; no backend configuration."""
VIOLET = '#8b74df'
BLUE = '#4c9bcd'
AMBER = '#cf9852'
SAGE = '#7d9e86'
MIXED = '#b49dcf'
CHART_HEIGHT = 420


def css_tokens():
    return (f':root {{ --violet:{VIOLET}; --blue:{BLUE}; --amber:{AMBER}; '
            '--space-1:.35rem; --space-2:.75rem; --space-3:1rem; --space-4:1.5rem; '
            '--text-small:.8rem; --text-body:.95rem; --radius:.75rem; --motion:120ms; }')
