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
- Hypervisor: KVM (per `lscpu`), full virtualization
- Root cause of Outcome B: standard for VirtualBox/KVM guests — the vCPU doesn't get ACPI P-state/MSR passthrough, so no cpufreq driver has anything to bind to. Not a misconfiguration; not fixable by installing packages in the guest.
