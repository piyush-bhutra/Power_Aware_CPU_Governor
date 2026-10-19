# Power-Aware CPU Governor — Literature Check and Positioning

Prepared 2026-10-18 for BITE303P. Covers: (A) verification of the six papers in `docs/Research_Paper_Summary.md`, (B) recent and related work, (C) where the project stands (novelty), (D) the overhead question, (E) real deployment, (F) what to change in the build plan.

**How this was checked.** Paper details come from arXiv abstract pages, the full arXiv texts (read through an automated reader, not by me line by line), publisher/repository pages and Linux kernel documentation. Anything I could not open is marked **UNVERIFIED**. Where I say a claim is "not in the paper", please confirm with Ctrl-F in your own copy of the PDF before you edit the report. The web search tool returned little 2025–2026 material specific to your niche, so "I did not find X" below means exactly that, not "X does not exist".

---

## A. Verification of the six papers in your notes

| # | Paper | Verdict |
|---|---|---|
| 1 | ZeroDVFS | Mostly confirmed. Two additions worth knowing (below). |
| 2 | Memory-Aware DVFS Governing Policy | Venue confirmed. Authors and content **UNVERIFIED**. |
| 3 | Mittal, Data Center Power Survey | Equation confirmed. Notes over-reach slightly. |
| 4 | Big Data Workload Profiling | **Several claims in the notes do not match the paper.** |
| 5 | zTT | Confirmed. |
| 6 | Zhou & Lin, temporal-encoding DRL | Confirmed. |

### Paper 4 is the one to fix before you write anything
The notes say this paper uses a decision tree to *classify workloads*, compares it to a neural network, reports about 97% and 98% accuracy, found `cpu_mem_ratio` to be the top feature, and is the "closest precedent for our ML classifier". What I found in the full text:

- The decision tree **ranks candidate hosts** for VM placement by predicted energy impact and SLA risk. It is not a workload classifier.
- Workload classification is **rule-based**: each workload is labelled by its dominant resource (argmax over CPU, memory, disk I/O). The authors list "unsupervised learning to identify workload patterns without manual classification" as *future work*.
- I found **no accuracy figures, no feature-importance analysis, no `cpu_mem_ratio`, and no neural-network comparison**. The numbers it reports are 15–20% energy reduction and under 5% change in job time.
- The 5-second `dstat`/`perf` sampling interval **is** in the paper.
- DVFS is only mentioned as a complementary technique and is **not evaluated**.

Consequences: do not cite 97–98% accuracy as a benchmark, and do not call it a decision-tree classification precedent. Actions 1, 2 and 6 in your "what we're incorporating" list lean on it. Ironically, it gives you a precedent for your *rule-based* classifier (dominant-resource labelling). It is also a 4-author arXiv preprint with no venue listed, so cite it lightly. I could not tell where the 97%/98% and `cpu_mem_ratio` details came from; check whether they came from a different paper or from an AI-generated summary.

### Paper 1: ZeroDVFS (Pivezhandi, Banisharif, Saifullah, Jannesari; arXiv 2601.08166, Jan 2026, v2 Feb 2026)
Confirmed: double-dueling DQN agents, 13 LLM-extracted semantic features (plus 17 syntactic features), Profiler Agent (cores + frequency) and Temperature Agent, OpenMP source code as input, Jetson TX2/Orin NX/RubikPi/Core i7, no mention of iowait/I-O. It also states that utilization-based DVFS does not distinguish active from stall time, which matches your motivation.
Additions: (a) it compares against **ondemand, conservative and schedutil**, plus zTT and GearDVFS, so it is a ready-made list of what a credible baseline set looks like; (b) the headline 7.09× energy gain is framed against ondemand in the abstract but against the "Precise" scheduler in Section 5.4, so avoid quoting it without checking; (c) decision latency is 358 ms. I could not find a code-availability statement in the text I saw (the text was truncated near the end), so "needs source code" is true of its *input*, but whether *their* code is public is unknown. The notes' claims about GPU training and per-query LLM API calls are unverified.
The same group also has **HiDVFS** (arXiv 2601.06425, Jan 2026, rev. Jul 2026): three-agent hierarchical DVFS on Jetson TX2, 32.9% energy reduction vs a port of GearDVFS.

