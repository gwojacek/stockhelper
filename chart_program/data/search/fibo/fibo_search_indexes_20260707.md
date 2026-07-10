## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ITA40 | long | 🚀 3p_steep_incline | 2026-03-23->2026-06-19 | 61/1 (27.81:1) | - | 11571321722720 | [📈](https://stooq.pl/q/a2/?s=%5Efmib&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c ITA40 --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-06-19 --fibo-right | ❌ | 2026-07-06 | 2026-07-07 |
## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BRACOMP | long | reached_23_6_waiting_for_61_8 | none | 2025-10-10->2026-04-14 | 124/17 (7.29:1) |  | 894943567680 |  59.2% | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --fibo-lines 5 --fibo-anchor-start 2025-10-10 --fibo-anchor-end 2026-04-14 --fibo-right | ✅ | 2026-07-07 | 2026-07-07 |
## WYNIKI FIBO #2 (valid pattern >5 days, last month)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| UK100 | 🚀 breakout | 2025-11-21->2026-07-07 | 156 | 7.4 | 2026-02-27@10934.90039->2026-06-25@10575.30957 | 2025-11-21@9423.90039->2026-03-23@9670.5 | 3 | 2 | 12.30% | 6.14% | mild | 2026-07-02 | long | 991.82 | 6383174272525 | [📈](https://stooq.pl/q/a2/?s=%5Eukx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c UK100 --wedge-lines --wedge-upper-start 2026-02-27,10934.90039 --wedge-upper-end 2026-06-25,10575.30957 --wedge-lower-start 2025-11-21,9423.90039 --wedge-lower-end 2026-03-23,9670.5 --wedge-right | ✅ | 2026-07-07 | 2026-07-07 |
| FRA40 | 🚀 breakout | 2026-02-26->2026-07-06 | 90 | 4.3 | 2026-02-26@8642.23047->2026-06-15@8506.65039 | 2026-06-01@8101.1499->2026-06-10@8113.0 | 3 | 2 | 5.00% | 3.96% | mild | 2026-07-03 | long | 545.43 | 460087174659 | [📈](https://stooq.pl/q/a2/?s=%5Ecac&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c FRA40 --wedge-lines --wedge-upper-start 2026-02-26,8642.23047 --wedge-upper-end 2026-06-15,8506.65039 --wedge-lower-start 2026-06-01,8101.1499 --wedge-lower-end 2026-06-10,8113.0 --wedge-right | ❌ | 2026-07-06 | 2026-07-07 |
| MEXCOMP | ⏳ unbroken | 2025-12-17->2026-07-07 | 138 | 6.6 | 2026-02-12@72111.40625->2026-02-27@71890.34375 | 2025-12-17@62461.05859->2026-06-09@64666.23828 | 3 | 2 | 13.40% | 7.62% | mild | - | - | 298.07 | 9174565824938 | [📈](https://stooq.pl/q/a2/?s=%5Eipc&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c MEXCOMP --wedge-lines --wedge-upper-start 2026-02-12,72111.40625 --wedge-upper-end 2026-02-27,71890.34375 --wedge-lower-start 2025-12-17,62461.05859 --wedge-lower-end 2026-06-09,64666.23828 --wedge-right | ✅ | 2026-07-07 | 2026-07-07 |
| AU200.CASH | ⏳ unbroken | 2026-03-03->2026-07-06 | 87 | 4.1 | 2026-03-03@9200.90039->2026-06-18@8983.7998 | 2026-05-20@8485.2002->2026-06-09@8490.90039 | 2 | 2 | 6.31% | 5.09% | mild | - | - | 86.94 | 6259997714 | [📈](https://stooq.pl/q/a2/?s=%5Eaor&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c AU200.CASH --wedge-lines --wedge-upper-start 2026-03-03,9200.90039 --wedge-upper-end 2026-06-18,8983.7998 --wedge-lower-start 2026-05-20,8485.2002 --wedge-lower-end 2026-06-09,8490.90039 --wedge-right | ❌ | 2026-07-06 | 2026-07-07 |
