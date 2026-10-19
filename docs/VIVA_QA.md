# Viva questions and honest answers

Last updated October 19, 2026. Numbers come from files in this repository or from
recorded runs listed in [TEST_PLAN_AND_RESULTS.md](TEST_PLAN_AND_RESULTS.md).
Rule of thumb for every answer: counters are measured; frequencies are simulated;
energy and savings are modelled.

## The idea

**1. What does the project do, in one sentence?**
It reads Linux `/proc/stat` counters, classifies each second of activity as CPU-bound,
I/O-bound, idle or mixed with transparent rules, and picks a target frequency only
after the same class persists for K=3 samples; the frequency is simulated.

**2. What problem are you solving?**
Utilization alone does not say whether the CPU is busy computing or waiting on I/O,
and reacting to every spike causes frequency thrashing. We test whether workload
classes plus hysteresis give a more stable, explainable policy.

**3. What is new here?**
Not the algorithm. Counter-based classification, rule-based workload labelling,
hysteresis and I/O-aware frequency policies all exist (see the positioning section of
[PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md)). The defensible part is a narrow
evaluation question: Linux's schedutil *raises* frequency after I/O waits, while our
policy *lowers* it for I/O-bound phases; when does that help or hurt energy and delay?
We have the instrumented prototype and the tooling to study it; the answer itself is
pending real closed-loop measurements.

**4. What does Linux already do?**
schedutil sets frequency from the scheduler's per-entity utilization signal (documented
as about 1.25 × util × f_max), with an I/O-wait boost and a rate limit. ondemand and
conservative use utilization thresholds. On the Ryzen 7 7840HS, the amd-pstate driver
in active mode lets firmware choose frequency from an energy-performance hint.

**5. Why not just use schedutil?**
For real use, schedutil is the sensible default. This project is an OS-lab study of
an alternative, interpretable policy and its trade-offs, not a replacement claim. We
have not implemented a schedutil baseline yet, so we make no comparison claim
against it.

## Why simulated

**6. Why is frequency simulated?**
The development machine is a VirtualBox VM. Its guest exposes no cpufreq interface on
any core (`docs/vm_feasibility.md`), so frequency cannot be set or read. The policy
logic is real; only the final actuation is simulated.

**7. Then is anything real?**
Yes. On the Ubuntu VM the `/proc/stat` counters, the measured elapsed intervals, the
derived rates, the classification and the policy decisions are real executions of the
code on real kernel data. Only frequency and power are simulated or modelled.

**8. Where do the power numbers come from?**
A model, P = 21.6 + 32.4·(f/5.1 GHz)³·util/100 W, fitted at two points to AMD's
published 35-54 W TDP range for the 7840HS (`docs/power_model.md`). It is not
calibrated against measurements. Every chart and table labels it modelled.

**9. So does your governor save energy?**
We cannot claim that. In the archived 34-tick synthetic comparison (modelled energy),
ours is 1336.622 J against performance 1482.886 J, ondemand 1442.784 J, conservative
1365.647 J and powersave 1044.012 J. Powersave is lowest because the open-loop model
never makes slower work take longer. Real savings need real hardware, real workloads
and measured energy.

## Classifier and policy

**10. Is the classifier machine learning?**
No. It is four ordered rules (`classifier/rules.py`): I/O-bound if I/O wait ≥ 20 % or
(blocked processes > 0 and context switches ≥ 2000/s); CPU-bound if utilization ≥ 70 %
with nothing blocked; idle if utilization < 10 % and at most one runnable process;
otherwise mixed. The original plan's decision tree has not been built.

**11. Why these thresholds?**
They are provisional engineering guesses, written down in `docs/thresholds.md`, not
tuned on labelled data. Tuning needs bounded, labelled workloads; that is pending.
Classifier accuracy on real workloads is therefore unknown.

**12. Why put the I/O rule first?**
A short I/O burst can show high utilization (data is copied after it arrives).
Checking I/O wait and blocked processes first stops such a burst from being called
CPU-bound. The synthetic `io_burst` profile exists to test exactly that.

