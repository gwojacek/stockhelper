## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Saved by user | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Pattern date | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Saved by user | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TXT.WA | long | 🟡 touched_61_8_no_pattern | none |  | 2026-06-08->2026-08-12 | 47/13 (3.62:1) | 2026-08-31 | 5662185 | 136.1% | no | [📈](https://stooq.pl/q/a2/?s=txt.wa&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c TXT.WA --fibo-lines 5 --fibo-anchor-start 2026-06-08 --fibo-anchor-end 2026-08-12 --fibo-right | ✅ | 2026-09-01 | 2026-09-01 |
| SNT.WA | long | 3p_steep_23_6_zone | none |  | 2026-06-01->2026-07-15 | 31/1 (52.06:1) |  | 13958051 |  75.3% | no | [📈](https://stooq.pl/q/a2/?s=snt.wa&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c SNT.WA --fibo-lines 5 --fibo-anchor-start 2026-06-01 --fibo-anchor-end 2026-07-15 --fibo-right | ✅ | 2026-09-01 | 2026-09-01 |
| CRI.WA | long | 3p_steep_23_6_zone | none |  | 2025-12-18->2026-05-29 | 107/1 (271.84:1) |  | 4695119 |  63.2% | no | [📈](https://stooq.pl/q/a2/?s=cri.wa&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c CRI.WA --fibo-lines 5 --fibo-anchor-start 2025-12-18 --fibo-anchor-end 2026-05-29 --fibo-right | ✅ | 2026-09-01 | 2026-09-01 |
## WYNIKI FIBO #2 (valid pattern up to 2 weeks)

| Ticker | Dir | Pattern | Pattern date | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Saved by user | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CDR.WA | long | bullish_harami | 2026-08-28 | 2026-06-26->2026-08-13 | 34/10 (3.40:1) | 2026-08-27 | 119080575 | no | [📈](https://stooq.pl/q/a2/?s=cdr.wa&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c CDR.WA --fibo-lines 5 --fibo-anchor-start 2026-06-26 --fibo-anchor-end 2026-08-13 --fibo-right --scanner-pattern-date 2026-08-28 --scanner-pattern-name bullish_harami | ✅ | 2026-09-01 | 2026-09-01 |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Saved by user | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SNT.WA | 🚀 breakout | 2026-07-09->2026-09-01 | 39 | 1.9 | 2026-08-06@384.4->2026-08-20@360.2 | 2026-07-09@368.2->2026-07-24@357.2 | 2 | 4 | 11.07% | 3.25% | very strong | 2026-09-01 | short | 726.08 | 13958051 | no | [📈](https://stooq.pl/q/a2/?s=snt.wa&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c SNT.WA --wedge-lines --wedge-upper-start 2026-08-06,384.4 --wedge-upper-end 2026-08-20,360.2 --wedge-lower-start 2026-07-09,368.2 --wedge-lower-end 2026-07-24,357.2 --wedge-right | ✅ | 2026-09-01 | 2026-09-01 |
| CDR.WA | ⏳ unbroken | 2026-04-22->2026-09-01 | 93 | 4.4 | 2026-04-22@297.0->2026-08-13@269.0 | 2026-07-23@225.0->2026-08-27@230.3 | 2 | 2 | 21.04% | 14.27% | strong | - | - | 171.68 | 119080575 | no | [📈](https://stooq.pl/q/a2/?s=cdr.wa&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c CDR.WA --wedge-lines --wedge-upper-start 2026-04-22,297.0 --wedge-upper-end 2026-08-13,269.0 --wedge-lower-start 2026-07-23,225.0 --wedge-lower-end 2026-08-27,230.3 --wedge-right | ✅ | 2026-09-01 | 2026-09-01 |
