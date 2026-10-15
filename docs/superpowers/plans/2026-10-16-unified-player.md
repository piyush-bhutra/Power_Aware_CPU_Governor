# Unified Daybreak player implementation plan

**Goal:** One finite automatic/manual player for verified synthetic and validated Linux sessions.

**Architecture:** Keep existing Dataset/Frame APIs and visual surfaces. A pure Player
owns tick, speed and lifecycle; Streamlit fragments render a consistent snapshot.
A single-purpose Linux child calls the existing bounded collect_live API. A parent
watchdog cancels/reaps it on deadline or lost UI heartbeat. Saved captures are
raw-counter validated and decisions reconstructed, never trusted as current live data.

**Tech stack:** Existing Python, Streamlit 1.66, Plotly; standard-library processes/threads.

- [x] Write and run failing progression, saved-session, collection lifecycle and widget tests.
- [x] Implement player.py and sessions.py; verify actual 5/34 sample counts, drift rejection.
- [x] Implement worker.py and collection.py; mock isolation, timeout, cancellation, cleanup.
- [x] Integrate shared controls and timed fragment in app.py, retaining approved design/views.
- [x] Extend charts for source labels and actual transition markers; preserve evidence boundaries.
- [x] Run portable suite, static/archive/dependency checks and bounded real browser/startup checks.
- [x] Independent review, document Ubuntu-only checks and local recovery handoff.
- [x] Reverify remote freshness; include this plan in the authorized development-only checkpoint.

Final push/hash confirmation is reported in the chat after the commit, avoiding a
self-referential commit hash in this document. No main merge is authorized.

User specification fixes scope/architecture and authorizes implementation. No additional
design approval or real Linux collection on Windows is required. Main stays at 2753fc3.
