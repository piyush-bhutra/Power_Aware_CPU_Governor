# PRD v2 — Power-Aware CPU Governor
### A Workload-Adaptive CPU Frequency Scaling Policy for Linux Systems

**Course:** BITE303P — Operating Systems Lab
**Institution:** School of Computer Science Engineering and Information Systems, Department of Information Technology, VIT Vellore
**Semester:** Fall 2026-27
**Guide:** Prof. Harshita Patel
**Marks:** 40 (lab project), 4 VTOP upload slots × 10 marks each

**Registered team (3, per course requirement):**
- Piyush Bhutra — 24BIT0134
- Vedant Amol Doye — 24BIT0161
- Shubh Agrawal — 24BIT0160

**Actual working subset:** 2 people (Piyush + one partner), co-located in the same hostel — working model is joint/pair-based rather than siloed ownership. See §10.

**Current status:** Proposal report submitted and complete. VM not yet set up. No code written. This PRD is the scaffolding + shared-context document for starting implementation.

---

## 1. One-line summary

Every N seconds, sample the CPU core's aggregate state, classify what kind of workload that state represents, and set the core's clock frequency to match — saving estimated power on workloads where clock speed buys nothing, without slowing down workloads where it does.

---

## 2. Problem statement

Linux ships several built-in CPU frequency governors — `ondemand`, `performance`, `powersave`, `conservative`, `schedutil`. With the partial exception of `schedutil`, these scale frequency primarily from **aggregate CPU utilization**: one number describing how busy the CPU is.

The limitation: utilization alone doesn't say **why** the CPU is busy, or why it isn't. Consider a process blocked on disk I/O. When data finally arrives, it produces a short burst of high CPU utilization (parsing, copying, buffer handling) even though the process is fundamentally I/O-bound. `ondemand` sees that spike and ramps the clock toward maximum — burning power — despite the fact that the actual bottleneck is the storage device. The extra clock speed delivers **zero** real speedup, because the process will simply return to blocking on I/O moments later.

The inverse case matters too: genuinely compute-bound work (tight loops, encoding, numerical work) *does* convert clock speed directly into faster completion, and there under-clocking is a real performance loss.

Same utilization number, opposite correct responses. That gap is what this project addresses.

---

## 3. Core idea and novelty

**Contribution:** a governor that classifies the current workload before deciding frequency.

It reads a richer signal set than utilization alone — utilization %, I/O wait %, context-switch rate, ready-queue depth, blocked-queue depth, and interrupt time — and classifies the core's current state into a workload class (CPU-bound / I/O-bound / idle / mixed). A decision policy then maps that class to a target frequency.

**The novel/patentable contribution is the classification method plus the decision policy**, not the implementation shell around it. Power-optimization heuristics are a well-established patent category in OS and embedded systems, which supports the team's patent-track ambition.

> **Note:** for any actual patent filing, the team must consult VIT's technology transfer office. Nothing in this document constitutes legal or patent advice.

**Prior-art context to be honest about in the report:** workload-characterization-driven DVFS is a real, actively published research area. The project's claim should be framed as a specific classification+policy design and its empirical evaluation, not as inventing the category.

---

## 4. What this project is NOT (critical scope boundaries)

These boundaries were arrived at deliberately and should be stated in the report's scope section. They also pre-empt likely viva questions.

**We do not touch the scheduler.** The Linux scheduler (CFS) decides *which* process runs next, on which core, and for how long. All of that is untouched. Process ordering, queue membership, and time-slice allocation behave exactly as they would without our governor installed.

**We do not move processes between queues.** No process is promoted, demoted, migrated, or reprioritized. Queue state is *read* as an input signal only — never modified.

**We do not change time slices.** If the scheduler grants a process a 10ms quantum, it still gets 10ms at any frequency. What changes is how many instructions execute within that same 10ms — roughly twice as many at 3.2GHz as at 1.6GHz. The process gets the same *turn*, doing more or less *work* during it.

