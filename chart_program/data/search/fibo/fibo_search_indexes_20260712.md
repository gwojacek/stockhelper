## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| JP225 | long | 🚀 3p_steep_incline | 2025-07-14->2026-06-22 | 227/1 (85.37:1) | - | 11071834890078 | [📈](https://stooq.pl/q/a2/?s=%5Enkx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c JP225 --fibo-lines 5 --fibo-anchor-start 2025-07-14 --fibo-anchor-end 2026-06-22 --fibo-right | ✅ | 2026-07-10 | 2026-07-10 |
| ITA40 | long | 🚀 3p_steep_incline | 2026-03-23->2026-07-07 | 73/1 (27.89:1) | - | 12822841244410 | [📈](https://stooq.pl/q/a2/?s=%5Efmib&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c ITA40 --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-07-07 --fibo-right | ✅ | 2026-07-10 | 2026-07-10 |
## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BRACOMP | long | reached_23_6_waiting_for_61_8 | none | 2025-10-10->2026-04-14 | 124/20 (6.20:1) |  | 1119535878090 |  33.4% | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --fibo-lines 5 --fibo-anchor-start 2025-10-10 --fibo-anchor-end 2026-04-14 --fibo-right | ✅ | 2026-07-10 | 2026-07-10 |
| BRACOMP | short | reached_23_6_waiting_for_61_8 | none | 2026-04-14->2026-06-19 | 45/15 (3.00:1) |  | 1119535878090 |  22.5% | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --fibo-lines 5 --fibo-anchor-start 2026-04-14 --fibo-anchor-end 2026-06-19 --fibo-right | ✅ | 2026-07-10 | 2026-07-10 |
## WYNIKI FIBO #2 (valid pattern up to 2 weeks)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MEXCOMP | ⏳ unbroken | 2025-12-17->2026-07-10 | 141 | 6.7 | 2026-02-12@72111.40625->2026-02-27@71890.34375 | 2025-12-17@62461.05859->2026-06-09@64666.23828 | 3 | 2 | 13.44% | 7.46% | mild | - | - | 274.47 | 8078365084670 | [📈](https://stooq.pl/q/a2/?s=%5Eipc&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c MEXCOMP --wedge-lines --wedge-upper-start 2026-02-12,72111.40625 --wedge-upper-end 2026-02-27,71890.34375 --wedge-lower-start 2025-12-17,62461.05859 --wedge-lower-end 2026-06-09,64666.23828 --wedge-right | ✅ | 2026-07-10 | 2026-07-10 |
| AU200.CASH | ⏳ unbroken | 2026-03-03->2026-07-10 | 91 | 4.3 | 2026-03-03@9200.90039->2026-06-18@8983.7998 | 2026-05-20@8485.2002->2026-06-09@8490.90039 | 2 | 2 | 6.33% | 4.95% | mild | - | - | 102.77 | 5799053026 | [📈](https://stooq.pl/q/a2/?s=%5Eaor&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c AU200.CASH --wedge-lines --wedge-upper-start 2026-03-03,9200.90039 --wedge-upper-end 2026-06-18,8983.7998 --wedge-lower-start 2026-05-20,8485.2002 --wedge-lower-end 2026-06-09,8490.90039 --wedge-right | ✅ | 2026-07-10 | 2026-07-10 |
| US100 | ⏳ unbroken | 2026-05-12->2026-07-10 | 41 | 2.0 | 2026-06-03@30762.19922->2026-06-15@30587.16016 | 2026-05-12@28628.64062->2026-05-19@28567.16016 | 3 | 3 | 7.77% | 6.97% | mild | - | - | 58.37 | 275596634429482 | [📈](https://stooq.pl/q/a2/?s=%5Endx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c US100 --wedge-lines --wedge-upper-start 2026-06-03,30762.19922 --wedge-upper-end 2026-06-15,30587.16016 --wedge-lower-start 2026-05-12,28628.64062 --wedge-lower-end 2026-05-19,28567.16016 --wedge-right | ✅ | 2026-07-10 | 2026-07-10 |
