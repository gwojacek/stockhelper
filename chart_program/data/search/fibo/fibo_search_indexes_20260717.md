## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ITA40 | long | 🚀 3p_steep_incline | 2026-03-23->2026-07-07 | 73/1 (27.89:1) | - | 10211546541340 | [📈](https://stooq.pl/q/a2/?s=%5Efmib&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c ITA40 --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-07-07 --fibo-right | ✅ | 2026-07-17 | 2026-07-17 |
## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BRACOMP | long | reached_23_6_waiting_for_61_8 | none | 2025-10-10->2026-04-14 | 124/25 (4.96:1) |  | 1073604612490 |  51.7% | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --fibo-lines 5 --fibo-anchor-start 2025-10-10 --fibo-anchor-end 2026-04-14 --fibo-right | ✅ | 2026-07-17 | 2026-07-17 |
| HK.CASH | short | reached_23_6_waiting_for_61_8 | none | 2026-01-29->2026-06-26 | 97/14 (6.93:1) |  | 69649151699023 |  34.8% | [📈](https://stooq.pl/q/a2/?s=%5Ehsi&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c HK.CASH --fibo-lines 5 --fibo-anchor-start 2026-01-29 --fibo-anchor-end 2026-06-26 --fibo-right | ✅ | 2026-07-17 | 2026-07-17 |
| BRACOMP | short | reached_23_6_waiting_for_61_8 | none | 2026-02-25->2026-06-19 | 78/10 (7.80:1) |  | 1073604612490 |   1.7% | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --fibo-lines 5 --fibo-anchor-start 2026-02-25 --fibo-anchor-end 2026-06-19 --fibo-right | ✅ | 2026-07-17 | 2026-07-17 |
## WYNIKI FIBO #2 (valid pattern up to 2 weeks)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MEXCOMP | ⏳ unbroken | 2025-12-17->2026-07-17 | 146 | 7.0 | 2026-02-12@72111.40625->2026-02-27@71890.34375 | 2025-12-17@62461.05859->2026-06-09@64666.23828 | 3 | 2 | 13.41% | 7.15% | mild | - | - | 277.08 | 8674159851393 | [📈](https://stooq.pl/q/a2/?s=%5Eipc&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c MEXCOMP --wedge-lines --wedge-upper-start 2026-02-12,72111.40625 --wedge-upper-end 2026-02-27,71890.34375 --wedge-lower-start 2025-12-17,62461.05859 --wedge-lower-end 2026-06-09,64666.23828 --wedge-right | ✅ | 2026-07-17 | 2026-07-17 |
| US100 | ⏳ unbroken | 2026-05-12->2026-07-17 | 46 | 2.2 | 2026-06-22@30642.57031->2026-06-30@30328.78906 | 2026-05-12@28628.64062->2026-05-19@28567.16016 | 2 | 2 | 8.20% | 5.69% | moderate | - | - | 68.01 | 206967699469861 | [📈](https://stooq.pl/q/a2/?s=%5Endx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c US100 --wedge-lines --wedge-upper-start 2026-06-22,30642.57031 --wedge-upper-end 2026-06-30,30328.78906 --wedge-lower-start 2026-05-12,28628.64062 --wedge-lower-end 2026-05-19,28567.16016 --wedge-right | ✅ | 2026-07-17 | 2026-07-17 |