**Frequency is per-core, not per-process.** Clock frequency is a hardware property of a physical core. It is not possible to run process A at 3.2GHz and process B at 1.6GHz simultaneously on the same core. Every process scheduled onto that core during a given window experiences the same frequency. This is exactly how existing governors like `schedutil` already operate (they read aggregate run-queue utilization for a scheduling domain), so this introduces no new fairness class — but it must be stated correctly, because "per-process frequency" is a common misreading of the project.

**Deadlocks are out of scope.** Deadlock is a resource-allocation and synchronization problem (mutual exclusion, hold-and-wait, circular wait) belonging to an entirely different OS subsystem. This governor never touches locking, resource graphs, or allocation decisions, so there is nothing here to detect or prevent. Note: "predictive deadlock prevention" was one of the alternatives considered during topic selection and was consciously not chosen — worth being able to state that distinction cleanly if a reviewer conflates the two.

**Process priority (nice value / scheduling class) is not used in the MVP.** Deferred to future work — see §11.

**No physical hardware.** Runs in an Ubuntu Linux VM. No Raspberry Pi, no measurement rig.

**No measured wattage.** Power is *estimated* via a documented, cited frequency-to-power model. Every report sentence, chart axis label, and slide must say "estimated" or "modelled" — never "measured." Overclaiming measured power to evaluators is the single easiest avoidable credibility loss in this project.

**No full-stack web application.** This is a backend/systems project. The graded content is kernel-interface code, algorithm design, and benchmarking rigour. A UI earns no additional marks. See §9 for the optional terminal dashboard stretch goal.

**No reinforcement learning for the policy engine.** See §8.2 for the reasoning.

---

## 5. Phase 0 — critical feasibility check (do this before anything else)

VMs frequently do not expose real CPU frequency scaling to the guest OS. The hypervisor may hide `cpufreq` entirely, or expose it while silently ignoring writes. **This single unknown determines the implementation approach for two modules, so it must be resolved in week 1, not week 6.**

Once the Ubuntu VM is up, run:

```bash
ls /sys/devices/system/cpu/cpu0/cpufreq/
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver
```

Then verify writes actually take effect:

```bash
sudo cpupower frequency-set -g userspace
sudo sh -c 'echo <some_freq> > /sys/devices/system/cpu/cpu0/cpufreq/scaling_setspeed'
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq   # did it change?
```

**Outcome A — real control available** (`cpufreq` present, `userspace` governor listed, writes to `scaling_setspeed` visibly change `scaling_cur_freq`):
Build a real governor. Only the power *number* is estimated; the frequency control is genuine. This is the stronger version of the project.

**Outcome B — no real control** (directory missing, or writes are silent no-ops):
Build a software-simulated cpufreq layer — a module presenting the same interface and state transitions, driven by the policy's decisions, with the frequency-dependent effects modelled. The classification and policy logic (the actual novel contribution) are unaffected either way. Report framing shifts to "policy validated against a modelled frequency-response environment."

**Also determine during Phase 0:** how many vCPUs the VM exposes, and whether they share one frequency domain or scale independently. This decides whether the classifier/policy operates at whole-system or per-vCPU granularity.

**Deliverable:** record the outcome, raw command output, VM specs, and the resulting decision in `docs/vm_feasibility.md`. This file is a report input, not just a note.

---

## 6. How the system works (the loop)

The governor is a control loop firing at a fixed interval (start with 1–2 seconds; tune later):

```
1. WAKE UP (timer tick)

2. READ raw counters:
     /proc/stat        → cpu times (user, nice, system, idle, iowait, irq, softirq)
     /proc/stat ctxt   → cumulative context switches
     /proc/stat procs_running  → ready-queue depth
     /proc/stat procs_blocked  → processes blocked on I/O
     /sys/.../cpufreq/scaling_cur_freq → current frequency

3. COMPUTE DELTAS
     /proc/stat gives CUMULATIVE counters since boot. Rates require
     (current - previous) / interval. Using raw totals is the single
     most common bug in this kind of project — utilization would
     appear to converge to a constant and never move.

4. CLASSIFY  → CPU-bound / I/O-bound / idle / mixed

5. DECIDE    → policy maps class (+ persistence/confidence) → target frequency

6. ACT       → write scaling_setspeed (Outcome A) or update simulated state (Outcome B)

7. LOG       → append full row to CSV: timestamp, all raw signals, all deltas,
                classification, decision, resulting frequency, estimated power

8. SLEEP → back to step 1
```

