## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| USDCAD | short | 🚀 3p_steep_incline | 2026-06-24->2026-08-21 | 42/1 (3.83:1) | - | - | [📈](https://stooq.pl/q/a2/?s=usdcad&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c USDCAD --fibo-lines 5 --fibo-anchor-start 2026-06-24 --fibo-anchor-end 2026-08-21 --fibo-right | ✅ | 2026-08-22 | 2026-08-21 |
## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Pattern date | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURGBP | short | reached_23_6_waiting_for_61_8 | none |  | 2026-06-22->2026-07-15 | 17/27 (0.63:1) |  | 0 |  57.6% | [📈](https://stooq.pl/q/a2/?s=eurgbp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c EURGBP --fibo-lines 5 --fibo-anchor-start 2026-06-22 --fibo-anchor-end 2026-07-15 --fibo-right | ✅ | 2026-08-21 | 2026-08-21 |
| EURPLN | long | reached_23_6_waiting_for_61_8 | none |  | 2026-05-29->2026-07-10 | 30/25 (1.20:1) |  | 0 |  26.1% | [📈](https://stooq.pl/q/a2/?s=eurpln&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c EURPLN --fibo-lines 5 --fibo-anchor-start 2026-05-29 --fibo-anchor-end 2026-07-10 --fibo-right | ✅ | 2026-08-21 | 2026-08-21 |
## WYNIKI FIBO #2 (valid pattern up to 2 weeks)

| Ticker | Dir | Pattern | Pattern date | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURGBP | ⏳ unbroken | 2026-05-18->2026-08-21 | 70 | 3.3 | 2026-05-18@0.873->2026-06-18@0.86845 | 2026-07-31@0.85426->2026-08-10@0.85366 | 2 | 2 | 0.94% | 0.77% | mild | - | - | 49.83 | - | [📈](https://stooq.pl/q/a2/?s=eurgbp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c EURGBP --wedge-lines --wedge-upper-start 2026-05-18,0.873 --wedge-upper-end 2026-06-18,0.86845 --wedge-lower-start 2026-07-31,0.85426 --wedge-lower-end 2026-08-10,0.85366 --wedge-right | ✅ | 2026-08-21 | 2026-08-21 |