**13. Why K=3?**
It is a balance between stability and lag. Our sensitivity study
(`evidence/phase1b_sensitivity/`, synthetic, simulated) shows the lag after a phase
change is exactly K - 1 ticks, bursts shorter than K never change frequency, K ≥ 3
removes all transitions in a 2-tick flapping scenario, and at K ≥ 7 the archived
scenario stops reaching some targets before the phase ends.

**14. How do the class targets map to frequency?**
Fractions of the ladder: idle 0.0, I/O 0.3, mixed 0.6, CPU 1.0, giving 3.8, 4.23, 4.67
and 5.1 GHz on the four-step model ladder. These fractions are hand-chosen.

## Measurement quality

**15. How do you know the counters are right?**
Rates use deltas and the measured monotonic interval; guest time is not counted twice;
counter resets reject the interval; a decreasing I/O-wait counter is clamped and
flagged; every saved session is revalidated from its raw counters. All of these have
tests (MON-01 to MON-09).

**16. What happens when the VM's timing goes wrong?**
The VM's timer overshoots by about 10 %. Each interval must last 0.5-2 s and show a
plausible CPU-accounting rate. In the default tolerant mode a failing interval is
discarded, recorded and never classified, and collection continues up to N +
max(3, ceil(N/2)) attempts. The session is marked degraded and shows a banner. On
the VM one run discarded one 2.32 s interval and kept 5 of 5 samples. `--strict`
aborts instead.

**17. Doesn't discarding intervals bias the data?**
It can: kept samples in a degraded session may be non-adjacent in time, so K=3
persistence can span a gap. That is why every discard is disclosed with its attempt
number, reason, elapsed time and ratio, and why strict mode still exists.

## Overhead and deployment

**18. What does the governor itself cost?**
So far only smoke runs on the VM: about 0.3 to 0.8 ms of CPU per tick (single 5 s
runs, quantized). At a 1 s interval that would be under 0.1 % of one core, but this is
a rough derivation from smoke runs, not a result. The full measurement (four
intervals × 60 s × 3 repetitions against a sleep-only control) is pending.

**19. Could that overhead cancel the savings?**
It is a break-even: savings must exceed the governor's own energy. We can measure the
cost side now; the savings side needs measured energy on real hardware, which we do
not have. So the honest answer is: not yet known.

**20. What would a real deployment need?**
A native Linux machine with cpufreq; on the 7840HS, mapping classes to amd-pstate's
energy-performance preference or min/max bounds rather than exact frequencies; a root
systemd service that coexists with or replaces power-profiles-daemon/TLP; fail-safe
fallback to the stock governor; rate-limited, logged writes; and measured energy
(hardware counters or a power meter). None of that is done.

**21. Why user space and Python?**
Safety, transparency and course scope. Reading `/proc/stat` needs no privileges and
the logic is easy to inspect. An in-kernel governor would remove user-space wake-ups
but is outside this project.

## Evaluation and evidence

**22. How did you test it?**
Unit and integration tests by feature (monitoring, classifier, policy, simulated
actuation, sessions, tolerant collection, dashboard, error handling, evidence,
benchmarks). Windows portable suite: 236 passed + 6 on commit f47e288. Ubuntu VM full
suite: 326 passed on commit 8b7280e; a run on f47e288 is pending.

**23. Are your baselines the real kernel governors?**
No. performance, powersave, ondemand and conservative are Python approximations driven
by the same inputs. There is no schedutil baseline yet.

**24. How do you prevent fake or edited results?**
Archives have SHA-256 manifests and provenance files; replays rebuild every decision
from the backend and fail on any mismatch; saved sessions carry hash manifests and are
revalidated on load. Missing data shows an error, never a substitute.

**25. What are the main limitations?**
Simulated frequency, modelled energy, provisional thresholds, a ladder that omits low
P-states, Python baselines without schedutil, aggregate-only counters (no per-core,
per-process or IPC/stall signals), open-loop replay with no completion-time effect, a
VM with about 10 % timer overshoot, and an overhead result that is still pending.

**26. What would you do next?**
Run the full overhead plan; add a schedutil-style baseline including its I/O-wait
boost; build closed-loop bounded workloads so lower frequency stretches work; add an
energy-delay metric; label bounded stress workloads to tune thresholds; then measure
on native hardware.
