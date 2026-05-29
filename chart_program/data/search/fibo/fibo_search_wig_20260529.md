## WYNIKI FIBO #1 (status waiting 23.6->61.8, bez starych valid_reversal)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TRN | long | reached_23_6_waiting_for_61_8 | none | 2026-01-30->2026-05-21 | 76/5 (15.20:1) |  | 1629651 |  89.5% | https://stooq.pl/q/a2/?s=trn&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c TRN --fibo-lines 5 --fibo-anchor-start 2026-01-30 --fibo-anchor-end 2026-05-21 --fibo-right |
| ELT | long | reached_23_6_waiting_for_61_8 | none | 2026-04-16->2026-05-21 | 24/5 (4.80:1) |  | 1969827 |  22.2% | https://stooq.pl/q/a2/?s=elt&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c ELT --fibo-lines 5 --fibo-anchor-start 2026-04-16 --fibo-anchor-end 2026-05-21 --fibo-right |
| MRC | long | reached_23_6_waiting_for_61_8 | none | 2026-03-27->2026-05-25 | 38/3 (12.67:1) |  | 1317649 |  20.5% | https://stooq.pl/q/a2/?s=mrc&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c MRC --fibo-lines 5 --fibo-anchor-start 2026-03-27 --fibo-anchor-end 2026-05-25 --fibo-right |
| SNT | long | reached_23_6_waiting_for_61_8 | none | 2026-03-23->2026-04-14 | 14/16 (0.88:1) |  | 6342648 |  72.9% | https://stooq.pl/q/a2/?s=snt&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c SNT.WA --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-04-14 --fibo-right |
| UNT | long | reached_23_6_waiting_for_61_8 | none | 2026-03-30->2026-05-13 | 29/11 (2.64:1) |  | 720845 |  52.7% | https://stooq.pl/q/a2/?s=unt&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c UNT --fibo-lines 5 --fibo-anchor-start 2026-03-30 --fibo-anchor-end 2026-05-13 --fibo-right |
| CEZ | long | reached_23_6_waiting_for_61_8 | none | 2026-03-02->2026-05-21 | 55/5 (11.00:1) |  | 1090522 |   5.5% | https://stooq.pl/q/a2/?s=cez&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c CEZ --fibo-lines 5 --fibo-anchor-start 2026-03-02 --fibo-anchor-end 2026-05-21 --fibo-right |
| SCW | long | reached_23_6_waiting_for_61_8 | none | 2025-11-21->2026-04-20 | 98/27 (3.63:1) |  | 6305472 |  41.3% | https://stooq.pl/q/a2/?s=scw&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c SCW --fibo-lines 5 --fibo-anchor-start 2025-11-21 --fibo-anchor-end 2026-04-20 --fibo-right |
## WYNIKI FIBO #2 (valid formation, last 4 months)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ATT | long | hammer | 2026-03-23->2026-05-06 | 29/3 (9.67:1) | 2026-05-11 | 10394797 | https://stooq.pl/q/a2/?s=att&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c ATT.WA --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-05-06 --fibo-right |
| TPE | long | bullish_harami | 2026-03-23->2026-04-10 | 12/13 (0.92:1) | 2026-04-29 | 28279170 | https://stooq.pl/q/a2/?s=tpe&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c TPE --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-04-10 --fibo-right |
