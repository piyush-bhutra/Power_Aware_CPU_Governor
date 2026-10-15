# CPU timing diagnostic implementation plan

Spec: shared prompts/CPU_Timing_Diagnostics.txt. Work in the existing clean
development checkout as explicitly required. User requests autonomous completion;
no approval pauses, real workload, collector invocation or configuration changes.

1. Inspect failed evidence and source; separate facts from missing instrumentation.
2. Reproduce missing readiness and failure evidence using harmless child processes
   and simulated time. Observe failing tests before implementation.
3. Add an opt-in monitor ready/start handshake with a two-second startup limit
   inside the existing total deadline. Start worker only after readiness. Retain
   seven-second worker, eleven-second supervisor and fifteen-second outer budgets.
   Capture supervisor lifecycle/exit/cleanup diagnostics and distinguish deadline
   phases. Validate any preserved CSV independently of process success.
4. Test handshake, startup/sampling/workload deadlines, interruption/cleanup and
   independent validation. Run bounded full suite and static checks.
5. Review accumulated main diff by milestone, update state/log/workflow/review docs,
   commit and push development only. Export evidence/report, archive prior handoffs,
   atomically update and verify shared handoffs.

Review focus: no worker before readiness; no increased total runtime; absent or
   failed readiness aborts safely; partial CSV is retained but never promoted to a
   successful dataset; process cleanup and original failure remain observable.

Progress: evidence inspected; source has worker-first startup, no readiness, a
single deadline and success-only exit evidence/validation. Original monitor cause
cannot be recovered from an empty log and header alone. Fetch shows no divergence.

Completion ledger: implementation and mock regression verification complete. Final
suite 104 passed in 16.57 s; independent prior 103-test suite passed in 8.19 s.
Ruling: use existing development checkout and inline execution because the prompt
requires development only and user explicitly requests no approval pauses. Preserve
all original evidence. Final review resolved diagnostic-storage cleanup regression.
No live collector/sampler or stress executed. Documentation complete; checkpoint and
shared export are the remaining operational steps, recorded in shared handoff.
