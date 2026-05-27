# Tab. 10 -- S9 estimator-impairment sensitivity (paper [Fan26] §6.7)

CM8 reactive jamming, 10 dBm, 20 dB target SNR, three seeds, three payload
sizes, two distances. Each row aggregates the matching CSV rows from the
`s9_estimator_sensitivity` campaign.

## Reactive jamming

| MCS | Profile | PDR | PLR/PER | PDR jammer-ON | p95 delay [ms] | # defer |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | ideal | 1.0000 | 0.0000 | 1.0000 | 5.372 | 27122 |
| 0 | moderate | 1.0000 | 0.0000 | 0.9999 | 5.408 | 31041 |
| 0 | conservative | 1.0000 | 0.0000 | 0.9999 | 5.408 | 35147 |
| 1 | ideal | 1.0000 | 0.0000 | 1.0000 | 5.206 | 29188 |
| 1 | moderate | 0.9998 | 0.0002 | 0.9992 | 5.292 | 32752 |
| 1 | conservative | 0.9998 | 0.0002 | 0.9992 | 5.292 | 37252 |
| 3 | ideal | 0.9869 | 0.0131 | 0.9802 | 10.191 | 51824 |
| 3 | moderate | 0.9756 | 0.0244 | 0.9608 | 10.249 | 54876 |
| 3 | conservative | 0.9765 | 0.0235 | 0.9622 | 10.249 | 58607 |


## Clean baseline

| MCS | Profile | PDR | PLR/PER | p95 delay [ms] | # defer |
| --- | --- | --- | --- | --- | --- |
| 0 | ideal | 1.0000 | 0.0000 | 0.127 | 3316 |
| 0 | moderate | 1.0000 | 0.0000 | 1.343 | 8243 |
| 0 | conservative | 1.0000 | 0.0000 | 1.343 | 13783 |
| 1 | ideal | 1.0000 | 0.0000 | 1.302 | 6532 |
| 1 | moderate | 1.0000 | 0.0000 | 1.302 | 11176 |
| 1 | conservative | 1.0000 | 0.0000 | 1.302 | 17143 |
| 3 | ideal | 0.9952 | 0.0048 | 8.917 | 40065 |
| 3 | moderate | 0.9891 | 0.0109 | 8.106 | 43579 |
| 3 | conservative | 0.9897 | 0.0103 | 8.025 | 48177 |
