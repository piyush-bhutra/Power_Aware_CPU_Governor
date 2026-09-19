# Phase 0 — cpufreq feasibility check

**Status: DONE — Outcome B confirmed.** Blocks Modules 1 and 4 resolved: build the simulated cpufreq layer.

## Commands run in the VM (raw output below each)

```bash
lscpu | head -20
```
```
Architecture:                            x86_64
CPU op-mode(s):                          32-bit, 64-bit
Address sizes:                           48 bits physical, 48 bits virtual
Byte Order:                              Little Endian
CPU(s):                                  4
On-line CPU(s) list:                     0-3
Vendor ID:                               AuthenticAMD
Model name:                              AMD Ryzen 7 7840HS w/ Radeon 780M Graphics
CPU family:                              25
Model:                                   116
Thread(s) per core:                      1
Core(s) per socket:                      4
Socket(s):                               1
Stepping:                                1
BogoMIPS:                                7585.85
Flags:                                   fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 ht syscall nx mmxext fxsr_opt rdtscp lm constant_tsc rep_good nopl xtopology nonstop_tsc cpuid extd_apicid tsc_known_freq pni pclmulqdq ssse3 fma cx16 sse4_1 sse4_2 movbe popcnt aes xsave avx f16c rdrand hypervisor lahf_lm cmp_legacy cr8_legacy abm sse4a misalignsse 3dnowprefetch vmmcall fsgsbase bmi1 avx2 bmi2 invpcid rdseed adx clflushopt sha_ni arat
Hypervisor vendor:                       KVM
Virtualization type:                     full
NUMA node(s):                            1
NUMA node0 CPU(s):                       0-3
```

```bash
nproc
```
```
4
```

```bash
ls /sys/devices/system/cpu/cpu0/cpufreq/
```
```
ls: cannot access '/sys/devices/system/cpu/cpu0/cpufreq/': No such file or directory
```

```bash
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors
```
```
cat: /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors: No such file or directory
```

```bash
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies
```
```
cat: /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies: No such file or directory
```

```bash
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver
```
```
cat: /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver: No such file or directory
```

### Write-verification

```bash
sudo cpupower frequency-set -g userspace
```
```
Setting cpu: 0
Error setting new values. Common errors:
- Do you have proper administration rights? (super-user?)
- Is the governor you requested available and modprobed?
- Trying to set an invalid policy?
- Trying to set a specific frequency, but userspace governor is not available,
   for example because of hardware which cannot be set to a specific frequency
   or because the userspace governor isn't loaded?
```

```bash
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq
```
```
cat: /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq: No such file or directory
```

```bash
sudo sh -c 'echo 2000000 > /sys/devices/system/cpu/cpu0/cpufreq/scaling_setspeed'
```
```
sh: 1: cannot create /sys/devices/system/cpu/cpu0/cpufreq/scaling_setspeed: Directory nonexistent
```

```bash
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq   # did it change?
```
```
cat: /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq: No such file or directory
```

### Per-core check (cpu0..cpu3)

```bash
for i in 0 1 2 3; do
  echo "--- cpu$i ---"
  ls /sys/devices/system/cpu/cpu$i/cpufreq/ 2>&1
done
```
```
--- cpu0 ---
ls: cannot access '/sys/devices/system/cpu/cpu0/cpufreq/': No such file or directory
--- cpu1 ---
ls: cannot access '/sys/devices/system/cpu/cpu1/cpufreq/': No such file or directory
--- cpu2 ---
ls: cannot access '/sys/devices/system/cpu/cpu2/cpufreq/': No such file or directory
--- cpu3 ---
ls: cannot access '/sys/devices/system/cpu/cpu3/cpufreq/': No such file or directory
```

## Outcome

- [ ] **A — real control.** cpufreq present, `userspace` available, writes change
      `scaling_cur_freq`. Build a real frequency setter; only power is estimated.
- [x] **B — no real control.** Directory missing or writes are silent no-ops.
      Build a simulated cpufreq layer behind the same interface. Modules 2 and 3
      are unaffected.

## Decisions that fall out of this

| Question | Answer |
|---|---|
| Outcome A or B | **B** |
| vCPU count | **4** |
| Shared or independent frequency domains | **N/A** — no cpufreq interface exists on any of the 4 cores, confirmed individually |
| Classifier/policy granularity (whole-system vs per-vCPU) | **Whole-system** — no per-vCPU control is possible on this VM |
| Available frequencies (feed to `Policy(available_khz=...)`) | **N/A from hardware** — synthetic ladder used instead: `RYZEN_7840HS_LADDER_KHZ` in `hardware_profile.py` (the single source; used by the setter fallback and `setter/mock_kernel.py`) |
| f_max in kHz (feed to `estimate_power_w`) | `RYZEN_7840HS_LADDER_KHZ[-1]` — the ladder's top step, the Ryzen 7 7840HS boost clock |
| Does the hardware ever partially clamp/no-op a write (not just fully ignore cpufreq)? | **N/A** — the cpufreq directory is fully absent on every core, not partially functional, so `test_hardware_desync.py`'s scenario doesn't apply to this environment |

