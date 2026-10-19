# Review II checklist

Last updated October 19, 2026 (commit f47e288 plus documentation). Deliverables are
taken from the lab guideline list supplied by the team and from `docs/PRD.md`
section 15; the guideline PDF itself is not stored in this repository.

Status: **done** = complete and in the repo (or recorded as delivered); **partial** =
started, with named gaps; **missing** = not in the repo.

## Course deliverables

| Deliverable | Status | Where | Notes |
|---|---|---|---|
| Project proposal report | done (delivered outside the repo) | not in repo | PRD section 15 records `Project_Proposal_Report.docx` as delivered; the file is not committed |
| Design and progress report (Review I) | partial (not in repo) | not in repo | Review I was held (October 2026). The report file and marks are not stored here. Supporting material: `docs/REVIEW1_STATUS.md`, `docs/REVIEW1_PLAN.md`, `evidence/review1/` |
| Final project report | missing | — | Template `OS_Project_Report.docx` (PRD section 16: Times New Roman, 1.5 spacing, ≥ 15 MLA references) is not in the repo. Inputs ready: [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md), [TEST_PLAN_AND_RESULTS.md](TEST_PLAN_AND_RESULTS.md), `docs/power_model.md`, `docs/thresholds.md`, evidence folders |
| Final presentation, 15-20 slides | missing | — | Can be built from the problem statement, test plan, sensitivity plots and dashboard screenshots |
| Source code | done | repository root | Monitor, classifier, policy, setter, power model, benchmarks, Governorlab, Daybreak, session store |
| Test cases and results | partial | [TEST_PLAN_AND_RESULTS.md](TEST_PLAN_AND_RESULTS.md), `tests/` | Windows 241 + 6 passed (4eb1865); Ubuntu 331 tests on 943dba1 (9 launcher timeouts under VM load, all 33 launcher tests passing on a clean re-run); disconnect/shutdown and attempt-cap checks pending |
| User manual | done | [USER_MANUAL.md](USER_MANUAL.md) | Installation, commands, dashboard, sessions, troubleshooting, limitations |

## Review II items

| Item | Status | Evidence | Gaps |
|---|---|---|---|
| Complete implementation | partial | Monitoring, classification, hysteretic policy, simulated actuation, modelled power, five-policy comparison, live collection (5-30 samples, tolerant/strict), shared sessions, terminal and dashboard | Frequency is simulated (VM has no cpufreq); no ML classifier (planned in PRD, not built); only a schedutil-style approximation, not the kernel governor |
| Testing | partial | [TEST_PLAN_AND_RESULTS.md](TEST_PLAN_AND_RESULTS.md) | Classifier accuracy on labelled workloads pending; real dashboard disconnect and server-shutdown checks pending; launcher tests are timing-sensitive on a loaded VM |
| Performance evaluation | partial | `evidence/review1/synthetic_policy_comparison_20261015/` (modelled energy), `evidence/phase1b_sensitivity/` (K and interval study), [`evidence/phase2a_closed_loop/`](../evidence/phase2a_closed_loop/README.md) (closed-loop modelled energy, completion time and EDP for 11 policies; our policy wins none of these under pure 1/f), full overhead run on the VM (24/24 runs ok; net 0.55-0.62 ms CPU per tick, 0.0117-0.1198 % of one core derived; [test plan](TEST_PLAN_AND_RESULTS.md)) | Overhead run archived in [`evidence/phase1b_overhead/`](../evidence/phase1b_overhead/README.md); completion time and EDP are modelled only; no measured energy, no real-hardware run |
| Error handling | done | Input validation (policy, classifier, counters), tolerant collection with disclosure, attempt cap, deadlines and watchdog, archive and session integrity checks, plain-words dashboard failures; tests ERR-01 to ERR-07 | Real attempt-cap case not yet observed on the VM |
| Demo of all features | partial | Governorlab synthetic, recorded, live (tolerant and strict, verified on the VM), session list/replay; Daybreak four views and saved-session replay | Dashboard collection verified at 5, 10 and 20 samples with Cancel on the VM; demo still needs a quiet VM (terminal collection plus dashboard replay is the reliable route) |
| Viva preparation | done | [VIVA_QA.md](VIVA_QA.md), [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md) | Rehearsal by the team |

## Open items before Review II (in suggested order)

1. Check dashboard disconnect and server-shutdown handling with a real child on the VM,
   and observe a real attempt-cap failure if one occurs.
2. Re-run the Ubuntu full suite on a quiet VM at the latest commit.
3. Write the final report in the official template and build the 15-20 slide deck.
4. Optional: measured energy on native hardware, which is the only way to test the
   closed-loop model's conclusions.
