# Tab. 11 -- S9 component ablation (paper [Fan26] §6.8)

CM8 reactive jamming, 10 dBm, 20 dB target SNR, six-user round-robin
fairness subset, three seeds, three payload sizes, two distances.

## Reactive jamming

| MCS | Variant | PDR | PDR jammer-ON | p95 delay [ms] | Jain |
| --- | --- | --- | --- | --- | --- |
| 0 | full | 1.0000 | 1.0000 | 5.372 | 1.0000 |
| 0 | no_jammer_flag | 1.0000 | 1.0000 | 5.372 | 1.0000 |
| 0 | no_cooldown | 0.9892 | 0.9857 | 4.497 | 1.0000 |
| 0 | snir_only | 1.0000 | 1.0000 | 5.372 | 1.0000 |
| 1 | full | 1.0000 | 1.0000 | 5.206 | 1.0000 |
| 1 | no_jammer_flag | 1.0000 | 1.0000 | 5.206 | 1.0000 |
| 1 | no_cooldown | 0.9673 | 0.9541 | 4.474 | 0.9999 |
| 1 | snir_only | 1.0000 | 1.0000 | 5.206 | 1.0000 |
| 3 | full | 0.9869 | 0.9802 | 10.191 | 1.0000 |
| 3 | no_jammer_flag | 0.9869 | 0.9802 | 10.191 | 1.0000 |
| 3 | no_cooldown | 0.7522 | 0.6739 | 4.141 | 0.9950 |
| 3 | snir_only | 0.9824 | 0.9826 | 10.191 | 1.0000 |


## Clean baseline

| MCS | Variant | PDR | PDR jammer-ON | p95 delay [ms] | Jain |
| --- | --- | --- | --- | --- | --- |
| 0 | full | 1.0000 | 0.0000 | 0.127 | 1.0000 |
| 0 | no_jammer_flag | 1.0000 | 0.0000 | 0.127 | 1.0000 |
| 0 | no_cooldown | 0.9917 | 0.0000 | 0.127 | 1.0000 |
| 0 | snir_only | 1.0000 | 0.0000 | 0.127 | 1.0000 |
| 1 | full | 1.0000 | 0.0000 | 1.302 | 1.0000 |
| 1 | no_jammer_flag | 1.0000 | 0.0000 | 1.302 | 1.0000 |
| 1 | no_cooldown | 0.9754 | 0.0000 | 0.086 | 1.0000 |
| 1 | snir_only | 1.0000 | 0.0000 | 0.086 | 1.0000 |
| 3 | full | 0.9952 | 0.0000 | 8.917 | 1.0000 |
| 3 | no_jammer_flag | 0.9952 | 0.0000 | 8.917 | 1.0000 |
| 3 | no_cooldown | 0.8062 | 0.0000 | 0.424 | 1.0000 |
| 3 | snir_only | 0.9886 | 0.0000 | 6.427 | 1.0000 |
