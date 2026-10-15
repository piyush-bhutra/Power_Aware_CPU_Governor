# Development roadmap after stable milestone integration

Agreed in user-invoked `prompts/Stable_Milestone_Integration.txt`, October 15, 2026.
Main's verified baseline is `207e7326369506c4e9021cc8f397c50c06fb3794`.
Development remains the remotely backed-up active branch. This roadmap authorizes
no frontend implementation, installation or experiment by itself.

## Track A — OS Course Project v1.0

Goal: a reliable, visually presentable, reproducible workload-aware CPU governor
prototype for the undergraduate course. Review 1 is October 16, 2026.
The foundation comprises real aggregate Linux monitoring, provisional rule-based
classification, adaptive decisions with K-tick hysteresis, simulated selection,
synthetic comparisons and modelled energy, a successful five-row background
observation, bounded collection and safety infrastructure.

Near-term priorities, in order:

1. Stable Git baseline and preserved evidence (established by this integration).
2. Professional local demonstration dashboard after frontend brainstorming finishes.
3. Clear separation of real monitoring and synthetic simulation.
4. Reproducible one-command launch with minimal VM resource use.
5. Architecture documentation and demonstration screenshots.
6. Short Review 1 explanation of algorithms, verified progress and limits.
7. Course-project final packaging and verification.

Use offline/replay evidence first; the dashboard does not require new stress runs.
Real labelled accuracy and physical energy are future investigations, not promises
needed to present the existing prototype. Current terminal/PNG presentation remains
available while dashboard design is pending.

## Track B — Longer-term research development

After the academic demonstration is stable, investigate controlled CPU-bound,
I/O-bound and mixed datasets; classification accuracy/calibration; stronger frequency
policies; adaptive hysteresis and transition cost; better energy/performance models;
physical CPUFreq actuation on supported Linux hardware; actual energy measurements
if hardware permits; repeated meaningful baseline comparisons; literature and novel
contribution feasibility. Research-paper exploration and patent prior-art assessment
are separate future tasks. No novelty or patentability conclusion has been established.
These are not mandatory prerequisites for the undergraduate demonstration.

## Frontend objectives and boundaries

Another ChatGPT conversation is brainstorming frontend UX. No design is final.
Preferred technology is currently Streamlit with optional Plotly and justified Pandas
use, reusing existing Python modules. These are preferences, not installed components
or a committed architecture. Do not implement UI, install dependencies, generate
mockups or change backend APIs in anticipation of that design.

Priorities: low VM resource use, strong presentation, reliable offline/replay operation,
clear explanations, honest provenance labels and simple one-command startup. No fake
live data, fabricated savings or unnecessary frontend/backend infrastructure.
Possible sections are overview/architecture, Linux monitoring, classification,
simulated decisions/hysteresis, policy comparisons/modelled energy and methodology/
limitations. These are candidate topics, not an approved layout.

Use [dashboard integration handoff](DASHBOARD_INTEGRATION_HANDOFF.md) when the design
is finalized. Any actual live monitoring must be an explicit bounded operation;
the dashboard must not automatically launch collectors, stress or hardware writes.

## Git milestones

Review the full accumulated main-to-development diff, tests, limitations, remote
alignment and historical branches at each meaningful milestone. Assess READY/DEFER/
BLOCKED and integrate only after explicit approval, preferably fast-forward-only.
No blind pulls/merges, force-pushes, history rewrites or historical branch deletion.
Keep documentation with the deliverable it describes; avoid separate trivial commits
or automatic main integrations. The synthetic archive/roadmap commit follows the
approved integration on development and needs its own assessment/approval for main.
