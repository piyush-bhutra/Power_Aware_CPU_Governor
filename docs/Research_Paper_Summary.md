# Research Paper Summary — Power-Aware CPU Governor
### Quick-recap reference. Read this if you've forgotten the details of any paper.

---

## Quick-reference table

| # | Paper | Venue/Year | Core method | Relevance to us |
|---|---|---|---|---|
| 1 | ZeroDVFS | arXiv, 2026 | LLM code-feature extraction + multi-agent RL | Shares our problem statement, nothing else — key differentiation paper |
| 2 | Memory-Aware DVFS Governing Policy | IEEE 2023 | CPI/memory-stall regression, reformulates schedutil | Defines memory-stall as a 3rd category we deliberately exclude |
| 3 | Power Management Techniques for Data Centers (Survey) | arXiv | Survey — DVFS formula + periodic-decision precedent | Source for our power model formula |
| 4 | Big Data Workload Profiling | arXiv 2026 | Decision-tree workload classification, cloud scale | Closest precedent for our Review-II ML classifier |
| 5 | zTT | ACM MobiSys 2021 (Best Paper) | Model-free RL, mobile CPU+GPU | RL precedent, future-work citation |
| 6 | CPU Frequency Scheduling w/ Deep RL | arXiv 2309.03779 | Profiles built-in governors, then builds RL alternative | Methodology precedent for our Phase-0-first approach |

---

## 1. ZeroDVFS: Zero-Shot LLM-Guided Core and Frequency Allocation for Embedded Platforms
**Pivezhandi, Banisharif, Saifullah, Jannesari — arXiv 2601.08166 (2026)**

**Summary:** Targets embedded multi-core boards (Jetson TX2, Jetson Orin NX, RubikPi, Core i7 baseline) running known OpenMP parallel benchmarks (FFT, Strassen, matrix multiplication, etc.). Uses model-based hierarchical multi-agent reinforcement learning (Double Dueling Deep Q-Networks) — one agent decides core count and frequency, a second manages per-core temperature to prevent thermal throttling. Its headline technique is using LLMs to extract 13 semantic features (algorithmic complexity, memory access patterns) directly from a program's **source code before execution**, enabling zero-shot deployment on unseen programs without target-hardware profiling.

**Key takeaways for us:**
- States the same motivating gap we open with: utilization conflates active execution time with stall time, hiding the real demand signal. This is one of the most common opening observations in the whole DVFS literature — sharing it is normal, not a sign of duplicated work.
- Demonstrates that a "profile-first" mentality (their multi-stage Profiler/Temperature agent split) is a well-established design pattern for reducing an unmanageable decision space.

**Limitations / why it's not our project:**
- Requires access to program **source code** — our governor works on arbitrary running processes with no source access, using only live runtime OS counters.
- Uses deep multi-agent RL with GPU training and per-query LLM API calls — heavy infrastructure incompatible with a 12-week course project.
- Targets embedded ARM boards with known parallel scientific benchmarks, not general-purpose desktop/VM workloads.
- **No I/O-bound classification at all** — iowait never appears in its feature set. Its whole framing is compute/thermal/core-allocation for parallel jobs, not the CPU-bound vs I/O-bound distinction that is the center of our project.
- Full second RL agent dedicated to thermal management — entirely out of our scope.

**Similarities:** Shared opening motivation only.

**Action for our project:** Cite in the report's related-work section explicitly as a *precedent-and-differentiation* citation — acknowledges the field has moved toward heavy ML/RL solutions for this gap, then explains why our lightweight, interpretable, runtime-signal-based approach is the right fit for a general-purpose system with unknown workloads, not a limitation of understanding.

---

## 2. Memory-Aware DVFS Governing Policy for Improved Energy-Saving in the Linux Kernel
**Shin, Kim, Hong — IEEE 29th International Conference on Embedded and Real-Time Computing Systems and Applications, 2023**

**Summary:** Directly critiques the **schedutil** governor — the same governor we benchmark against. Shows schedutil's CPU performance estimation (based on CPI, cycles-per-instruction) doesn't account for memory stalls caused by contention, leading to inaccurate frequency decisions. Proposes dynamically-constructed regression models that estimate expected workload and slack time for the next time slot, adjusting voltage/frequency accordingly.