Step 7 is load-bearing beyond logging: that CSV is simultaneously the benchmarking dataset, the source for every report chart, and the training data for the ML classifier in §8.1. The monitor module must be solid before anything downstream is trustworthy.

### Worked example (what you will actually see on screen)

A video encoder alternating between computing frames and writing output to disk:

| Tick | Signals | Class | Action |
|---|---|---|---|
| 1 | util 94%, iowait 1%, ctxt low, blocked 0 | CPU-bound | Frequency → **max**. Clock speed converts directly to frames/sec. |
| 2 | util 8%, iowait 76%, ctxt high (short frequent switches), blocked 1 | I/O-bound | Frequency → **low/medium**. Disk is the bottleneck; extra clock buys nothing. |
| 3 | util 91%, iowait 2%, blocked 0 | CPU-bound | Frequency → **max** again. |

At no point was the encoder moved between queues, reprioritized, or given a different time slice. Only execution speed changed.

This exact sequence is reproducible on demand once the monitor exists: run `stress-ng --cpu 1`, then `stress-ng --io 1`, and watch the classification flip live.

---

## 7. Architecture

```
[/proc, /sys readers] → [Workload classifier] → [Policy engine] → [Frequency setter]
          │                                            │
          └──────────────────┬─────────────────────────┘
                             ▼
                    [CSV log / dataset]
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     [Power model]  [Benchmark harness]  [ML classifier training]
                             │
                             ▼
                    [Analysis / charts]
```

### Module 1 — Monitor

Reads and rate-converts kernel counters. Owns the delta computation.

| Signal | Source | Why it's used |
|---|---|---|
| CPU utilization % | `/proc/stat` cpu line | Baseline busy-ness; what stock governors use |
| I/O wait % | `/proc/stat` iowait field | Distinguishes "blocked on device" from "computing" |
| Context-switch rate | `/proc/stat` `ctxt` (delta) | I/O-bound work shows frequent short switches; compute-bound shows long uninterrupted bursts |
| `procs_running` | `/proc/stat` | **Direct ready-queue depth** — real scheduler contention, not inferred |
| `procs_blocked` | `/proc/stat` | **Direct blocked-queue depth** — processes waiting on I/O |
| `irq` / `softirq` time | `/proc/stat` | Device-driven activity; corroborates I/O-bound classification independent of iowait |
| Current frequency | `/sys/.../scaling_cur_freq` | Feedback / verification that actions took effect |

The queue-depth and interrupt signals are a deliberate strengthening over the original proposal, which used only the first three. Reading actual scheduler queue depth is a materially stronger claim in the report than inferring contention from context-switch rate alone, and costs nothing — the fields are in a file already being parsed.

Output: one CSV row per tick.

### Module 2 — Workload classifier (rule-based)

Threshold rules over the Module 1 signals producing one of four labels:

- **CPU-bound** — high utilization, low iowait, low context-switch rate, low blocked count
- **I/O-bound** — low-to-moderate utilization, high iowait, high context-switch rate, blocked > 0, possibly elevated softirq
- **Idle** — low utilization, low iowait, empty-ish run queue
- **Mixed** — anything not cleanly matching the above

Thresholds are tuned empirically against known `stress-ng` workloads (see §8.3). Every threshold must be justified in the report with the data that produced it — "we chose 30% because" is a graded sentence.

Fully interpretable by design; the rules can be printed directly into the report.

### Module 3 — Policy engine

Maps workload class → target frequency. **This plus Module 2 is the core novel contribution.**

