# Governor self-overhead (measured on this Linux host)

Plan: intervals [0.5, 1.0, 2.0, 5.0] s, 60 s of ticks per run, 3 repetition(s), governor and sleep-only control. No generated load; simulated setter (no frequency writes). Net = governor minus control per repetition; median [min, max] across repetitions.

Runs: 24 ok, 0 failed.

## Net governor cost (primary: CPU ms per tick)

| interval s | net CPU ms/tick (mean) | net p95 ms/tick | net CPU % of one core (derived) | net CPU-s/hour (derived) | net CPU % from /proc/self/stat (quantized) | net wake-ups/s | pairs |
|---|---|---|---|---|---|---|---|
| 0.5 | 0.5988 [0.5554, 0.6218] | 0.8634 [0.6768, 0.9011] | 0.1198 [0.1111, 0.1244] | 4.312 [3.999, 4.477] | 0.0712 [0.0470, 0.1107] | -0.180 [-0.679, -0.015] | 3 |
| 1 | 0.6168 [0.5390, 0.6694] | 0.8142 [0.6604, 0.8542] | 0.0617 [0.0539, 0.0669] | 2.221 [1.940, 2.410] | 0.0481 [0.0293, 0.0659] | -0.002 [-0.236, 0.004] | 3 |
| 2 | 0.5483 [0.4642, 0.5703] | 0.6584 [0.5411, 0.7816] | 0.0274 [0.0232, 0.0285] | 0.987 [0.836, 1.027] | 0.0318 [0.0003, 0.0328] | 0.001 [-0.007, 0.010] | 3 |
| 5 | 0.5861 [0.4591, 0.5964] | 0.7012 [0.3504, 0.7631] | 0.0117 [0.0092, 0.0119] | 0.422 [0.331, 0.429] | 0.0008 [0.0000, 0.0166] | -0.000 [-0.000, 0.010] | 3 |

## Per mode

| interval s | mode | CPU ms/tick (mean) | CPU % of one core (derived) | RSS KiB | runs ok |
|---|---|---|---|---|---|
| 0.5 | governor | 0.7215 [0.6618, 0.7239] | 0.1443 [0.1324, 0.1448] | 17712 [17500, 17716] | 3 |
| 0.5 | control | 0.1063 [0.1022, 0.1227] | 0.0213 [0.0204, 0.0245] | 17708 [17704, 17720] | 3 |
| 1 | governor | 0.7211 [0.6492, 0.7843] | 0.0721 [0.0649, 0.0784] | 17716 [17708, 17720] | 3 |
| 1 | control | 0.1102 [0.1043, 0.1149] | 0.0110 [0.0104, 0.0115] | 17716 [17708, 17724] | 3 |
| 2 | governor | 0.6708 [0.6069, 0.6796] | 0.0335 [0.0303, 0.0340] | 17716 [17708, 17724] | 3 |
| 2 | control | 0.1225 [0.1092, 0.1427] | 0.0061 [0.0055, 0.0071] | 17716 [17708, 17724] | 3 |
| 5 | governor | 0.6792 [0.6042, 0.7224] | 0.0136 [0.0121, 0.0144] | 17716 [17708, 17724] | 3 |
| 5 | control | 0.1261 [0.0931, 0.1451] | 0.0025 [0.0019, 0.0029] | 17716 [17708, 17724] | 3 |

## VM timer overshoot

| interval s | mode | actual/planned elapsed | sleep overshoot mean ms | p95 ms | max ms |
|---|---|---|---|---|---|
| 0.5 | governor | 1.5718 [1.0529, 1.7161] | 285.295 [25.851, 357.433] | 1043.440 [100.841, 1270.678] | 1686.841 [1170.493, 3210.218] |
| 0.5 | control | 1.0845 [1.0445, 1.3772] | 42.209 [22.219, 188.589] | 213.503 [29.086, 1113.195] | 1302.214 [600.355, 1618.897] |
| 1 | governor | 1.0397 [1.0117, 1.3459] | 39.157 [11.087, 345.189] | 243.599 [42.032, 1082.068] | 858.519 [139.818, 1604.458] |
| 1 | control | 1.0217 [1.0156, 1.0373] | 21.723 [15.528, 37.246] | 66.035 [53.157, 94.956] | 664.803 [238.213, 1078.855] |
| 2 | governor | 1.0164 [1.0073, 1.0479] | 32.208 [13.988, 95.280] | 51.468 [36.822, 1131.560] | 779.902 [80.275, 1424.839] |
| 2 | control | 1.0280 [1.0181, 1.0321] | 56.006 [36.154, 64.144] | 409.034 [149.865, 609.393] | 626.300 [258.494, 838.779] |
| 5 | governor | 1.0014 [1.0011, 1.0031] | 6.666 [5.137, 14.692] | 19.020 [13.823, 48.767] | 19.020 [13.823, 48.767] |
| 5 | control | 1.0014 [1.0013, 1.0529] | 6.940 [6.432, 264.380] | 36.199 [22.438, 2194.037] | 36.199 [22.438, 2194.037] |

Primary metric: CPU ms per tick from time.process_time(). CPU % of one core (derived) = mean ms per tick / (interval s x 1000) x 100, projected at the nominal tick rate. The /proc/self/stat percentage is secondary: it is quantized to the 10 ms kernel clock and can read zero or negative in short runs. Wake-ups/s = voluntary context switches per second. Excludes CSV logging and UI rendering. This is process CPU time, not electrical power.
