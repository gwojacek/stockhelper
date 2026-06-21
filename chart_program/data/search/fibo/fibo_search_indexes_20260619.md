## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| US100 | long | 🚀 3p_steep_incline | 2026-03-30->2026-06-03 | 45/1 (34.68:1) | - | 263116892528405 | [📈](https://stooq.pl/q/a2/?s=%5Endx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c US100 --fibo-lines 5 --fibo-anchor-start 2026-03-30 --fibo-anchor-end 2026-06-03 --fibo-right | ❌ | 2026-06-18 | 2026-06-19 |
| ITA40 | long | 🚀 3p_steep_incline | 2026-03-23->2026-06-19 | 60/1 (27.81:1) | - | 17668387233410 | [📈](https://stooq.pl/q/a2/?s=%5Efmib&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c ITA40 --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-06-19 --fibo-right | ✅ | 2026-06-19 | 2026-06-19 |
## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BRACOMP | long | reached_23_6_waiting_for_61_8 | none | 2025-10-10->2026-04-14 | 124/25 (4.96:1) |  | 1046938695240 |  75.5% | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --fibo-lines 5 --fibo-anchor-start 2025-10-10 --fibo-anchor-end 2026-04-14 --fibo-right | ✅ | 2026-06-19 | 2026-06-19 |
## WYNIKI FIBO #2 (valid pattern >5 days, last month)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AU200.CASH | 🚀 breakout | 2026-03-23->2026-06-19 | 61 | 2.9 | 2026-03-03@9200.90039->2026-04-16@9017.2002 | 2026-03-23@8262.40039->2026-05-20@8485.2002 | 3 | 3 | 9.66% | 1.71% | moderate | 2026-06-12 | long | 465.23 | 5204473272 | [📈](https://stooq.pl/q/a2/?s=%5Eaor&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c AU200.CASH --wedge-lines --wedge-upper-start 2026-03-03,9200.90039 --wedge-upper-end 2026-04-16,9017.2002 --wedge-lower-start 2026-03-23,8262.40039 --wedge-lower-end 2026-05-20,8485.2002 --wedge-right | ✅ | 2026-06-19 | 2026-06-19 |
| CHN.CASH | ⏳ unbroken | 2026-03-30->2026-06-17 | 53 | 2.5 | 2026-01-29@9585.82031->2026-05-12@8957.7998 | 2026-03-30@8286.24023->2026-06-17@8120.33008 | 3 | 2 | 11.40% | 7.36% | mild | - | - | 81.32 | 20424537677 | [📈](https://stooq.pl/q/a2/?s=0el.c&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c CHN.CASH --wedge-lines --wedge-upper-start 2026-01-29,9585.82031 --wedge-upper-end 2026-05-12,8957.7998 --wedge-lower-start 2026-03-30,8286.24023 --wedge-lower-end 2026-06-17,8120.33008 --wedge-right | ❌ | 2026-06-17 | 2026-06-19 |
| HK.CASH | ⏳ unbroken | 2026-05-14->2026-06-17 | 24 | 1.1 | 2026-05-14@26844.80078->2026-06-02@26045.07031 | 2026-04-02@24901.76953->2026-06-11@23999.66992 | 2 | 2 | 10.14% | 5.73% | moderate | - | - | 39.45 | 75912040986367 | [📈](https://stooq.pl/q/a2/?s=%5Ehsi&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c HK.CASH --wedge-lines --wedge-upper-start 2026-05-14,26844.80078 --wedge-upper-end 2026-06-02,26045.07031 --wedge-lower-start 2026-04-02,24901.76953 --wedge-lower-end 2026-06-11,23999.66992 --wedge-right | ❌ | 2026-06-17 | 2026-06-19 |