## Environment notes

- VM: VirtualBox on Windows host, 4 vCPUs, 4GB RAM, 30GB disk
- Underlying host CPU: AMD Ryzen 7 7840HS (mobile, real boost clock 5.1 GHz)
- Hypervisor: VirtualBox, full virtualization. The `Hypervisor vendor: KVM` line in the `lscpu` output above was VirtualBox's default KVM paravirtualization interface, not a KVM host. That interface has since been switched to `legacy` (see [VirtualBox/AMD Zen 4 timing issues](#virtualboxamd-zen-4-timing-issues--resolved)), and `lscpu` no longer reports a hypervisor vendor.
- Root cause of Outcome B: standard for VirtualBox/KVM guests — the vCPU doesn't get ACPI P-state/MSR passthrough, so no cpufreq driver has anything to bind to. Not a misconfiguration; not fixable by installing packages in the guest.

## Stress-ng environment notes

*Added 2026-09-19. All items below are resolved; the timing investigation is written up in the next section.*

- **SIGILL workaround (resolved).** stress-ng's default `--cpu`, `--vm` and `--hdd` methods crash with SIGILL on this VM. The faulting instruction uses an EVEX (AVX-512) prefix, and `/proc/cpuinfo` shows no `avx512*` flags. A host-side CPUID fix is also required; see the next section. Workarounds in `collect_real_traces.sh`:
  - cpu: `--cpu-method int64` (runs cleanly).
  - vm: `--vm-method flip` (runs cleanly).
  - io: a `dd` direct-I/O loop (`oflag=direct conv=fsync`) replaces `--hdd`. Verified at about 5.9% mean iowait over 20 ticks, up from about 0.6% with the earlier method.
- **4-vCPU time dilation (resolved).** Caused by VirtualBox's KVM paravirtualization interface, not host contention. See the next section.

## VirtualBox/AMD Zen 4 timing issues — RESOLVED

*Resolved 2026-09-19.* Two separate bugs were found and fixed. Both fixes are host-side `VBoxManage` settings. The VM must be **fully powered off** (not just closed or saved) for them to apply, and they must be **re-applied if the VM is ever deleted and recreated**.

### 1. SIGILL crash in stress-ng's default methods

- **Symptom:** stress-ng's default `--cpu` and `--vm` methods crash with SIGILL.
- **Cause:** AMD Zen 4 mobile CPUs expose CPUID data under VirtualBox that makes stress-ng's default methods crash.
- **Guest-side workaround:** `--cpu-method int64` and `--vm-method flip` (already used in `collect_real_traces.sh`).
- **Host-side fix (also required):**

  ```bash
  VBoxManage setextradata osproject VBoxInternal/CPUM/HostCPUID/80000006/edx 0x02009140
  ```

  This is a known community workaround for a division-by-zero-class bug on Ryzen Zen 4 mobile CPUs under VirtualBox.

### 2. Severe, worsening time drift under 2+ concurrent CPU-bound workers

- **Symptom:** an 8 s stress-ng job on 2 workers took longer on each repeated run: 6.9 s, then 28.5 s, then 34 s, then 104 s. That is up to about 20x slower than requested. This is the same effect as the earlier 4-worker observation: an 8 s run taking 5 m 49 s, and `/proc/stat` advancing about 205 jiffies over a 2 s window where about 800 were expected.
- **Host contention ruled out:** host Task Manager showed CPU usage never above 18% during the slow runs.
- **Cause:** VirtualBox's default paravirtualization interface for Linux guests is "KVM". `lscpu` confirmed it was active (`Hypervisor vendor: KVM`). This interface has a long-documented bug that causes severe guest time drift under load.
- **Fix (host-side, VM powered off):**

  ```bash
  VBoxManage modifyvm osproject --paravirtprovider legacy
  ```

- **Verification after the fix:**
  - Idle baseline, 3 runs of a timed 5 s sleep: 5.001 s, 5.008 s and 5.006 s.
  - 2 workers, 3 repeated runs: a timed 5 s sleep measured 5.000 s each time while an 8 s `stress-ng --cpu 2` ran in the background. Each stress-ng run reported `successful run completed in 8.01 secs` (2 passed, 0 failed, 0 metrics untrustworthy). There was no slowdown across repeats, unlike the escalating runs before the fix.
  - 4 workers, 5 s `stress-ng --cpu 4 --cpu-method int64`: 5.15 s wall-clock, including stress-ng startup.
  - `/proc/stat` under 4 workers advanced 782 jiffies over 2 s, against about 800 expected. Before the fix it advanced about 205.
  - `lscpu` no longer reports `Hypervisor vendor: KVM`.

This is a full fix, not a workaround. `util_pct` data collected under the 4-worker cpu profile can be trusted again, but only for data collected **after** the fix. Discard any traces recorded before it.

### Swap safety net

The VM originally had no swap. This probably turned an earlier memory-pressure slowdown during I/O testing into a full freeze that could not be recovered. A 2 GB `/swapfile` was added and persisted via `/etc/fstab` as a standing safety net.
