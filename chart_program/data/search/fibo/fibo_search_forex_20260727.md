## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| USDPLN | long | ↩️ returned_above_23_6 | 2026-05-07->2026-06-24 | 34/8 (4.25:1) | - | - | [📈](https://stooq.pl/q/a2/?s=usdpln&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c USDPLN --fibo-lines 5 --fibo-anchor-start 2026-05-07 --fibo-anchor-end 2026-06-24 --fibo-right | ❌ | 2026-07-20 | 2026-07-27 |
| USDJPY | long | ↩️ returned_above_23_6 | 2026-05-14->2026-07-01 | 34/13 (2.62:1) | - | - | [📈](https://stooq.pl/q/a2/?s=usdjpy&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c USDJPY --fibo-lines 5 --fibo-anchor-start 2026-05-14 --fibo-anchor-end 2026-07-01 --fibo-right | ❌ | 2026-07-20 | 2026-07-27 |
## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| USDCAD | long | reached_23_6_waiting_for_61_8 | none | 2026-05-01->2026-06-24 | 38/18 (2.11:1) |  | 0 |  20.0% | [📈](https://stooq.pl/q/a2/?s=usdcad&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c USDCAD --fibo-lines 5 --fibo-anchor-start 2026-05-01 --fibo-anchor-end 2026-06-24 --fibo-right | ❌ | 2026-07-20 | 2026-07-27 |
## WYNIKI FIBO #2 (valid pattern up to 2 weeks)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURJPY | 🚀 breakout | 2026-04-30->2026-07-20 | 58 | 2.8 | 2026-04-30@187.539->2026-06-17@186.318 | 2026-05-06@182.059->2026-06-24@183.172 | 3 | 2 | 2.88% | 0.94% | mild | 2026-07-15 | long | 351.30 | - | [📈](https://stooq.pl/q/a2/?s=eurjpy&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c EURJPY --wedge-lines --wedge-upper-start 2026-04-30,187.539 --wedge-upper-end 2026-06-17,186.318 --wedge-lower-start 2026-05-06,182.059 --wedge-lower-end 2026-06-24,183.172 --wedge-right | ❌ | 2026-07-20 | 2026-07-27 |
