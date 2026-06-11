## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| US100 | long | 🚀 3p_steep_incline | 2026-03-30->2026-06-03 | 45/1 (34.68:1) |   0.0% | 282249336389899 | [📈](https://stooq.pl/q/a2/?s=%5Endx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c US100 --fibo-lines 5 --fibo-anchor-start 2026-03-30 --fibo-anchor-end 2026-06-03 --fibo-right | ✅ | 2026-06-11 | 2026-06-11 |
| ITA40 | long | 🚀 3p_steep_incline | 2026-03-23->2026-06-09 | 53/1 (23.13:1) |   0.0% | 18179412611730 | [📈](https://stooq.pl/q/a2/?s=%5Efmib&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c ITA40 --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-06-09 --fibo-right | ✅ | 2026-06-11 | 2026-06-11 |
## WYNIKI FIBO #1 (status waiting 23.6->61.8, bez starych valid_reversal)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DE40 | long | reached_23_6_waiting_for_61_8 | none | 2026-03-23->2026-05-25 | 42/13 (3.23:1) |  | 1570388141957 |  28.2% | [📈](https://stooq.pl/q/a2/?s=%5Edax&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c DE40 --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-05-25 --fibo-right | ✅ | 2026-06-11 | 2026-06-11 |
| BRACOMP | long | reached_23_6_waiting_for_61_8 | none | 2025-10-10->2026-04-14 | 124/24 (5.17:1) |  | 1431478768440 |  61.6% | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --fibo-lines 5 --fibo-anchor-start 2025-10-10 --fibo-anchor-end 2026-04-14 --fibo-right | ✅ | 2026-06-11 | 2026-06-11 |
## WYNIKI FIBO #2 (valid formation, last 4 months)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CHN.CASH | long | bullish_piercing_line | 2026-03-23->2026-05-14 | 34/2 (17.00:1) | 2026-05-18 | 27538933285 | [📈](https://stooq.pl/q/a2/?s=0el.c&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c CHN.CASH --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-05-14 --fibo-right | ❌ | 2026-06-10 | 2026-06-11 |
| HK.CASH | long | bullish_harami | 2026-03-23->2026-05-14 | 34/9 (3.78:1) | 2026-05-28 | 98156158779941 | [📈](https://stooq.pl/q/a2/?s=%5Ehsi&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c HK.CASH --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-05-14 --fibo-right | ❌ | 2026-06-10 | 2026-06-11 |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