### Paper 2: Memory-Aware DVFS Governing Policy (IEEE RTCSA 2023)
Confirmed: title, venue (29th IEEE RTCSA, 2023), pages 57–66. A Semantic Scholar URL slug suggests "Shin, Kim" among the authors. I could **not** open the abstract or PDF, so the author list "Shin, Kim, Hong", the CPI/regression method and the PMU requirement are unverified. A preprint is hosted at `redwood.snu.ac.kr/wordpress/wp-content/uploads/2023/05/23-04-28-mSchedutil.pdf`; open it yourself and read the method and platform sections before citing specifics.
Related fact you can use: memory-aware DVFS is **not new in 2023**. Green Governors (Spiliopoulos, Kaxiras, Keramidas, Uppsala/Patras, IGCC 2011) already used stall/IPC counters to slow down memory-bound but CPU-busy programs, reporting EDP gains up to 56% on memory-bound mixes against ondemand, with governor overhead "well below 1%" at a 50 ms interval.

### Paper 3: Mittal, "Power Management Techniques for Data Centers: A Survey" (arXiv 1404.6681, 2014)
Confirmed: Section IV.A, Eq. (1), **P = P_static + C·F·V²**, with the variable definitions you wrote. The survey gives no source for the equation. Two cautions: (a) your power model is a *fitted cubic*; the survey supports the general form, not the cubic. Say explicitly that the cubic is the usual simplification when V scales roughly with F, and that you fitted it; (b) the survey is from 2014. The claims about Sharma et al. / Hsu & Feng and about feedback governors bounding utilization are unverified.

### Paper 5: zTT (Kim, Bin, Ha, Chong; ACM MobiSys 2021)
Confirmed: authors, Best Paper Award, joint CPU+GPU frequency control by deep RL, Pixel 3a and Jetson TX2, 23.9% lower average power in a high-temperature rendering test. "Model-free" is a fair description of its DQN approach but I did not see the word on the pages I opened. Useful newer data point: MetaDVFS (below) reports zTT often performing *worse than schedutil* (0.52–0.98 of baseline perf-per-watt) when training data was limited.

### Paper 6: Zhou & Lin (arXiv 2309.03779, Sep 2023; journal version in Journal of Systems Architecture)
Confirmed: shows Linux built-in management struggles on three workload patterns, uses temporal-encoding DRL with a single performance counter, Jetson Nano, compared against **ondemand** (3–11% more energy saved on MiBench, 5–14% on two custom apps), and releases an in-kernel quantized NN engine ("tinyagent"). The follow-up (Li, Zhou, Wang, Lin, arXiv 2409.19434) extends it to multi-task systems, 3–10% power saving vs built-in governors. A 2022 thesis proposal by Zhou describes the "profile built-in governors first" step as low-cost kernel-level profiling. Your "profile first" methodology point is fair.

---

## B. Related and recent work (verified from abstracts/pages unless marked)

