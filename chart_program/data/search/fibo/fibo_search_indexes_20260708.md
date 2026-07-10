## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ITA40 | long | 🚀 3p_steep_incline | 2026-03-23->2026-07-07 | 73/1 (27.89:1) | - | 10108850602920 | [📈](https://stooq.pl/q/a2/?s=%5Efmib&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c ITA40 --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-07-07 --fibo-right | ✅ | 2026-07-08 | 2026-07-08 |
## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BRACOMP | long | reached_23_6_waiting_for_61_8 | none | 2025-10-10->2026-04-14 | 124/18 (6.89:1) |  | 848087430350 |  65.3% | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --fibo-lines 5 --fibo-anchor-start 2025-10-10 --fibo-anchor-end 2026-04-14 --fibo-right | ✅ | 2026-07-08 | 2026-07-08 |
## WYNIKI FIBO #2 (valid pattern up to 2 weeks)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| UK100 | 🚀 breakout | 2025-11-21->2026-07-08 | 157 | 7.5 | 2026-02-27@10934.90039->2026-06-25@10575.30957 | 2025-11-21@9423.90039->2026-03-23@9670.5 | 3 | 2 | 12.51% | 6.17% | mild | 2026-07-02 | long | 783.58 | 6062151418722 | [📈](https://stooq.pl/q/a2/?s=%5Eukx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c UK100 --wedge-lines --wedge-upper-start 2026-02-27,10934.90039 --wedge-upper-end 2026-06-25,10575.30957 --wedge-lower-start 2025-11-21,9423.90039 --wedge-lower-end 2026-03-23,9670.5 --wedge-right | ✅ | 2026-07-08 | 2026-07-08 |
| MEXCOMP | ⏳ unbroken | 2025-11-24->2026-07-08 | 155 | 7.4 | 2026-02-12@72111.40625->2026-02-27@71890.34375 | 2025-11-24@61840.51172->2026-06-09@64666.23828 | 3 | 2 | 13.70% | 7.49% | mild | - | - | 305.37 | 8416433275114 | [📈](https://stooq.pl/q/a2/?s=%5Eipc&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c MEXCOMP --wedge-lines --wedge-upper-start 2026-02-12,72111.40625 --wedge-upper-end 2026-02-27,71890.34375 --wedge-lower-start 2025-11-24,61840.51172 --wedge-lower-end 2026-06-09,64666.23828 --wedge-right | ✅ | 2026-07-08 | 2026-07-08 |
| AU200.CASH | ⏳ unbroken | 2026-03-03->2026-07-08 | 89 | 4.2 | 2026-03-03@9200.90039->2026-06-18@8983.7998 | 2026-05-20@8485.2002->2026-06-09@8490.90039 | 2 | 2 | 6.34% | 5.04% | mild | - | - | 107.78 | 5382908050 | [📈](https://stooq.pl/q/a2/?s=%5Eaor&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c AU200.CASH --wedge-lines --wedge-upper-start 2026-03-03,9200.90039 --wedge-upper-end 2026-06-18,8983.7998 --wedge-lower-start 2026-05-20,8485.2002 --wedge-lower-end 2026-06-09,8490.90039 --wedge-right | ✅ | 2026-07-08 | 2026-07-08 |