**Key takeaways for us:**
- Establishes that "busy time" hides *multiple distinct stall causes* — not just I/O waits, but also memory stalls, cache misses, and contention. This is a genuinely useful three-way split to be aware of: CPU-bound / I/O-bound / **memory-bound** (a category we don't build for).
- Uses regression (a lighter ML technique than deep RL) to predict near-future workload — worth knowing as a middle ground between our rule-based classifier and heavier RL approaches, in case it's ever worth exploring later.

**Limitations / why it's not our project:**
- Requires CPI and memory-stall-cycle measurements, which need **hardware performance-monitoring-unit (PMU) counters** — frequently unavailable or restricted inside a VM (directly relevant to our own Phase 0 feasibility concerns).
- Focused specifically on memory contention, not the CPU vs I/O split we're building.

**Similarities:** Both explicitly critique schedutil's frequency-selection logic and propose an alternative decision method layered on the same governor family.

**Action for our project:** Use this to write a clean, deliberate limitation statement: *"Memory-bound workloads are a theoretically distinct third category, requiring PMU/CPI access typically unavailable in VM environments — consistent with our feasibility-first design philosophy (§5), and left as future work."* Turns a gap into a stated, defensible scope decision.

---

## 3. Power Management Techniques for Data Centers: A Survey
**arXiv 1404.6681**

**Summary:** A broad survey of data-center power-management techniques, of which DVFS is one section among several (alongside workload consolidation, VM migration, cooling-aware scheduling). States the standard CMOS dynamic power model directly: **P = P_static + C·F·V²**, where C is transistor gate capacitance, F is frequency, and V is supply voltage.

**Key takeaways for us:**
- **Direct source for our power estimation formula** — this is the citation for `docs/power_model.md` and `power_model/estimate.py`.
- Describes Sharma et al.'s and Hsu & Feng's DVFS algorithms, both of which take decisions **at the end of a fixed time period** using an estimation model — structurally the same periodic-tick design as our governor loop. Good precedent that a fixed-interval decision loop (rather than continuous/event-driven control) is an established, defensible pattern.
- Notes feedback-loop governors that keep instantaneous utilization **bounded** for QoS-sensitive servers — reinforces the value of our hysteresis/smoothing design in the policy engine.

**Limitations / why it's broader than us:** Data-center scale; covers many power techniques beyond CPU DVFS (cooling, VM placement) that are irrelevant to our single-machine scope.

**Similarities:** Shared periodic-decision-loop structure; shared DVFS fundamentals.

**Action for our project:** Cite the P = P_static + CFV² formula directly in the power model documentation. Cite the fixed-interval precedent to justify the tick-based loop design if questioned in a viva.

---

## 4. Big Data Workload Profiling for Energy-Aware Cloud Resource Management
**arXiv 2601.11935 (2026)**

**Summary:** Profiles Hadoop/Spark cluster workloads (CPU-bound Spark MLlib jobs, I/O-bound Hadoop shuffle-heavy jobs, ETL pipelines) to drive VM placement and consolidation decisions. Uses a **decision tree** trained on historical execution outcomes to rank candidate hosts by predicted energy impact. Also evaluates a neural network for comparison. Monitoring done via `dstat`/`perf` sampling **every 5 seconds**.

**Key takeaways for us — the most directly actionable paper of the six:**
- **Feature engineering:** their top-importance features were **ratios** — e.g. `cpu_mem_ratio` — not raw signals. Worth trying derived ratio features in our own classifier: `iowait / utilization`, `ctxt_rate / procs_running`, rather than relying on raw values alone.
- **Sampling interval reference point:** they used a 5-second interval; we're planning 1–2s. Worth running a small side-experiment comparing 1s/2s/5s intervals and reporting the responsiveness-vs-noise tradeoff — cheap to do, strengthens the report, and gives a defensible "we tested this" answer if asked why we chose our interval.
- **Accuracy benchmark to cite against:** reports ~97% accuracy for CPU-intensive workloads and ~98% for mixed workloads using a decision tree. When our own Review-II classifier accuracy comes in, we can frame it as *"comparable to published results in the adjacent domain of cloud workload profiling, adapted to a single-node OS-level context."*

**Limitations / why it's not our project:** Operates at cluster/VM-placement scale for scheduling and migration decisions, not single-node CPU frequency scaling. Its own paper notes the decision tree may not capture complex interactions in highly dynamic environments — a limitation to keep in mind for our classifier too.

**Similarities:** Directly parallels our planned Review-II decision-tree classifier — closest methodological precedent of all six papers.

**Action for our project:** (1) add ratio-based derived features to the classifier signal set, (2) run and report a sampling-interval comparison, (3) cite their accuracy figures as a comparison benchmark once our own numbers exist.

---

## 5. zTT: Learning-based DVFS with Zero Thermal Throttling for Mobile Devices
**Kim, Bin, Ha, Chong — ACM MobiSys 2021 (Best Paper Award)**

**Summary:** A deep reinforcement learning technique that jointly scales CPU and GPU frequencies on mobile devices to maximize application performance while avoiding thermal throttling entirely, adapting to changing thermal environments (e.g. how the phone is held) that conventional governors can't react to.

**Key takeaways for us:** Well-regarded, award-winning proof that RL-based DVFS is a legitimate, high-quality research direction — useful purely as a credible anchor citation, not for borrowing technique.

**Limitations / why it's not our project:** Mobile-specific (CPU+GPU joint control), application-specific reward function (tuned per app), heavy thermal focus — none of which applies to our general-purpose, thermal-agnostic, CPU-only scope.

**Similarities:** Both aim to do "smarter than utilization-only" DVFS.

**Action for our project:** Cite in the report's future-work section as the credibility anchor for why RL-based DVFS is a real, deliberately-deferred direction (§8.2 of the PRD) — not something we're unaware of, just not the right fit for a 12-week course project.

---

## 6. CPU Frequency Scheduling of Real-Time Applications on Embedded Devices with Temporal Encoding-Based Deep RL
**arXiv 2309.03779**

**Summary:** Targets periodic soft-real-time embedded tasks. Notably, before building their RL solution, the authors first **profiled the existing built-in Linux governors through kernel-level profiling** to understand exactly where and why they underperform for their target workload pattern, motivated by the observation that built-in governors focus on short-term characteristics and lack "macroscopic" knowledge of past/future computation.

**Key takeaways for us:** The **methodology**, not the technique, is the useful part — establish a baseline by profiling existing governors first, understand precisely where they fall short, *then* design the alternative. That's exactly the same move as our own Phase 0 feasibility check and baseline study.

**Limitations / why it's not our project:** Embedded, real-time soft-deadline periodic tasks — a different problem framing than general-purpose workload classification. RL-based, same reasoning as zTT for why we're not adopting the technique itself.

**Similarities:** Profile-existing-governors-first methodology mirrors our Phase 0 design directly.

**Action for our project:** Cite as a methodology precedent — validates that "baseline study before building" is standard, credible research practice, useful for defending our own Phase 0 sequencing in a viva.

---

## What we're actually incorporating (summary of actions)

1. **Ratio-based classifier features** — add `iowait/utilization` and `ctxt_rate/procs_running` alongside raw signals (from paper 4).
2. **Sampling interval experiment** — test and report 1s/2s/5s tradeoffs (from paper 4).
3. **Memory-bound out-of-scope note** — explicit, defensible limitation statement citing PMU/CPI requirements (from paper 2).
4. **Power model citation** — P = P_static + CFV² formula sourced to paper 3.
5. **ZeroDVFS differentiation paragraph** — related-work section explicitly contrasting method, platform, and signals (from paper 1).
6. **Accuracy benchmark target** — ~97–98% decision-tree accuracy as a comparison point once our own classifier is trained (from paper 4).
7. **Methodology justification** — cite papers 3 and 6 to defend the periodic-tick loop design and the profile-first Phase 0 sequencing if questioned.
