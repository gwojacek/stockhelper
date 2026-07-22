## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ITA40 | long | 🚀 3p_steep_incline | 2026-03-23->2026-07-07 | 73/1 (27.89:1) | - | 11615262894250 | [📈](https://stooq.pl/q/a2/?s=%5Efmib&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c ITA40 --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-07-07 --fibo-right | ✅ | 2026-07-20 | 2026-07-20 |
## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HK.CASH | short | reached_23_6_waiting_for_61_8 | none | 2026-01-29->2026-06-26 | 97/15 (6.47:1) |  | 78074428031426 |  62.3% | [📈](https://stooq.pl/q/a2/?s=%5Ehsi&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c HK.CASH --fibo-lines 5 --fibo-anchor-start 2026-01-29 --fibo-anchor-end 2026-06-26 --fibo-right | ✅ | 2026-07-20 | 2026-07-20 |
| BRACOMP | long | reached_23_6_waiting_for_61_8 | none | 2025-10-10->2026-04-14 | 124/26 (4.77:1) |  | 1101411609930 |  51.4% | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --fibo-lines 5 --fibo-anchor-start 2025-10-10 --fibo-anchor-end 2026-04-14 --fibo-right | ✅ | 2026-07-20 | 2026-07-20 |
## WYNIKI FIBO #2 (valid pattern up to 2 weeks)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| US100 | 🚀 breakout | 2026-04-30->2026-07-20 | 55 | 2.6 | 2026-06-22@30642.57031->2026-06-30@30328.78906 | 2026-04-30@27029.41016->2026-06-09@28196.90039 | 2 | 3 | 7.30% | 0.99% | strong | 2026-07-16 | short | 441.35 | 203448973123410 | [📈](https://stooq.pl/q/a2/?s=%5Endx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c US100 --wedge-lines --wedge-upper-start 2026-06-22,30642.57031 --wedge-upper-end 2026-06-30,30328.78906 --wedge-lower-start 2026-04-30,27029.41016 --wedge-lower-end 2026-06-09,28196.90039 --wedge-right | ✅ | 2026-07-20 | 2026-07-20 |
| MEXCOMP | ⏳ unbroken | 2025-12-17->2026-07-20 | 147 | 7.0 | 2026-02-12@72111.40625->2026-02-27@71890.34375 | 2025-12-17@62461.05859->2026-06-09@64666.23828 | 3 | 2 | 13.43% | 7.11% | mild | - | - | 282.72 | 7873346017640 | [📈](https://stooq.pl/q/a2/?s=%5Eipc&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c MEXCOMP --wedge-lines --wedge-upper-start 2026-02-12,72111.40625 --wedge-upper-end 2026-02-27,71890.34375 --wedge-lower-start 2025-12-17,62461.05859 --wedge-lower-end 2026-06-09,64666.23828 --wedge-right | ✅ | 2026-07-20 | 2026-07-20 |
| BRACOMP | ⏳ unbroken | 2026-04-17->2026-07-20 | 64 | 3.0 | 2026-04-17@198666.0->2026-07-13@178154.0 | 2026-07-01@169666.0->2026-07-08@169972.0 | 2 | 2 | 6.51% | 3.41% | strong | - | - | 93.69 | 1101411609930 | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --wedge-lines --wedge-upper-start 2026-04-17,198666.0 --wedge-upper-end 2026-07-13,178154.0 --wedge-lower-start 2026-07-01,169666.0 --wedge-lower-end 2026-07-08,169972.0 --wedge-right | ✅ | 2026-07-20 | 2026-07-20 |
