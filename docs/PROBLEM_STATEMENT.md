# Problem statement

Power-Aware CPU Governor: a workload-adaptive CPU frequency policy for Linux
(BITE303P Operating Systems Lab). Last updated October 19, 2026.

## 1. Problem

Common Linux frequency governors decide CPU frequency mainly from aggregate CPU
utilization. Utilization alone does not say *why* the CPU is busy or idle. A process
that repeatedly blocks on disk or network I/O and a process that computes
continuously can look similar in a single utilization number, yet they may need
different frequency treatment. Frequent switching on short spikes also wastes
transitions and makes behaviour hard to explain.

## 2. Motivation

- Linux exposes cheap, unprivileged aggregate signals in `/proc/stat` (CPU time split
  into user, system, idle, I/O wait, IRQ; context switches; runnable and blocked
  process counts) that say more about workload type than utilization alone.
- A transparent rule set plus hysteresis is easy to inspect, log and explain, which
  matters for a course project and for debugging any policy.
- Before any real deployment, the policy's response dynamics (lag, suppressed bursts,
  stability) and its own CPU cost should be understood.

## 3. Objectives

1. Monitor `/proc/stat` correctly: deltas not totals, measured elapsed time, rejection
   of invalid intervals.
2. Classify each interval as `cpu_bound`, `io_bound`, `idle` or `mixed` with
   transparent rules.
3. Map classes to target frequencies with K-tick hysteresis to avoid thrashing.
4. Apply decisions through a simulated setter (the VM has no cpufreq) and log every
   decision with its reason.
5. Compare against Python approximations of performance, powersave, ondemand and
   conservative on identical inputs, using a modelled energy estimate.
6. Measure the governor's own CPU cost and study sensitivity to K and to the
   sampling interval.
7. Present all of this in a terminal tool (Governorlab) and a local dashboard
   (Daybreak), with every number traceable to evidence.

## 4. Scope

In scope: user-space Python prototype; aggregate `/proc/stat` monitoring on Linux;
rule-based classification; hysteretic policy; simulated actuation; modelled power;
synthetic replay and bounded background-only live observation on the Ubuntu VM;
overhead and sensitivity tooling; saved, revalidated sessions.

## 5. Non-goals

- Not a kernel scheduler; does not change run queues or scheduling.
- No per-process frequency (frequency is a core/domain property).
- No physical frequency control on the VM; no measured electrical power.
- No machine-learning classifier in the current build (the original PRD planned a
  decision tree for Review II; it has not been implemented).
- No claim of beating schedutil, RL-based governors or any production governor.

## 6. System overview

```
/proc/stat (measured) -> monitor.reader (deltas, rates, validity checks)
   -> classifier.rules.classify (4 classes, provisional thresholds)
   -> policy.Policy (class target + K=3 hysteresis)
   -> SimulatedSetter (simulated frequency, no hardware writes)
   -> power_model (modelled watts) -> CSV / saved session
   -> Governorlab (terminal) and Daybreak (dashboard) replay
```

Live collection (Linux) saves sessions in `run/` in one format shared by both
interfaces. Tolerant collection discards intervals with VM timing anomalies and
discloses each discard. Benchmarks: five-policy comparison (synthetic),
sensitivity study (synthetic), overhead tool (Linux).

## 7. What is measured and what is simulated

| Quantity | Status | Source |
|---|---|---|
| CPU time split, context switches, runnable/blocked counts | **Measured** (Linux kernel counters) | `/proc/stat` on the Ubuntu VM |
| Elapsed time per interval | **Measured** (monotonic clock) | `time.monotonic()` |
| Utilization, I/O wait %, context switches/s | **Derived** from measured counters | `monitor/reader.py` |
| Workload class | **Predicted** by provisional rules (not ground truth) | `classifier/rules.py` |
| Target / applied frequency | **Simulated** | `policy/`, `setter/SimulatedSetter` |
| Power, energy, savings | **Modelled** (formula fitted to published TDP figures) | `power_model/estimate.py`, `docs/power_model.md` |
| Governor CPU cost | **Measured** process CPU time on the VM (smoke runs only; full run pending) | `benchmark/overhead.py` |
| Completion time, real DVFS, electrical energy | **Not measured** | — |

## 8. Assumptions

- Frequency ladder: four steps from the Ryzen 7 7840HS base clock 3.8 GHz to boost
  5.1 GHz (`hardware_profile.py`). Real hardware has lower P-states.
- Power model: P = 21.6 + 32.4·(f/5.1 GHz)³·util/100 W, a two-point fit to AMD's
  published 35-54 W TDP range (`docs/power_model.md`).
- Class-to-frequency fractions (idle 0.0, io 0.3, mixed 0.6, cpu 1.0) and classifier
  thresholds (`docs/thresholds.md`) are hand-chosen and provisional.
- The VM's timer overshoots by about 10 %; validity thresholds for an interval are
  0.5-2 s elapsed and 0.5-1.5x the expected CPU-accounting rate.

## 9. Related work and positioning