Key design requirement — **hysteresis / smoothing.** A naive implementation acts on every single tick's classification, which produces *frequency thrashing*: rapid up-down oscillation when a workload sits near a threshold or when heterogeneous processes interleave on one core. Thrashing can hurt both power and performance and looks bad in a live demo. Mitigations to implement:

- Require a class to persist for K consecutive ticks before acting on a change (K ≈ 2–3 as a starting point)
- Optionally use asymmetric response: ramp up quickly (protects performance), ramp down slowly (avoids latency spikes on work resumption)
- Optionally step frequency gradually rather than jumping min↔max

This is not a nice-to-have. It is the mitigation for the main fairness/stability risk in §12 and should be presented that way in the report.

### Module 4 — Frequency setter

Writes to `scaling_setspeed` (Outcome A) or updates simulated cpufreq state (Outcome B). Kept as a thin, swappable layer specifically so the Phase 0 outcome doesn't ripple into Modules 2 and 3.

### Module 5 — Power estimation model

A documented, cited frequency-to-power estimation (e.g. based on published CMOS dynamic power relations, where power scales with frequency and the square of voltage). Requirements:

- Formula stated explicitly in the report with its source cited
- Assumptions and limitations stated plainly
- All outputs labelled "estimated" / "modelled" everywhere, without exception

### Module 6 — Benchmark harness

Automates identical workloads across governors and records results.

- Governors compared: **ours** vs `ondemand`, `performance`, `powersave`, `schedutil`
- Workloads: `stress-ng` synthetic profiles — CPU-bound (`--cpu`), I/O-bound (`--io`, `--hdd`), memory (`--vm`), mixed, and idle baseline
- Metrics: average frequency, estimated power/energy, task completion time, classification distribution
- Multiple repeated runs per configuration; report means (and ideally variance) rather than single runs — single-run numbers are not defensible

### Module 7 — Analysis

pandas + matplotlib over the benchmark CSVs. Produces the comparison charts that carry the results chapter and the Review II presentation.

### Module 8 (stretch) — Live terminal dashboard

See §9.

---

## 8. Machine learning: scope and sequencing

ML-driven DVFS is a legitimate, published research direction. The question is which parts are worth the risk in a 12-week course project. The answer splits cleanly.

### 8.1 ML for classification — YES, planned as the Review II increment

This is a straightforward supervised classification problem:

- **Features:** utilization, iowait, ctxt rate, `procs_running`, `procs_blocked`, irq/softirq time
- **Labels:** the workload type you deliberately generated (you *told* `stress-ng` to run `--cpu` vs `--io`, so ground truth is free)
- **Model:** decision tree (or logistic regression) — chosen specifically because it is **interpretable**. The tree's splits can be printed in the report and defended in a viva.
- **Training data:** already being produced by the benchmark runs; no separate data-collection effort needed
- **Deliverable framing:** "rule-based thresholds vs. trained classifier — accuracy compared on held-out synthetic workloads"

Terminology note for the report: **neither classifier is a black box.** Threshold rules are explicit; a decision tree's splits are printable. Avoid a neural net here — it would sacrifice the interpretability that makes this defensible in an OS course, and buys nothing in return.

**Sequencing decision:** announce this plan to the faculty **at Review I**, presented as the already-planned Review II increment. Executing a stated roadmap reads far better to reviewers than an enhancement appearing from nowhere.

**Honest limitation to state:** a classifier trained only on synthetic `stress-ng` patterns will not necessarily generalize to real-world workloads. State this as a known limitation rather than letting a reviewer find it.

### 8.2 RL for the policy engine — NO (documented as future work)

Learning the frequency policy via reinforcement learning (reward = −power − λ×slowdown) is what real ML-DVFS papers do, and it is genuinely interesting. It is rejected here for concrete reasons:

- Reward shaping is a trap — a naive reward is trivially maximized by always selecting the lowest frequency, tanking performance
- RL requires many training episodes and careful tuning
- RL policies behave unpredictably in live demos, which is exactly the wrong risk profile for a graded Review II demonstration
- The rule-based policy is explainable; an RL policy is much harder to defend in a viva

