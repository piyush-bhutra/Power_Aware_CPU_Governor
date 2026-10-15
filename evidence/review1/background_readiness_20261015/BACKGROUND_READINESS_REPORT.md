# Background readiness report

Date: 2026-10-15T14:41:07.976180+00:00

Validation: passed
Overall success: True; exit code: 0
Commit: 18b87efa6ffdcc4e7f4ed58936c824876a42d3fc; dirty state: False
Collector started: True; worker startup recorded: False
Cleanup: verified no recorded running processes

Local evidence: /home/vboxuser/Power_Aware_CPU_Governor/data/background_readiness/launcher-20261015T144107Z-ulqlq_gi
Shared evidence: results/safe_background_launcher-20261015T144107Z-ulqlq_gi/

Configuration, resources before/after, manifest, statistics, class counts and errors:

```json
{
  "start_utc": "2026-10-15T14:41:07.976180+00:00",
  "workload_started": false,
  "collector_started": true,
  "validation": "passed",
  "cleanup": "verified no recorded running processes",
  "errors": [],
  "config": {
    "profile": "background",
    "cpu_workers": 0,
    "method": null,
    "sampling_intervals": 5,
    "interval_s": 1,
    "worker_timeout_s": null,
    "supervisor_deadline_s": 11,
    "outer_timeout_s": 15,
    "vm_workers": 0,
    "io_workers": 0,
    "frequency_control": "none"
  },
  "statistics": {
    "rows": 5,
    "workload_label": "uncontrolled_background",
    "observation_source": "linux_proc_stat",
    "elapsed_s": {
      "min": 1.0067027810000582,
      "mean": 1.2421605750001619,
      "max": 1.8549103749992355
    },
    "util_pct": {
      "min": 0.0,
      "mean": 0.3231045009245093,
      "max": 0.8676789587852495
    },
    "iowait_pct": {
      "min": 0.0,
      "mean": 0.0,
      "max": 0.0
    },
    "ctxt_per_s": {
      "min": 246.37308958940312,
      "mean": 389.20042390754,
      "max": 638.1285923027353
    },
    "iowait_decrease_intervals": 0
  },
  "swap_preflight": {
    "requested_window_s": 0.25,
    "window_count": 3,
    "max_total_pages": 32,
    "max_active_windows": 1,
    "page_size_bytes": 4096,
    "min_available_kib": 524288,
    "max_swap_growth_kib": 131072,
    "samples": [
      {
        "pswpin": 32832,
        "pswpout": 130658,
        "elapsed_s": 0,
        "resources": {
          "mem_available_kib": 2323364,
          "swap_used_kib": 423728
        }
      },
      {
        "pswpin": 32832,
        "pswpout": 130658,
        "elapsed_s": 0.7921744300001592,
        "resources": {
          "mem_available_kib": 2323308,
          "swap_used_kib": 423728
        }
      },
      {
        "pswpin": 32832,
        "pswpout": 130658,
        "elapsed_s": 1.2980304510001588,
        "resources": {
          "mem_available_kib": 2323308,
          "swap_used_kib": 423728
        }
      },
      {
        "pswpin": 32832,
        "pswpout": 130658,
        "elapsed_s": 1.708859680000387,
        "resources": {
          "mem_available_kib": 2323308,
          "swap_used_kib": 423728
        }
      }
    ],
    "windows": [
      {
        "elapsed_s": 0.7921744300001592,
        "delta_pswpin_pages": 0,
        "delta_pswpout_pages": 0,
        "swap_kib_per_s": 0.0
      },
      {
        "elapsed_s": 0.5058560209999996,
        "delta_pswpin_pages": 0,
        "delta_pswpout_pages": 0,
        "swap_kib_per_s": 0.0
      },
      {
        "elapsed_s": 0.4108292290002282,
        "delta_pswpin_pages": 0,
        "delta_pswpout_pages": 0,
        "swap_kib_per_s": 0.0
      }
    ],
    "passed": true,
    "elapsed_s": 1.708859680000387,
    "total_pages": 0,
    "total_kib": 0.0,
    "active_windows": 0
  },
  "resources_before": {
    "mem_available_kib": 2323308,
    "swap_used_kib": 423728
  },
  "kernel": "Linux osproject 7.0.0-31-generic #31-Ubuntu SMP PREEMPT_DYNAMIC Sat Aug  1 04:26:38 UTC 2026 x86_64 GNU/Linux",
  "cpu": "Architecture:                            x86_64\nCPU op-mode(s):                          32-bit, 64-bit\nAddress sizes:                           48 bits physical, 48 bits virtual\nByte Order:                              Little Endian\nCPU(s):                                  4\nOn-line CPU(s) list:                     0-3\nVendor ID:                               AuthenticAMD\nModel name:                              AMD Ryzen 7 7840HS w/ Radeon 780M Graphics\nCPU family:                              25\nModel:                                   116\nThread(s) per core:                      1\nCore(s) per socket:                      4\nSocket(s):                               1\nStepping:                                1\nBogoMIPS:                                7585.87\nFlags:                                   fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 ht syscall nx mmxext fxsr_opt rdtscp lm constant_tsc rep_good nopl xtopology nonstop_tsc cpuid extd_apicid tsc_known_freq pni pclmulqdq ssse3 fma cx16 sse4_1 sse4_2 movbe popcnt aes xsave avx f16c rdrand hypervisor lahf_lm cmp_legacy cr8_legacy abm sse4a misalignsse 3dnowprefetch vmmcall fsgsbase bmi1 avx2 bmi2 invpcid rdseed adx clflushopt sha_ni arat\nHypervisor vendor:                       KVM\nVirtualization type:                     full\nNUMA node(s):                            1\nNUMA node0 CPU(s):                       0-3\nVulnerability Gather data sampling:      Not affected\nVulnerability Ghostwrite:                Not affected\nVulnerability Indirect target selection: Not affected\nVulnerability Itlb multihit:             Not affected\nVulnerability L1tf:                      Not affected\nVulnerability Mds:                       Not affected\nVulnerability Meltdown:                  Not affected\nVulnerability Mmio stale data:           Not affected\nVulnerability Old microcode:             Not affected\nVulnerability Reg file data sampling:    Not affected\nVulnerability Retbleed:                  Not affected\nVulnerability Spec rstack overflow:      Vulnerable: Safe RET, no microcode\nVulnerability Spec store bypass:         Not affected\nVulnerability Spectre v1:                Mitigation; usercopy/swapgs barriers and __user pointer sanitization\nVulnerability Spectre v2:                Mitigation; Retpolines; STIBP disabled; RSB filling; PBRSB-eIBRS Not affected; BHI Not affected\nVulnerability Srbds:                     Not affected\nVulnerability Tsa:                       Vulnerable: No microcode\nVulnerability Tsx async abort:           Not affected\nVulnerability Vmscape:                   Not affected",
  "commit": "18b87efa6ffdcc4e7f4ed58936c824876a42d3fc",
  "git_changes": "",
  "source_hashes": {
    "benchmark/collect_traces.py": "dff7abd4388e57a6579ea6b6f8f418dce0e2d48e15bf66fcf6f0ea30a7298ac2",
    "monitor/capture.py": "5252317c51cb8c35f60a97678114254869fb2ed119eb1f51ec433742d347706a",
    "monitor/reader.py": "f46f1420837f7d93adbbcc63a58f4e4a550d036e71661422b67f3c1be1917d0b",
    "benchmark/safe_cpu_launcher.py": "da98be53571bb273bf40fb0bb60b8c9130af04ec178dc93fe081be768990865f",
    "scripts/run_safe_cpu_experiment.sh": "f26f82d689fffb0855bf2a6dfb34e6ce2e34464a76e64075f14c7ba7c91d7ffa",
    "scripts/run_background_readiness.sh": "2fad09a5880f05a0c7d547a44bd1ae8f1869054bf30895a4e2fb835da3628236",
    "benchmark/background_launcher.py": "76f816702683b89d43e23df7db5ad6c5ee6f3e98f5373b22c1f4d8ae1d79bee9",
    "collect_real_traces.sh": "66abc6406e85a4d424c585637c6c2f3b02ba8c30bb7bb881ac0c8ffd02408208"
  },
  "command": [
    "timeout",
    "--signal=TERM",
    "--kill-after=1s",
    "15s",
    "bash",
    "/home/vboxuser/Power_Aware_CPU_Governor/collect_real_traces.sh",
    "5",
    "64M",
    "/home/vboxuser/Power_Aware_CPU_Governor/data/background_readiness/launcher-20261015T144107Z-ulqlq_gi/collection",
    "--profile",
    "background"
  ],
  "launcher_child_pid": 36528,
  "collector_exit": 0,
  "manifest": {
    "status": "complete",
    "success": true,
    "workload_label": "uncontrolled_background",
    "processes": {
      "monitor_exit": 0,
      "worker_exit": null,
      "elapsed_s": 6.364050342001065
    },
    "sample_validation": {
      "success": true,
      "statistics": {
        "rows": 5,
        "workload_label": "uncontrolled_background",
        "observation_source": "linux_proc_stat",
        "elapsed_s": {
          "min": 1.0067027810000582,
          "mean": 1.2421605750001619,
          "max": 1.8549103749992355
        },
        "util_pct": {
          "min": 0.0,
          "mean": 0.3231045009245093,
          "max": 0.8676789587852495
        },
        "iowait_pct": {
          "min": 0.0,
          "mean": 0.0,
          "max": 0.0
        },
        "ctxt_per_s": {
          "min": 246.37308958940312,
          "mean": 389.20042390754,
          "max": 638.1285923027353
        },
        "iowait_decrease_intervals": 0
      }
    },
    "lifecycle": {
      "events": [
        {
          "event": "monitor_started",
          "elapsed_s": 0.001139334000981762,
          "utc": "2026-10-15T14:41:14.604770+00:00",
          "pid": 36533
        },
        {
          "event": "monitor_ready",
          "elapsed_s": 0.07937477199993737,
          "utc": "2026-10-15T14:41:14.683006+00:00"
        },
        {
          "event": "sampling_released",
          "elapsed_s": 0.07977056300114782,
          "utc": "2026-10-15T14:41:14.683400+00:00"
        },
        {
          "event": "monitor_exited",
          "elapsed_s": 6.363456770000994,
          "utc": "2026-10-15T14:41:20.967088+00:00",
          "exit_code": 0
        },
        {
          "event": "monitor_cleanup_requested",
          "elapsed_s": 6.364054048999606,
          "utc": "2026-10-15T14:41:20.967684+00:00",
          "exit_before_cleanup": 0
        },
        {
          "event": "cleanup_finished",
          "elapsed_s": 6.364476270000523,
          "utc": "2026-10-15T14:41:20.968106+00:00"
        }
      ],
      "monitor_exit": 0,
      "worker_exit": null,
      "cleanup": "completed"
    },
    "final_resources": {
      "mem_available_kib": 2333464,
      "swap_used_kib": 423728
    },
    "end_utc": "2026-10-15T14:41:20.969072+00:00"
  },
  "handshake_validation": "passed",
  "classifier_counts": {
    "mixed": 2,
    "idle": 3
  },
  "resources_after": {
    "mem_available_kib": 2341012,
    "swap_used_kib": 423728
  },
  "exit_code": 0,
  "end_utc": "2026-10-15T14:41:20.998920+00:00",
  "success": true
}
```

Interpretation: actual Linux counters; no frequency writes or measured energy. Background-only observations are uncontrolled kernel counters, not idle ground truth or a CPU workload dataset. Guest timers cannot recover an unresponsive VM/host. No retry occurred.

Next action: review manifest, worker logs and CSV; obtain approval before any further experiment.
