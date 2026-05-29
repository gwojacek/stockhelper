## WYNIKI FIBO #1 (status waiting 23.6->61.8, bez starych valid_reversal)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MUR | long | reached_23_6_waiting_for_61_8 | none | 2026-03-25->2026-04-16 | 14/11 (1.27:1) |  | 1287417 |  10.8% | https://stooq.pl/q/a2/?s=mur&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c MUR --fibo-lines 5 --fibo-anchor-start 2026-03-25 --fibo-anchor-end 2026-04-16 --fibo-right |
| PZU | long | reached_23_6_waiting_for_61_8 | none | 2025-09-26->2026-02-04 | 86/35 (2.46:1) |  | 85757731 |  38.6% | https://stooq.pl/q/a2/?s=pzu&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c PZU --fibo-lines 5 --fibo-anchor-start 2025-09-26 --fibo-anchor-end 2026-02-04 --fibo-right |
| UNT | long | reached_23_6_waiting_for_61_8 | none | 2026-03-30->2026-05-13 | 29/8 (3.62:1) |  | 1097061 |  16.1% | https://stooq.pl/q/a2/?s=unt&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c UNT --fibo-lines 5 --fibo-anchor-start 2026-03-30 --fibo-anchor-end 2026-05-13 --fibo-right |
| SNT | long | reached_23_6_waiting_for_61_8 | none | 2026-03-23->2026-04-14 | 14/18 (0.78:1) |  | 5690578 |  25.8% | https://stooq.pl/q/a2/?s=snt&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c SNT.WA --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-04-14 --fibo-right |
| SCW | long | reached_23_6_waiting_for_61_8 | none | 2025-11-21->2026-04-20 | 98/24 (4.08:1) |  | 5612320 |  10.5% | https://stooq.pl/q/a2/?s=scw&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c SCW --fibo-lines 5 --fibo-anchor-start 2025-11-21 --fibo-anchor-end 2026-04-20 --fibo-right |
## WYNIKI FIBO #2 (valid formation, last 4 months)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ATT | long | hammer | 2026-03-23->2026-05-06 | 29/3 (9.67:1) | 2026-05-11 | 9951619 | https://stooq.pl/q/a2/?s=att&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c ATT.WA --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-05-06 --fibo-right |
| TPE | long | bullish_harami | 2026-03-23->2026-04-10 | 12/13 (0.92:1) | 2026-04-29 | 28584213 | https://stooq.pl/q/a2/?s=tpe&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c TPE --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-04-10 --fibo-right |
