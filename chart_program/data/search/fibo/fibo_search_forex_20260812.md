## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Pattern date | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GBPUSD | short | 3p_steep_23_6_zone | none |  | 2026-01-27->2026-06-24 | 106/1 (5.53:1) |  | 0 |  76.2% | [📈](https://stooq.pl/q/a2/?s=gbpusd&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c GBPUSD --fibo-lines 5 --fibo-anchor-start 2026-01-27 --fibo-anchor-end 2026-06-24 --fibo-right | ✅ | 2026-08-12 | 2026-08-12 |
| EURJPY | short | 3p_steep_23_6_zone | none |  | 2026-04-17->2026-08-03 | 76/1 (5.01:1) |  | 0 |  67.4% | [📈](https://stooq.pl/q/a2/?s=eurjpy&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c EURJPY --fibo-lines 5 --fibo-anchor-start 2026-04-17 --fibo-anchor-end 2026-08-03 --fibo-right | ✅ | 2026-08-12 | 2026-08-12 |
| USDCAD | long | reached_23_6_waiting_for_61_8 | none |  | 2026-05-01->2026-06-24 | 38/35 (1.09:1) |  | 0 |  56.1% | [📈](https://stooq.pl/q/a2/?s=usdcad&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c USDCAD --fibo-lines 5 --fibo-anchor-start 2026-05-01 --fibo-anchor-end 2026-06-24 --fibo-right | ✅ | 2026-08-12 | 2026-08-12 |
| EURPLN | long | reached_23_6_waiting_for_61_8 | none |  | 2026-05-29->2026-07-10 | 30/23 (1.30:1) |  | 0 |  36.6% | [📈](https://stooq.pl/q/a2/?s=eurpln&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c EURPLN --fibo-lines 5 --fibo-anchor-start 2026-05-29 --fibo-anchor-end 2026-07-10 --fibo-right | ✅ | 2026-08-12 | 2026-08-12 |
| EURGBP | short | reached_23_6_waiting_for_61_8 | none |  | 2026-06-22->2026-07-15 | 17/20 (0.85:1) |  | 0 |  27.9% | [📈](https://stooq.pl/q/a2/?s=eurgbp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c EURGBP --fibo-lines 5 --fibo-anchor-start 2026-06-22 --fibo-anchor-end 2026-07-15 --fibo-right | ✅ | 2026-08-12 | 2026-08-12 |
## WYNIKI FIBO #2 (valid pattern up to 2 weeks)

| Ticker | Dir | Pattern | Pattern date | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| USDPLN | long | bullish_harami | 2026-08-10 | 2026-06-16->2026-07-23 | 27/11 (2.45:1) | 2026-08-07 | - | [📈](https://stooq.pl/q/a2/?s=usdpln&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c USDPLN --fibo-lines 5 --fibo-anchor-start 2026-06-16 --fibo-anchor-end 2026-07-23 --fibo-right --scanner-pattern-date 2026-08-10 --scanner-pattern-name bullish_harami | ✅ | 2026-08-12 | 2026-08-12 |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| USDCAD | ⏳ unbroken | 2026-06-15->2026-08-12 | 43 | 2.0 | 2026-07-06@1.42387->2026-07-28@1.41291 | 2026-06-15@1.39508->2026-08-07@1.39261 | 2 | 2 | 2.13% | 0.93% | mild | - | - | 50.22 | - | [📈](https://stooq.pl/q/a2/?s=usdcad&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c USDCAD --wedge-lines --wedge-upper-start 2026-07-06,1.42387 --wedge-upper-end 2026-07-28,1.41291 --wedge-lower-start 2026-06-15,1.39508 --wedge-lower-end 2026-08-07,1.39261 --wedge-right | ✅ | 2026-08-12 | 2026-08-12 |
