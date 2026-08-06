## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Pattern date | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURGBP | short | reached_23_6_waiting_for_61_8 | none |  | 2026-06-22->2026-07-15 | 17/16 (1.06:1) |  | 0 |  78.1% | [📈](https://stooq.pl/q/a2/?s=eurgbp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c EURGBP --fibo-lines 5 --fibo-anchor-start 2026-06-22 --fibo-anchor-end 2026-07-15 --fibo-right | ✅ | 2026-08-06 | 2026-08-06 |
| USDPLN | long | reached_23_6_waiting_for_61_8 | none |  | 2026-06-16->2026-07-23 | 27/10 (2.70:1) |  | 0 |  73.4% | [📈](https://stooq.pl/q/a2/?s=usdpln&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c USDPLN --fibo-lines 5 --fibo-anchor-start 2026-06-16 --fibo-anchor-end 2026-07-23 --fibo-right | ✅ | 2026-08-06 | 2026-08-06 |
| GBPUSD | short | 3p_steep_23_6_zone | none |  | 2026-01-27->2026-06-24 | 106/1 (5.53:1) |  | 0 |  54.0% | [📈](https://stooq.pl/q/a2/?s=gbpusd&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c GBPUSD --fibo-lines 5 --fibo-anchor-start 2026-01-27 --fibo-anchor-end 2026-06-24 --fibo-right | ✅ | 2026-08-06 | 2026-08-06 |
| EURPLN | long | reached_23_6_waiting_for_61_8 | none |  | 2026-05-29->2026-07-10 | 30/19 (1.58:1) |  | 0 |  40.7% | [📈](https://stooq.pl/q/a2/?s=eurpln&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c EURPLN --fibo-lines 5 --fibo-anchor-start 2026-05-29 --fibo-anchor-end 2026-07-10 --fibo-right | ✅ | 2026-08-06 | 2026-08-06 |
| USDCAD | long | reached_23_6_waiting_for_61_8 | none |  | 2026-05-01->2026-06-24 | 38/31 (1.23:1) |  | 0 |  25.9% | [📈](https://stooq.pl/q/a2/?s=usdcad&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c USDCAD --fibo-lines 5 --fibo-anchor-start 2026-05-01 --fibo-anchor-end 2026-06-24 --fibo-right | ✅ | 2026-08-06 | 2026-08-06 |
| EURJPY | short | 3p_steep_23_6_zone | none |  | 2026-04-17->2026-08-03 | 76/1 (5.05:1) |  | 0 |  23.4% | [📈](https://stooq.pl/q/a2/?s=eurjpy&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c EURJPY --fibo-lines 5 --fibo-anchor-start 2026-04-17 --fibo-anchor-end 2026-08-03 --fibo-right | ✅ | 2026-08-06 | 2026-08-06 |
## WYNIKI FIBO #2 (valid pattern up to 2 weeks)

| Ticker | Dir | Pattern | Pattern date | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GBPUSD | ⏳ unbroken | 2025-11-05->2026-08-06 | 195 | 9.3 | 2026-01-27@1.38598->2026-07-15@1.35582 | 2025-11-05@1.30105->2026-06-19@1.31633 | 4 | 2 | 5.91% | 2.40% | mild | - | - | 380.85 | - | [📈](https://stooq.pl/q/a2/?s=gbpusd&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c GBPUSD --wedge-lines --wedge-upper-start 2026-01-27,1.38598 --wedge-upper-end 2026-07-15,1.35582 --wedge-lower-start 2025-11-05,1.30105 --wedge-lower-end 2026-06-19,1.31633 --wedge-right | ✅ | 2026-08-06 | 2026-08-06 |
| USDCAD | ⏳ unbroken | 2026-06-05->2026-08-06 | 45 | 2.1 | 2026-07-06@1.42387->2026-07-28@1.41291 | 2026-06-05@1.38682->2026-07-30@1.39911 | 2 | 2 | 2.17% | 0.53% | mild | - | - | 63.91 | - | [📈](https://stooq.pl/q/a2/?s=usdcad&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c USDCAD --wedge-lines --wedge-upper-start 2026-07-06,1.42387 --wedge-upper-end 2026-07-28,1.41291 --wedge-lower-start 2026-06-05,1.38682 --wedge-lower-end 2026-07-30,1.39911 --wedge-right | ✅ | 2026-08-06 | 2026-08-06 |