The rule-based policy engine remains the core deliverable. RL is named in the report's future-work section as a considered and deliberately deferred direction — which demonstrates awareness without betting the project on it.

### 8.3 Threshold tuning (prerequisite for both)

Before either classifier is trustworthy, run known `stress-ng` workloads and record the signal ranges each produces. This produces both the hand-tuned thresholds for Module 2 and the labelled training set for §8.1. Do this once, properly, early.

---

## 9. User interface — scope decision

**The graded core is terminal/backend. No UI is required.** matplotlib charts in the report are sufficient for the results chapter.

However, demo-ability was one of the team's own topic-selection criteria, and a live view does land better at Review I/II than scrolling raw terminal output. Options considered:

| Option | Verdict |
|---|---|
| No UI, charts only | Fully acceptable. Zero risk. |
| **Terminal dashboard (`rich` / `textual`)** | **Recommended stretch goal.** Live panel: current class, live frequency, running estimated power, mini sparkline. ~1 day of work, same Python stack, thematically consistent with a systems project. |
| Web dashboard (Flask + frontend) | Rejected. Extra stack, extra failure surface, zero additional marks. |

**Decision rule:** build the core pipeline first. Only after Review I, and only if genuinely ahead of schedule, add the `rich`/`textual` dashboard as demo polish. If searching for design references now, search "python textual TUI dashboard" or "rich library live dashboard" — not web component libraries.

---

## 10. Working model (2 people, co-located)

Because both members are in the same hostel, coordination overhead is low and pair-based work beats siloed ownership — it avoids the classic integration failure where the monitor's output shape doesn't match what the policy module expected.

**Model:** work through the pipeline phases together in shared sessions. Pair on the conceptually tricky parts (classifier thresholds, hysteresis design, power model). Split trivially parallel chores within the same session (one writes the `/proc` parser while the other writes the CSV logger).

**For the formal report:** the proposal already lists a 3-way role split for the registered team. Present role attribution in the report consistently with what was submitted; internal working practice being more collaborative is normal and not something the report needs to litigate.

---

## 11. Tech stack

- **Language:** Python throughout. `/proc` and `/sys` are plain text files; `subprocess` drives `stress-ng`; pandas/matplotlib are needed for analysis anyway. No reason to introduce C — one language means both members can review all code, and it removes build-system friction entirely.
- **Core libraries:** stdlib (`os`, `time`, `csv`, `subprocess`, `signal`). Optionally `psutil`, though parsing `/proc/stat` directly is more defensible in an OS lab report.
- **Workload generation:** `stress-ng`
- **Analysis:** `pandas`, `matplotlib`
- **ML (Review II):** `scikit-learn` (`DecisionTreeClassifier`)
- **Stretch UI:** `rich` or `textual`
- **Frequency control:** `cpupower` / direct sysfs writes (requires root)
- **VCS:** Git, shared repo

---

## 12. Design considerations and risks

**Frequency thrashing.** Rapid classification flips → rapid frequency flips → potential harm to both power and performance, plus a visibly unstable demo. *Mitigation:* K-consecutive-tick persistence requirement and asymmetric ramp rates in the policy engine (§ Module 3). Present this in the report as an identified risk with an implemented mitigation — that framing is worth marks on its own.

**Fairness across interleaved processes.** If a CPU-bound and an I/O-bound process time-share one core, the classification reflects the *mix*, and both processes experience whatever frequency results. This is not a new fairness class — `schedutil` already sets frequency from aggregate scheduling-domain utilization — but it should be stated explicitly rather than discovered by a reviewer.

**Monitoring overhead is O(1) in process count.** `/proc/stat` is a fixed-size aggregate the kernel maintains regardless; reading it costs the same with 10 processes or 10,000. Classification is a few comparisons or one tree traversal — negligible against the cost of a context switch. The approach is therefore production-plausible at scale, not a toy-only trick. Worth measuring and reporting the actual overhead.

