## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| US100 | long | 🚀 3p_steep_incline | 2026-03-30->2026-06-03 | 45/1 (34.68:1) | - | 302309511963805 | [📈](https://stooq.pl/q/a2/?s=%5Endx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c US100 --fibo-lines 5 --fibo-anchor-start 2026-03-30 --fibo-anchor-end 2026-06-03 --fibo-right | ✅ | 2026-06-12 | 2026-06-12 |
| ITA40 | long | 🚀 3p_steep_incline | 2026-03-23->2026-06-12 | 56/1 (24.10:1) | - | 19914987411180 | [📈](https://stooq.pl/q/a2/?s=%5Efmib&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c ITA40 --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-06-12 --fibo-right | ✅ | 2026-06-12 | 2026-06-12 |
## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BRACOMP | long | reached_23_6_waiting_for_61_8 | none | 2025-10-10->2026-04-14 | 124/25 (4.96:1) |  | 1603767012520 |  63.2% | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --fibo-lines 5 --fibo-anchor-start 2025-10-10 --fibo-anchor-end 2026-04-14 --fibo-right | ✅ | 2026-06-12 | 2026-06-12 |
## WYNIKI FIBO #2 (valid pattern >5 days, last month)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| UK100 | ⏳ unbroken | 2026-05-12->2026-06-12 | 23 | 1.1 | 2026-04-20@10683.7002->2026-05-26@10557.2002 | 2026-05-12@10152.09961->2026-06-10@10127.59961 | 2 | 3 | 4.32% | 3.47% | mild | - | - | 12.10 | 8454173197308 | [📈](https://stooq.pl/q/a2/?s=%5Eukx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c UK100 --wedge-lines --wedge-upper-start 2026-04-20,10683.7002 --wedge-upper-end 2026-05-26,10557.2002 --wedge-lower-start 2026-05-12,10152.09961 --wedge-lower-end 2026-06-10,10127.59961 --wedge-right | ✅ | 2026-06-12 | 2026-06-12 |
