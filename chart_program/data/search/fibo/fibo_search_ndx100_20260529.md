## WYNIKI FIBO #1 (status waiting 23.6->61.8, bez starych valid_reversal)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AEP.US | long | reached_23_6_waiting_for_61_8 | none | 2026-01-05->2026-05-05 | 83/16 (5.19:1) |  | 2505649041 |  51.9% | https://stooq.pl/q/a2/?s=aep.us&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c AEP.US --fibo-lines 5 --fibo-anchor-start 2026-01-05 --fibo-anchor-end 2026-05-05 --fibo-right |
| WMT.US | long | reached_23_6_waiting_for_61_8 | none | 2025-11-14->2026-05-19 | 126/6 (21.00:1) |  | 11703823441 |  55.5% | https://stooq.pl/q/a2/?s=wmt.us&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c WMT.US --fibo-lines 5 --fibo-anchor-start 2025-11-14 --fibo-anchor-end 2026-05-19 --fibo-right |
| TTWO.US | long | reached_23_6_waiting_for_61_8 | none | 2026-03-27->2026-05-22 | 39/3 (13.00:1) |  | 2677065810 |  66.7% | https://stooq.pl/q/a2/?s=ttwo.us&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c TTWO.US --fibo-lines 5 --fibo-anchor-start 2026-03-27 --fibo-anchor-end 2026-05-22 --fibo-right |
| NVDA.US | long | reached_23_6_waiting_for_61_8 | none | 2026-03-30->2026-05-14 | 32/9 (3.56:1) |  | 136736432639 |  19.0% | https://stooq.pl/q/a2/?s=nvda.us&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c NVDA.US --fibo-lines 5 --fibo-anchor-start 2026-03-30 --fibo-anchor-end 2026-05-14 --fibo-right |
| COST.US | long | reached_23_6_waiting_for_61_8 | none | 2025-12-16->2026-05-19 | 105/6 (17.50:1) |  | 8743305198 |  43.3% | https://stooq.pl/q/a2/?s=cost.us&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c COST.US --fibo-lines 5 --fibo-anchor-start 2025-12-16 --fibo-anchor-end 2026-05-19 --fibo-right |
## WYNIKI FIBO #2 (valid formation, last 4 months)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MPWR.US | long | bullish_engulfing | 2025-12-31->2026-02-25 | 37/7 (5.29:1) | 2026-03-06 | 3641417744 | https://stooq.pl/q/a2/?s=mpwr.us&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c MPWR.US --fibo-lines 5 --fibo-anchor-start 2025-12-31 --fibo-anchor-end 2026-02-25 --fibo-right |
| NVDA.US | long | bullish_engulfing | 2026-02-05->2026-02-25 | 13/2 (6.50:1) | 2026-02-27 | 136736432639 | https://stooq.pl/q/a2/?s=nvda.us&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c NVDA.US --fibo-lines 5 --fibo-anchor-start 2026-02-05 --fibo-anchor-end 2026-02-25 --fibo-right |