This section uses only what `docs/Literature_Review_Notes.md` (prepared 2026-10-18)
reports. Those notes were compiled from arXiv abstract pages, full arXiv texts read
through an automated reader, publisher pages and Linux kernel documentation; items
the notes mark **UNVERIFIED** are marked the same way here. Each claim below should
be checked against the original source before it goes into the final report.

**What Linux already does.**
- *schedutil* chooses frequency from PELT utilization (documented as
  f = 1.25 × util × f_max) with utilization estimation, uclamp and a rate limit
  (kernel schedutil and cpufreq documentation).
- schedutil already has an **I/O-wait boost**: when a task wakes after I/O, utilization
  is boosted so I/O completes sooner (LKML iowait-boost patch). This points the
  *opposite* way to this project's policy, which lowers frequency for I/O-bound phases.
- *ondemand* historically treated I/O wait as idle, which caused slow-downs during
  disk I/O; a 2010 LKML discussion argued that finishing sooner lets the CPU idle
  longer, i.e. energy rather than power is what matters.
- *amd-pstate* (the 7840HS driver): in active mode firmware chooses frequency from an
  energy-performance-preference hint; passive/guided modes accept OS targets or bounds
  (kernel amd-pstate documentation).
- *auto-cpufreq* is the closest architectural sibling: a user-space daemon switching
  governor/turbo/EPP profiles from usage, temperature, load and battery; its README
  lists no I/O-wait signal.

**Counter-based and learned DVFS.**
- Green Governors (Spiliopoulos, Kaxiras, Keramidas, IGCC 2011) used stall/IPC
  counters for memory-bound programs and reported governor overhead "well below 1%"
  at a 50 ms interval.
- Recent work (zTT, MobiSys 2021; GearDVFS, MobiCom 2023; Zhou & Lin, arXiv 2309.03779;
  MetaDVFS, arXiv 2509.22707; ZeroDVFS, arXiv 2601.08166) is dominated by
  reinforcement learning on mobile or embedded boards. ZeroDVFS reports a 358 ms
  decision latency.
- Parikh et al. (arXiv 2601.11935) label workloads by dominant resource with rules; the
  notes found it is not a decision-tree workload classifier, contrary to the team's
  earlier summary.
- The Memory-Aware DVFS paper (IEEE RTCSA 2023) is confirmed by venue only; its
  authors and method are **UNVERIFIED** in the notes.

**Positioning.** According to the notes, each element of this project is individually
not new: counter-based classification, utilization governors reading `/proc`-class
signals, rule-based dominant-resource labelling, hysteresis, and I/O awareness all
exist. **This project does not claim a new governor algorithm.** The defensible
contribution is a narrow evaluation question:

> Can an interpretable, I/O-aware, hysteresis-gated user-space policy match a
> utilization governor's performance at lower estimated energy, and under what
> conditions does lowering frequency for I/O-bound phases help or hurt, given that
> schedutil boosts frequency on I/O wake-ups?

Nothing in the repository answers that question yet. Answering it requires a
schedutil-style baseline, closed-loop workloads where lower frequency stretches
completion time, an energy-delay metric, and measured energy on real hardware; all
are **pending**. What exists today is the instrumented prototype, the synthetic
sensitivity study (lag of exactly K - 1 ticks, bursts shorter than K suppressed;
`evidence/phase1b_sensitivity/`) and the overhead tool.

**Limits stated plainly.** Power is modelled, frequency is simulated, baselines are
Python approximations without schedutil, the 3.8-5.1 GHz ladder omits the lower
P-states where most real savings occur, the VM cannot show hardware behaviour, and
classifier accuracy on labelled workloads is unknown.

**Sources (as listed in the notes).** Kernel cpufreq guide
https://docs.kernel.org/admin-guide/pm/cpufreq.html ; amd-pstate
https://docs.kernel.org/admin-guide/pm/amd-pstate.html ; schedutil
https://docs.kernel.org/scheduler/schedutil.html ; schedutil iowait boost patch
https://lkml.iu.edu/hypermail/linux/kernel/1804.1/02723.html ; ondemand disk-I/O thread
https://lkml.iu.edu/hypermail/linux/kernel/1004.2/00692.html ; auto-cpufreq
https://github.com/AdnanHodzic/auto-cpufreq ; Green Governors
https://pages.cs.wisc.edu/~kaxiras/papers/igcc11_green_governors.pdf ; zTT
https://ee.kaist.ac.kr/ai-in-computer/ztt-learning-based-dvfs-with-zero-thermal-throttling-for-mobile-devices-acm-mobisys-2021-best-paper-award/ ;
GearDVFS https://github.com/geardvfs/GearDVFS ; Zhou & Lin https://arxiv.org/abs/2309.03779 ;
MetaDVFS https://arxiv.org/abs/2509.22707 ; ZeroDVFS https://arxiv.org/abs/2601.08166 ;
Parikh et al. https://arxiv.org/abs/2601.11935 ; Mittal survey (power equation)
https://arxiv.org/abs/1404.6681 .
