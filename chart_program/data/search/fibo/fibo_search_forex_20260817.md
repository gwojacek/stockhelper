## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| USDPLN | long | ↩️ returned_above_23_6 | 2026-05-07->2026-06-24 | 34/8 (4.25:1) | - | - | [📈](https://stooq.pl/q/a2/?s=usdpln&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c USDPLN --fibo-lines 5 --fibo-anchor-start 2026-05-07 --fibo-anchor-end 2026-06-24 --fibo-right | ✅ | 2026-08-17 | 2026-08-17 |
## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Pattern date | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AUDUSD | short | 🟡 touched_61_8_no_pattern | none |  | 2026-05-13->2026-06-30 | 34/34 (1.00:1) | 2026-08-17 | 0 | 102.9% | [📈](https://stooq.pl/q/a2/?s=audusd&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c AUDUSD --fibo-lines 5 --fibo-anchor-start 2026-05-13 --fibo-anchor-end 2026-06-30 --fibo-right | ✅ | 2026-08-17 | 2026-08-17 |
| USDCAD | long | reached_23_6_waiting_for_61_8 | none |  | 2026-05-01->2026-06-24 | 38/38 (1.00:1) |  | 0 |  84.7% | [📈](https://stooq.pl/q/a2/?s=usdcad&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c USDCAD --fibo-lines 5 --fibo-anchor-start 2026-05-01 --fibo-anchor-end 2026-06-24 --fibo-right | ✅ | 2026-08-17 | 2026-08-17 |
| EURGBP | short | reached_23_6_waiting_for_61_8 | none |  | 2026-06-22->2026-07-15 | 17/23 (0.74:1) |  | 0 |  53.8% | [📈](https://stooq.pl/q/a2/?s=eurgbp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c EURGBP --fibo-lines 5 --fibo-anchor-start 2026-06-22 --fibo-anchor-end 2026-07-15 --fibo-right | ✅ | 2026-08-17 | 2026-08-17 |
| EURPLN | long | reached_23_6_waiting_for_61_8 | none |  | 2026-05-29->2026-07-10 | 30/26 (1.15:1) |  | 0 |  26.3% | [📈](https://stooq.pl/q/a2/?s=eurpln&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c EURPLN --fibo-lines 5 --fibo-anchor-start 2026-05-29 --fibo-anchor-end 2026-07-10 --fibo-right | ✅ | 2026-08-17 | 2026-08-17 |
## WYNIKI FIBO #2 (valid pattern up to 2 weeks)

| Ticker | Dir | Pattern | Pattern date | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| USDPLN | long | bullish_harami | 2026-08-10 | 2026-06-16->2026-07-23 | 27/11 (2.45:1) | 2026-08-07 | - | [📈](https://stooq.pl/q/a2/?s=usdpln&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c USDPLN --fibo-lines 5 --fibo-anchor-start 2026-06-16 --fibo-anchor-end 2026-07-23 --fibo-right --scanner-pattern-date 2026-08-10 --scanner-pattern-name bullish_harami | ✅ | 2026-08-17 | 2026-08-17 |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURGBP | ⏳ unbroken | 2026-06-22->2026-08-17 | 41 | 2.0 | 2026-06-22@0.86874->2026-08-05@0.85841 | 2026-07-31@0.85426->2026-08-10@0.85366 | 3 | 2 | 0.60% | 0.31% | mild | - | - | 68.18 | - | [📈](https://stooq.pl/q/a2/?s=eurgbp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c EURGBP --wedge-lines --wedge-upper-start 2026-06-22,0.86874 --wedge-upper-end 2026-08-05,0.85841 --wedge-lower-start 2026-07-31,0.85426 --wedge-lower-end 2026-08-10,0.85366 --wedge-right | ✅ | 2026-08-17 | 2026-08-17 |
