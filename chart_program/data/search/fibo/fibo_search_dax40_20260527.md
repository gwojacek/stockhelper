## WYNIKI FIBO #1 (status waiting 23.6->61.8, bez starych valid_reversal)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BAYN.DE | long | reached_23_6_waiting_for_61_8 | none | 2025-11-07->2026-02-17 | 67/26 (2.58:1) |  | 366300597 |  62.2% | https://stooq.pl/q/a2/?s=bayn.de&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c BAYN.DE --fibo-lines 5 --fibo-anchor-start 2025-11-07 --fibo-anchor-end 2026-02-17 --fibo-right |
| BNR.DE | long | reached_23_6_waiting_for_61_8 | none | 2026-03-09->2026-05-04 | 37/15 (2.47:1) |  | 90540359 |  25.5% | https://stooq.pl/q/a2/?s=bnr.de&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c BNR.DE --fibo-lines 5 --fibo-anchor-start 2026-03-09 --fibo-anchor-end 2026-05-04 --fibo-right |
## WYNIKI FIBO #2 (valid formation, last 4 months)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MRK.DE | long | bullish_engulfing | 2026-03-23->2026-04-21 | 19/5 (3.80:1) | 2026-04-28 | 187751063 | https://stooq.pl/q/a2/?s=mrk.de&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c MRK.DE --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-04-21 --fibo-right |
