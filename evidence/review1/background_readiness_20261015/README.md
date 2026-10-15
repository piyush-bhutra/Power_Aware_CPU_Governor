# Review 1: background monitor readiness evidence

Original run: `launcher-20261015T144107Z-ulqlq_gi`, October 15, 2026,
14:41:07–14:41:20 UTC. Producing source commit:
`18b87efa6ffdcc4e7f4ed58936c824876a42d3fc` (recorded clean working tree).
This archive was created after the experiment; the milestone archive commit did
not produce these observations.

All 15 original files were copied unchanged from
`/media/sf_OS_Project_Shared/results/safe_background_launcher-20261015T144107Z-ulqlq_gi/`.
The originals remain untouched. `PROVENANCE.json` lists original paths, environment,
command, safety limits, source hashes, validation and scientific limitations.
`SHA256SUMS` covers those originals and provenance; verify from this directory:

```bash
sha256sum -c SHA256SUMS
```

The raw `collection/20261015T144114Z-la72apwi/trace.csv` includes previous/current
kernel counters and derived signals. `validated_trace.csv` is the identical
validated copy. The collection directory retains statistics, source metadata,
manifest, lifecycle, monitor log, recorded process identity, empty worker log and
readiness/start markers. Launcher metadata/logs and the original report retain
execution, exit and cleanup evidence. No original evidence hash manifest existed;
these new hashes prove copy integrity, not independent authentication of the run.

Verified: exactly five valid, consecutive Linux aggregate observations; monitor
ready before sampling release; launcher/collector/monitor exits 0; cleanup reported
complete; zero CPU, memory or I/O stress workers. Mean CPU utilization 0.3231%;
iowait 0%; elapsed intervals 1.0067–1.8549 s (mean 1.2422 s) despite requested 1 s.
Recomputed aggregate accounting was 391.0–396.8 jiffies/s, plausible for four vCPUs
at 100 Hz. Original metadata omits CLK_TCK; the audit's current getconf reads 100.

This proves a successful background monitoring and readiness path in this VM.
It does not prove loaded timing stability, stress-test success, idle ground truth,
classifier accuracy, physical CPU frequency control, measured energy savings or
preserved workload completion time. Recorded classifier counts (3 idle, 2 mixed)
are provisional rule outputs, not labelled validation. There are no frequency
measurements in the CSV. Synthetic simulated-frequency/modelled-energy charts
belong to a separate evidence category; see `docs/REVIEW1_STATUS.md`.

All originals were small, relevant text artifacts and were retained, including
empty logs and handshake markers for completeness (33,913 bytes total). Inspection
found no credentials or email addresses. Kernel/CPU descriptions, local paths,
local hostname and historical process IDs are intentional provenance metadata.

The two original CSVs use CRLF. Exact-path .gitattributes rules disable text
normalization and recognize CR as part of the line ending for whitespace checks.
No original bytes were changed to satisfy Git checks.