**Classification confidence degrades under heavy multiprogramming.** With many heterogeneous processes interleaved, "the workload" becomes a moving average and the `mixed` class will legitimately dominate. State as a known limitation shared with all aggregate-utilization governors — not a defect unique to this design.

**Per-core / per-cluster DVFS is out of scope.** Real hardware (notably ARM big.LITTLE) allows independent per-core or per-cluster frequency domains. The VM will expose either a single shared domain or a small number of vCPUs. Scope the classifier and policy explicitly at whole-system or per-vCPU granularity per the Phase 0 finding, and list independent per-core scheduling domains as future work.

**Cumulative-counter bug.** `/proc/stat` values are cumulative since boot. Failing to difference consecutive readings produces silently wrong, slowly-converging metrics. Call this out in code comments and verify early.

**Root requirement.** Writing frequency requires root. Decide early how the governor is launched (sudo, systemd unit, capability) and document it in the README so demos don't fail on permissions.

**Future work (report section, not build targets):**
- Priority-aware policy — e.g. suppress downscaling for high-priority (low nice) processes even when momentarily idle-classified, to avoid latency spikes
- RL-learned policy (§8.2)
- Independent per-core frequency domains
- Validation against real (non-synthetic) workloads
- Real wattage instrumentation on physical hardware

---

## 13. Repository structure

```
power-aware-governor/
├── README.md                  # setup, how to run, root requirements
├── docs/
│   ├── vm_feasibility.md      # Phase 0 output — outcome A or B, raw command output
│   ├── thresholds.md          # tuned thresholds + the data justifying each
│   └── power_model.md         # formula, citation, assumptions, limitations
├── monitor/
│   └── reader.py              # /proc + /sys parsing, delta computation, CSV logging
├── classifier/
│   ├── rules.py               # threshold-based classifier
│   └── ml_model.py            # decision tree (Review II)
├── policy/
│   └── governor_policy.py     # class → frequency, hysteresis, ramp rates
├── setter/
│   └── freq_setter.py         # real sysfs write OR simulated layer
├── power_model/
│   └── estimate.py
├── benchmark/
│   ├── workloads.py           # stress-ng profiles
│   └── run_benchmarks.py      # automated multi-governor comparison runs
├── analysis/
│   └── plots.py
├── dashboard/                 # stretch goal only
├── data/                      # raw CSV logs (gitignore large runs)
└── report/                    # figures, drafts for Review I / II / final
```

---

## 14. Phase plan

Map these onto actual VTOP Review I / Review II dates once known — the original 12-week proposal timeline is a guide, not a schedule this document tracks.

| Phase | Work | Output |
|---|---|---|
| **0** | Ubuntu VM setup, cpufreq feasibility check, repo init, git workflow agreed | `docs/vm_feasibility.md`, working repo |
| **1** | Monitor module — parse `/proc/stat` and `/sys`, compute deltas, log CSV | Verified CSV logger with all 7 signals |
| **2** | Threshold tuning + rule-based classifier, validated against `stress-ng` profiles | `docs/thresholds.md`, working classifier |
| **3** | Policy engine (with hysteresis) + frequency setter | End-to-end loop: sense → classify → act → log |
| — | **REVIEW I** — architecture diagram, module design, flowcharts, 40–50% implementation, screenshots, challenges. **Announce ML classifier as planned Review II increment.** | Design & Progress Report |
| **4** | Power estimation model, documented and cited | `docs/power_model.md`, `estimate.py` |
| **5** | Benchmark harness — automated runs vs 4 stock governors, repeated trials | Result CSVs |
| **6** | Analysis + charts; ML classifier trained and compared vs rules | Report figures, accuracy comparison |
| — | **REVIEW II** — full benchmark results, ML comparison | Review II deliverable |
| **7** | Final project report using existing `OS_Project_Report.docx` template | Final report |
| **8** | Presentation, 15–20 slides | Final PPT |
| *stretch* | `rich`/`textual` live dashboard | Demo polish only, post-Review-I, only if ahead |

---

## 15. Deliverables (VTOP — 4 slots, 10 marks each)

