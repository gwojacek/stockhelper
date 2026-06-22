## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| US100 | long | 🚀 3p_steep_incline | 2026-03-30->2026-06-03 | 45/1 (34.68:1) | - | 310739448542867 | [📈](https://stooq.pl/q/a2/?s=%5Endx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c US100 --fibo-lines 5 --fibo-anchor-start 2026-03-30 --fibo-anchor-end 2026-06-03 --fibo-right | ❌ | 2026-06-18 | 2026-06-22 |
| ITA40 | long | 🚀 3p_steep_incline | 2026-03-23->2026-06-19 | 61/1 (27.81:1) | - | 19929943994250 | [📈](https://stooq.pl/q/a2/?s=%5Efmib&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c ITA40 --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-06-19 --fibo-right | ✅ | 2026-06-22 | 2026-06-22 |
## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BRACOMP | long | reached_23_6_waiting_for_61_8 | none | 2025-10-10->2026-04-14 | 124/25 (4.96:1) |  | 1284095994540 |  74.5% | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --fibo-lines 5 --fibo-anchor-start 2025-10-10 --fibo-anchor-end 2026-04-14 --fibo-right | ❌ | 2026-06-19 | 2026-06-22 |
## WYNIKI FIBO #2 (valid pattern >5 days, last month)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FRA40 | ⏳ unbroken | 2026-02-26->2026-06-22 | 80 | 3.8 | 2026-02-26@8642.23047->2026-06-15@8506.65039 | 2026-06-01@8101.1499->2026-06-10@8113.0 | 3 | 2 | 5.05% | 4.42% | mild | - | - | 69.68 | 592877021773 | [📈](https://stooq.pl/q/a2/?s=%5Ecac&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c FRA40 --wedge-lines --wedge-upper-start 2026-02-26,8642.23047 --wedge-upper-end 2026-06-15,8506.65039 --wedge-lower-start 2026-06-01,8101.1499 --wedge-lower-end 2026-06-10,8113.0 --wedge-right | ✅ | 2026-06-22 | 2026-06-22 |
