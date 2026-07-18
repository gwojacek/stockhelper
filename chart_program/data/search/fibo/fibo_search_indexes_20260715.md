## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| JP225 | long | 🚀 3p_steep_incline | 2025-07-14->2026-06-22 | 227/1 (85.37:1) | - | 8670153447344 | [📈](https://stooq.pl/q/a2/?s=%5Enkx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c JP225 --fibo-lines 5 --fibo-anchor-start 2025-07-14 --fibo-anchor-end 2026-06-22 --fibo-right | ✅ | 2026-07-15 | 2026-07-15 |
| ITA40 | long | 🚀 3p_steep_incline | 2026-03-23->2026-07-07 | 73/1 (27.89:1) | - | 10437003114250 | [📈](https://stooq.pl/q/a2/?s=%5Efmib&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c ITA40 --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-07-07 --fibo-right | ✅ | 2026-07-15 | 2026-07-15 |
## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BRACOMP | long | reached_23_6_waiting_for_61_8 | none | 2025-10-10->2026-04-14 | 124/23 (5.39:1) |  | 1006414016920 |  41.7% | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --fibo-lines 5 --fibo-anchor-start 2025-10-10 --fibo-anchor-end 2026-04-14 --fibo-right | ✅ | 2026-07-15 | 2026-07-15 |
| BRACOMP | short | reached_23_6_waiting_for_61_8 | none | 2026-04-14->2026-06-19 | 45/18 (2.50:1) |  | 1006414016920 |   7.0% | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --fibo-lines 5 --fibo-anchor-start 2026-04-14 --fibo-anchor-end 2026-06-19 --fibo-right | ✅ | 2026-07-15 | 2026-07-15 |
## WYNIKI FIBO #2 (valid pattern up to 2 weeks)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MEXCOMP | ⏳ unbroken | 2025-11-24->2026-07-15 | 160 | 7.6 | 2026-02-12@72111.40625->2026-02-27@71890.34375 | 2025-11-24@61840.51172->2026-06-09@64666.23828 | 3 | 2 | 13.76% | 7.22% | mild | - | - | 300.70 | 6988368921477 | [📈](https://stooq.pl/q/a2/?s=%5Eipc&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c MEXCOMP --wedge-lines --wedge-upper-start 2026-02-12,72111.40625 --wedge-upper-end 2026-02-27,71890.34375 --wedge-lower-start 2025-11-24,61840.51172 --wedge-lower-end 2026-06-09,64666.23828 --wedge-right | ✅ | 2026-07-15 | 2026-07-15 |
| US100 | ⏳ unbroken | 2026-05-04->2026-07-15 | 50 | 2.4 | 2026-06-22@30642.57031->2026-06-30@30328.78906 | 2026-05-04@27504.08984->2026-06-09@28196.90039 | 2 | 2 | 7.50% | 3.18% | strong | - | - | 84.90 | 212199008575523 | [📈](https://stooq.pl/q/a2/?s=%5Endx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c US100 --wedge-lines --wedge-upper-start 2026-06-22,30642.57031 --wedge-upper-end 2026-06-30,30328.78906 --wedge-lower-start 2026-05-04,27504.08984 --wedge-lower-end 2026-06-09,28196.90039 --wedge-right | ✅ | 2026-07-15 | 2026-07-15 |
| AU200.CASH | ⏳ unbroken | 2026-03-04->2026-07-15 | 93 | 4.4 | 2026-03-04@9077.2998->2026-06-18@8983.7998 | 2026-05-20@8485.2002->2026-06-09@8490.90039 | 2 | 2 | 5.93% | 5.17% | mild | - | - | 71.57 | 4808886573 | [📈](https://stooq.pl/q/a2/?s=%5Eaor&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c AU200.CASH --wedge-lines --wedge-upper-start 2026-03-04,9077.2998 --wedge-upper-end 2026-06-18,8983.7998 --wedge-lower-start 2026-05-20,8485.2002 --wedge-lower-end 2026-06-09,8490.90039 --wedge-right | ✅ | 2026-07-15 | 2026-07-15 |
