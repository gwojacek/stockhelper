## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| US100 | long | 🚀 3p_steep_incline | 2026-03-30->2026-06-03 | 45/1 (34.68:1) | - | 273186454268646 | [📈](https://stooq.pl/q/a2/?s=%5Endx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c US100 --fibo-lines 5 --fibo-anchor-start 2026-03-30 --fibo-anchor-end 2026-06-03 --fibo-right | ✅ | 2026-06-15 | 2026-06-15 |
| ITA40 | long | 🚀 3p_steep_incline | 2026-03-23->2026-06-15 | 57/1 (25.77:1) | - | 18299883731430 | [📈](https://stooq.pl/q/a2/?s=%5Efmib&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c ITA40 --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-06-15 --fibo-right | ✅ | 2026-06-15 | 2026-06-15 |
## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BRACOMP | long | reached_23_6_waiting_for_61_8 | none | 2025-10-10->2026-04-14 | 124/26 (4.77:1) |  | 1333498866440 |  61.6% | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --fibo-lines 5 --fibo-anchor-start 2025-10-10 --fibo-anchor-end 2026-04-14 --fibo-right | ✅ | 2026-06-15 | 2026-06-15 |
## WYNIKI FIBO #2 (valid pattern >5 days, last month)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FRA40 | long | bullish_piercing_line | 2026-03-23->2026-04-17 | 17/20 (0.85:1) | 2026-05-18 | 454681581026 | [📈](https://stooq.pl/q/a2/?s=%5Ecac&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c FRA40 --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-04-17 --fibo-right | ✅ | 2026-06-15 | 2026-06-15 |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CHN.CASH | ⏳ unbroken | 2026-04-02->2026-06-15 | 48 | 2.3 | 2026-02-10@9311.37988->2026-05-07@8945.55957 | 2026-04-02@8380.57031->2026-06-11@8159.12988 | 4 | 2 | 8.42% | 7.45% | mild | - | - | 25.17 | 21346863850 | [📈](https://stooq.pl/q/a2/?s=0el.c&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c CHN.CASH --wedge-lines --wedge-upper-start 2026-02-10,9311.37988 --wedge-upper-end 2026-05-07,8945.55957 --wedge-lower-start 2026-04-02,8380.57031 --wedge-lower-end 2026-06-11,8159.12988 --wedge-right | ✅ | 2026-06-15 | 2026-06-15 |
| UK100 | ⏳ unbroken | 2026-05-12->2026-06-15 | 24 | 1.1 | 2026-04-20@10683.7002->2026-05-26@10557.2002 | 2026-05-12@10152.09961->2026-06-10@10127.59961 | 3 | 2 | 4.34% | 3.45% | mild | - | - | 11.53 | 7485620329858 | [📈](https://stooq.pl/q/a2/?s=%5Eukx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c UK100 --wedge-lines --wedge-upper-start 2026-04-20,10683.7002 --wedge-upper-end 2026-05-26,10557.2002 --wedge-lower-start 2026-05-12,10152.09961 --wedge-lower-end 2026-06-10,10127.59961 --wedge-right | ✅ | 2026-06-15 | 2026-06-15 |
