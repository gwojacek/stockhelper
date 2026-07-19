## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GBPUSD | short | reached_23_6_waiting_for_61_8 | none | 2026-01-29->2026-06-24 | 106/19 (5.58:1) |  | 0 |  53.3% | [📈](https://stooq.pl/q/a2/?s=gbpusd&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c GBPUSD --fibo-lines 5 --fibo-anchor-start 2026-01-29 --fibo-anchor-end 2026-06-24 --fibo-right | ✅ | 2026-07-19 | 2026-07-17 |
| AUDUSD | short | reached_23_6_waiting_for_61_8 | none | 2026-05-01->2026-06-30 | 44/17 (2.59:1) |  | 0 |  24.4% | [📈](https://stooq.pl/q/a2/?s=audusd&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c AUDUSD --fibo-lines 5 --fibo-anchor-start 2026-05-01 --fibo-anchor-end 2026-06-30 --fibo-right | ✅ | 2026-07-19 | 2026-07-17 |
## WYNIKI FIBO #2 (valid pattern up to 2 weeks)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURJPY | 🚀 breakout | 2026-04-30->2026-07-17 | 57 | 2.7 | 2026-04-30@187.554->2026-06-17@186.30499 | 2026-05-06@182.063->2026-06-24@183.173 | 3 | 2 | 2.88% | 0.96% | mild | 2026-07-16 | long | 429.32 | 0 | [📈](https://stooq.pl/q/a2/?s=eurjpy&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c EURJPY --wedge-lines --wedge-upper-start 2026-04-30,187.554 --wedge-upper-end 2026-06-17,186.30499 --wedge-lower-start 2026-05-06,182.063 --wedge-lower-end 2026-06-24,183.173 --wedge-right | ✅ | 2026-07-17 | 2026-07-17 |
| EURGBP | ⏳ unbroken | 2026-05-11->2026-07-19 | 54 | 2.6 | 2026-06-26@0.86502->2026-07-14@0.8544 | 2026-05-11@0.8628->2026-07-16@0.8468 | 3 | 2 | 1.58% | 0.53% | mild | - | - | 72.02 | 0 | [📈](https://stooq.pl/q/a2/?s=eurgbp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c EURGBP --wedge-lines --wedge-upper-start 2026-06-26,0.86502 --wedge-upper-end 2026-07-14,0.8544 --wedge-lower-start 2026-05-11,0.8628 --wedge-lower-end 2026-07-16,0.8468 --wedge-right | ✅ | 2026-07-19 | 2026-07-17 |