1. **Project Proposal Report** — ✅ **COMPLETE.** `Project_Proposal_Report.docx` delivered, containing all 8 required sections (problem statement, objectives, scope, literature/background, methodology, tools, work plan, team responsibilities), formatted to spec.
2. **Project Design & Progress Report (Review I)** — not started. Needs architecture, module design, algorithms/flowcharts, 40–50% implementation progress, screenshots, challenges faced.
3. **Final Project Report** — not started. Full documentation: introduction, design, implementation, testing, results, conclusion, future enhancements, references, source code appendix. Template `OS_Project_Report.docx` already in hand.
4. **Final Presentation (PPT)** — not started. 15–20 slides.

---

## 16. Report formatting requirements (from the official template)

- Font: Times New Roman throughout
- Main headings: 16pt bold · Sub-headings: 14pt bold · Sub-subheadings: 12pt bold · Body: 12pt
- Line spacing 1.5, justified alignment
- Page numbers bottom centre
- Figure captions **below** figures ("Figure 1.1: Architecture of…"); table captions **above** tables ("Table 2.1: …")
- References in MLA format, **minimum 15** for the final report

---

## 17. Success criteria

- Monitor reliably logs all seven signals with correct rate/delta computation
- Rule-based classifier correctly labels at least three distinct synthetic workload types, with every threshold justified by recorded data
- Policy engine demonstrably behaves differently from `ondemand` — if the output traces are near-identical, the project has not demonstrated its premise
- No visible frequency thrashing under threshold-boundary workloads (hysteresis demonstrably working)
- Benchmark produces a clean comparison across our governor and at least three stock governors on frequency, estimated power, and completion time, from repeated runs
- ML classifier trained and its accuracy compared against the rule-based baseline
- All power figures labelled estimated/modelled throughout
- Final report meets formatting spec with ≥15 MLA references

---

## 18. Open decisions

- **VM cpufreq feasibility (Outcome A vs B)** — blocks Modules 1 and 4 implementation detail. Resolve in Phase 0.
- **Frequency-domain granularity** (whole-system vs per-vCPU) — falls out of the Phase 0 finding.
- **Sampling interval** — start at 1–2s, tune empirically; shorter is more responsive but noisier and more thrash-prone.
- **Hysteresis constant K** — start at 2–3 consecutive ticks, tune during Phase 3.
- **Stretch dashboard** — build or skip; decide after Review I based on remaining time.

---

## 19. Related but separate deliverable — BITE303L case study

**Not covered by this PRD.** BITE303L (Operating Systems theory) requires an **individual, solo** case study worth 20 marks, following a 21-section report structure. It is a separate submission from this team lab project.

OS candidates discussed but never finalized: QNX (microkernel RTOS), Android, Fedora / Rocky Linux, Zephyr RTOS — with a lean toward QNX or Android for richer, less generic content. **Still open; needs to be revisited separately.**

---

## 20. Reference files (from the original planning chat)

- `OS_Project_Report.docx` — official final-report template with structure and formatting rules
- `Operating_Systems_Lab_Project_Guidelines.pdf` — lab project rules (40 marks, team of 3, Review I/II, 4 VTOP deliverables)
- `Operating_Systems_Case_Study_guidelines.pdf` — case study rules (20 marks, individual, 21 sections)
- `OPERATING-SYSTEMS-LAB.pdf` / `OPERATING-SYSTEMS.pdf` — official syllabi for BITE303P and BITE303L
- `Sample_Problem_Statements.doc` / `Sample_Project_Ideas.doc` — teacher-provided sample topics, used during selection to steer away from the crowded CPU-scheduling space
- `Project_Proposal_Report.docx` — the completed and submitted proposal

**Topic-selection context:** ~280 students across 4 classes take this course and lab topics must be unique. The teacher's own sample lists were heavily concentrated in CPU scheduling variants, deadlock/dining philosophers, and disk scheduling + caching — so those areas will be crowded. Power/performance management appeared nowhere in those lists, which is a substantial part of why this topic was chosen.
