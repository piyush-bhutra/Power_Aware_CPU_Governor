# Phase 0 — cpufreq feasibility check

**Status: NOT RUN.** Fill this in once the Ubuntu VM exists. Blocks Modules 1 and 4.

## Commands to run in the VM (paste raw output under each)

```bash
lscpu | head -20
nproc
ls /sys/devices/system/cpu/cpu0/cpufreq/
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver
```

Then verify writes actually take effect:

```bash
sudo cpupower frequency-set -g userspace
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq
sudo sh -c 'echo <some_freq> > /sys/devices/system/cpu/cpu0/cpufreq/scaling_setspeed'
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq   # did it change?
```

Do the same for cpu1..cpuN to see whether vCPUs share one frequency domain
(writing cpu0 changes cpu1's `scaling_cur_freq`) or scale independently.

## Outcome

- [ ] **A — real control.** cpufreq present, `userspace` available, writes change
      `scaling_cur_freq`. Build a real frequency setter; only power is estimated.
- [ ] **B — no real control.** Directory missing or writes are silent no-ops.
      Build a simulated cpufreq layer behind the same interface. Modules 2 and 3
      are unaffected.

## Decisions that fall out of this

| Question | Answer |
|---|---|
| Outcome A or B | |
| vCPU count | |
| Shared or independent frequency domains | |
| Classifier/policy granularity (whole-system vs per-vCPU) | |
| Available frequencies (feed to `Policy(available_khz=...)`) | |
| f_max in kHz (feed to `estimate_power_w`) | |