**RL and learned DVFS (the heavy end)**
- zTT, MobiSys 2021 (above).
- GearDVFS, Lin, Wang, Li, Pu, ACM MobiCom 2023: workload-aware DVFS robust to concurrent tasks on mobile devices; 23.9–26.9% energy-efficiency gains over prior methods (per the project page).
- MetaDVFS, Yan et al., arXiv 2509.22707 (2025): meta-learning across devices/apps on five Pixel phones; baselines schedutil, zTT, GearDVFS, Orthrus; up to 17% perf-per-watt gain. Its app metadata includes a CPU/GPU/**IO sensitivity** attribute, so I/O sensitivity is recognised, but as metadata, not as a runtime class.
- Zhou & Lin 2023 and Li et al. 2024/25 (above); ZeroDVFS and HiDVFS 2026 (above); FlowRL (Pivezhandi & Saifullah, arXiv 2409.14178), few-shot RL for DVFS data scarcity.
- Takeaway: the 2023–2026 literature is dominated by embedded boards and mobile SoCs with RL, training cost, and fixed hardware. I found no recent paper that targets a general-purpose x86 laptop with a transparent, rule-based, user-space policy.

**Counter-based and analytical DVFS (the lightweight end)**
- Green Governors (2011), see above. Also the classic "DVFS based on workload decomposition" line (Pedram group; title seen at `mpedram.com/Papers/dvfs-slped04.pdf`, **UNVERIFIED**) and Brendan Gregg's "CPU Utilization is Wrong" (2017), arguing %CPU hides memory stalls and IPC is the better signal.
- All of these rely on PMU/IPC. Your `/proc/stat`-only signal set is a real, defensible constraint (VMs, no root PMU access), but it is also exactly what these works argue is *insufficient* for memory-bound phases.

**What Linux already does (this is where reviewers will push)**
- **schedutil** picks frequency from PELT utilization: `f = 1.25 × util × f_max`, frequency- and capacity-invariant, with UTIL_EST for periodic tasks, uclamp, and a rate limit. Kernel docs call the linear freq-to-capacity assumption "flawed but the best workable approximation."
- **schedutil already has an I/O-wait mechanism**, and it points the *opposite way* to yours: when a task wakes after I/O, utilization is boosted (doubling on repeated I/O wakeups, decaying otherwise) so I/O completes sooner. Commit text says it is conservative for sporadic I/O.
- **ondemand** historically treated I/O wait as idle, which caused a "really bad" slow-down during disk I/O; in 2010 Arjan van de Ven argued for backporting an I/O-aware change because finishing sooner lets the CPU "be idle longer later" ("you're measuring power not energy").
- **amd-pstate** (your Ryzen 7 7840HS): in *active* mode firmware/CPPC chooses frequency from an EPP hint; passive/guided modes let the OS give targets or min/max bounds. The kernel docs say it works with schedutil and ondemand.
- Piersma et al. (Columbia, "Reverse Engineering DVFS Mechanisms", ~2025, Intel) show hardware-managed P-states can ignore OS requests inside a range. The paper does not test AMD, but it illustrates the risk that an OS-level frequency request is only a hint.
- A Nov 2025 LKML thread reports a performance regression in stable 6.6 from the schedutil "performance estimation" rework (Chromebook, uclamp). Takeaway: schedutil keeps changing, so **record the exact kernel version** if you compare against it.
- **auto-cpufreq** (GPL-3.0, Python, systemd daemon) is the closest *architectural* sibling: a user-space daemon that switches governor/turbo/EPP profiles from CPU usage, temperature, load and battery state. Its README lists no I/O-wait signal and gives no overhead numbers.
- sched_ext (BPF schedulers): "energy-aware abstractions" are listed as a *2026 plan* by its maintainers (Phoronix, Dec 2025), not a shipped feature.

**Adjacent, not directly comparable**: mobile-LLM DVFS (FUSE, arXiv 2507.02135; CORE, MLSys 2026), HPC memory-aware DVFS (MEMPOWER, arXiv 2608.20734, Aug 2026), GPU/NPU DVFS. Cite only if you need breadth.

**Leads I could not verify (title seen only)**: "Is the powersave governor really saving power?" (EPFL Infoscience), "Dim Silicon and the Case for Improved DVFS Policies" (arXiv 2005.01498), "Learning-based Phase-aware Multi-core CPU Workload Forecasting" (ACM 10.1145/3564929). The powersave one is worth reading for your simulation's powersave baseline.

---

## C. Where the project stands: novelty

**Straight assessment.** Each item on your positioning list is individually not new: counter-based classification (Green Governors, 2011), utilization-only governors reading `/proc`-class signals (ondemand, conservative, auto-cpufreq), rule-based dominant-resource classification (Parikh et al. 2026), hysteresis (conservative governor, rate limits), I/O awareness (schedutil iowait boost, ondemand `io_is_busy`). A claim of "novel governor" will not hold. What *can* hold is narrower and more honest:

1. **A direction-of-effect question the kernel answers one way.** Linux boosts frequency on I/O wake-ups; your policy *lowers* it for I/O-bound phases. Whether that saves energy, or just lengthens I/O-dependent work (the 2010 ondemand experience), is an empirical question I found no recent clean answer to. A controlled study of it, on real bounded workloads, is a legitimate contribution. This is the most defensible differentiator, and also the biggest risk, so test it early.
2. **Transparent, hysteresis-controlled class-based policy with a K sweep.** Studying fixed K versus adaptive K versus fast-up/slow-down on energy-delay trade-offs is a cleanly scoped, answerable question, and none of the RL papers explain their decisions this way.
3. **Deployability under constraints**: no PMU, no source, no training, runs in a VM or locked-down machine. Real, but state it as a constraint, not a result.
4. **Methodology**: closed-loop evaluation under emulated frequency against a faithful schedutil model. Most student prototypes stop at simulation.

Suggested framing for the report: *"We evaluate whether an interpretable, I/O-aware, hysteresis-gated user-space policy can match schedutil's performance at lower estimated energy on general-purpose workloads, and under what conditions I/O-aware downscaling helps or hurts."* This survives a hostile reviewer because it makes no claim of beating RL systems.

**Honest threats to validity** to put in the report: power is modelled, not measured; frequency is simulated; the baselines are Python approximations (so "beats schedutil" cannot be claimed until schedutil's formula, rate limit and iowait boost are reproduced); the 3.8–5.1 GHz ladder starts at the 7840HS base clock, so it cannot represent the lower P-states where most real savings occur; and the VM cannot show hardware behaviour.

---

## D. Does the governor's own overhead cancel its savings?

**Frame it as a break-even.** The governor pays off if `ΔE_saved > E_governor`, over the same time window. Report both sides as numbers.

*Costs to measure:* (1) CPU time per tick (`time.process_time()` around the loop body, plus `utime+stime` from `/proc/<pid>/stat`); (2) wake-ups per second (the timer wake itself prevents deep idle; use `perf stat -e context-switches,cpu-migrations` on the governor PID or `/proc/<pid>/status` counters); (3) frequency-transition cost (count transitions; hysteresis K directly reduces this); (4) perturbation: the governor's own CPU use shows up in the `/proc/stat` it reads, so exclude or subtract its PID effect.
*Method:* same workload with the governor on and off, many repeats, report median and spread; sweep the sampling interval (e.g., 0.1, 0.5, 1, 2, 5 s) and plot overhead against reaction delay; convert overhead CPU time to energy using your own power model (clearly labelled as modelled).
*Prior art to compare against:* Green Governors report overhead "well below 1%" at 50 ms intervals with counter reads; ZeroDVFS reports 358 ms decision latency for its LLM/RL pipeline; Zhou & Lin built an in-kernel quantized NN specifically to keep overhead low. A Python loop reading `/proc/stat` once a second is very likely tiny by comparison, but treat that as a hypothesis until measured, including Python interpreter wake-up cost.
*Real measurement:* a VM cannot give energy. On the actual Ryzen laptop, booted natively (live USB is enough), use the hardware energy counters if the kernel exposes them, or a USB/wall power meter, and report idle-baseline with and without the daemon running.

---

## E. How it would work in a real deployment

- **Actuation on the 7840HS.** With amd-pstate in *active* mode, firmware decides frequency from an EPP hint, so a classic "set exact frequency" governor is not how the hardware is driven. Realistic knobs: `energy_performance_preference` per policy, `scaling_max_freq`/`scaling_min_freq` bounds (or guided mode min/max), and the `powersave`/`performance` governor choice. Map your four classes to EPP/bounds rather than to exact GHz. Confirm which amd-pstate mode the target machine is actually in.
- **Packaging.** A root systemd service like auto-cpufreq, reading `/proc/stat` (and optionally PSI under `/proc/pressure/`, **my suggestion, not verified against your design**) and writing sysfs. It must coexist with or replace power-profiles-daemon/TLP, otherwise two controllers will fight.
- **Safety.** Fail-safe to the stock governor on crash or exception, clamp changes to the allowed range, rate-limit writes, log every decision (your interpretability advantage), and cap how long the class can force a low frequency.
- **Longer-term options.** An in-kernel governor (C, via the cpufreq governor API) removes the user-space wake-up cost but is outside course scope; BPF/sched_ext would be the modern route but its energy abstractions are still only planned.
- **Limit to state.** Hardware may override or ignore requests (Piersma et al.), and aggregate `/proc/stat` hides per-core differences, which is why per-core features are a sensible next step.

---

## F. Changes to your plan

1. **Fix paper 4 in the notes and report** (Section A). Remove the 97/98% benchmark and the "decision-tree classification" framing.
2. **Reframe the decision-tree item.** With no real precedent for an ML classifier, position it as an *ablation*: rules versus a small tree on the same features, with ground-truth labels from synthetic workloads you generate (e.g., stress-ng CPU / disk / mixed), not labels produced by your own rules (that would be circular). Report interpretability and overhead, not just accuracy.
3. **Make the schedutil baseline the priority.** Implement the documented formula (`1.25 × util × f_max`, rate limit, iowait boost) and name the kernel version you imitate. Also add a baseline that implements the kernel's *boost-on-iowait* direction against your *lower-on-iowait* direction; that single comparison is your differentiator.
4. **Add an energy-delay metric**, not energy alone, given the 2010 "power vs energy" point and the race-to-idle risk of slowing I/O-bound work.
5. **Order of work:** (a) closed-loop duty-cycle emulation with bounded workloads, (b) schedutil-style baseline, (c) overhead measurement, (d) fixed-K versus adaptive-K and fast-up/slow-down, (e) per-core features, (f) tree. Overhead measurement is cheap and answers the professor's question 3 directly, so don't leave it last.
6. **Memory-bound class.** Keep it as stated future work, but cite Green Governors and the IPC argument, not only the 2023 paper, so the limitation reads as informed.

---

## Source list

- ZeroDVFS: https://arxiv.org/abs/2601.08166
- HiDVFS: https://arxiv.org/abs/2601.06425
- FlowRL: https://arxiv.org/abs/2409.14178
- MetaDVFS: https://arxiv.org/abs/2509.22707
- GearDVFS: https://github.com/geardvfs/GearDVFS
- Zhou & Lin: https://arxiv.org/abs/2309.03779 ; Li et al.: https://arxiv.org/abs/2409.19434 ; Zhou thesis proposal: https://www.stfx.ca/media/28326/download
- zTT: https://ee.kaist.ac.kr/ai-in-computer/ztt-learning-based-dvfs-with-zero-thermal-throttling-for-mobile-devices-acm-mobisys-2021-best-paper-award/
- Mittal survey: https://arxiv.org/abs/1404.6681
- Parikh et al.: https://arxiv.org/abs/2601.11935
- Memory-Aware DVFS (record): https://karla.hds.hebis.de/EdsRecord/edseee%252Cedseee.10296351 ; preprint: http://redwood.snu.ac.kr/wordpress/wp-content/uploads/2023/05/23-04-28-mSchedutil.pdf
- Green Governors: https://pages.cs.wisc.edu/~kaxiras/papers/igcc11_green_governors.pdf
- Piersma et al.: https://takhandipu.github.io/papers/piersma-reverse-2025.pdf
- Gregg, CPU Utilization is Wrong: https://www.brendangregg.com/blog/2017-05-09/cpu-utilization-is-wrong.html
- Kernel cpufreq admin guide: https://docs.kernel.org/admin-guide/pm/cpufreq.html ; amd-pstate: https://docs.kernel.org/admin-guide/pm/amd-pstate.html ; schedutil: https://docs.kernel.org/scheduler/schedutil.html
- schedutil iowait boost patch: https://lkml.iu.edu/hypermail/linux/kernel/1804.1/02723.html
- ondemand disk-IO thread (2010): https://lkml.iu.edu/hypermail/linux/kernel/1004.2/00692.html
- schedutil regression thread (Nov 2025): https://lkml.iu.edu/2511.3/01024.html
- auto-cpufreq: https://github.com/AdnanHodzic/auto-cpufreq
- sched_ext plans: https://www.phoronix.com/news/sched-ext-future-plans-2026
- Mobile LLM DVFS: https://arxiv.org/abs/2507.02135 ; MEMPOWER: https://arxiv.org/abs/2608.20734
