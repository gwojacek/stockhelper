## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| US100 | long | 🚀 3p_steep_incline | 2026-03-30->2026-06-01 | 43/1 (34.11:1) |   0.0% | 36860969767737 | [📈](https://stooq.pl/q/a2/?s=%5Endx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c US100 --fibo-lines 5 --fibo-anchor-start 2026-03-30 --fibo-anchor-end 2026-06-01 --fibo-right | ❌ | 2026-06-01 | 2026-06-02 |
| ITA40 | long | 🚀 3p_steep_incline | 2026-03-23->2026-05-25 | 42/1 (20.93:1) |   0.0% | 18563172249625 | [📈](https://stooq.pl/q/a2/?s=%5Efmib&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c ITA40 --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-05-25 --fibo-right | ❌ | 2026-06-01 | 2026-06-02 |
## WYNIKI FIBO #1 (status waiting 23.6->61.8, bez starych valid_reversal)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BRACOMP | long | reached_23_6_waiting_for_61_8 | none | 2025-10-10->2026-04-14 | 124/22 (5.64:1) |  | 144969619272529 |  58.5% | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --fibo-lines 5 --fibo-anchor-start 2025-10-10 --fibo-anchor-end 2026-04-14 --fibo-right | ❌ | 2026-06-01 | 2026-06-02 |
## WYNIKI FIBO #2 (valid formation, last 4 months)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FRA40 | long | bullish_piercing_line | 2026-03-23->2026-04-17 | 17/20 (0.85:1) | 2026-05-18 | 549825073149 | [📈](https://stooq.pl/q/a2/?s=%5Ecac&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c FRA40 --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-04-17 --fibo-right | ❌ | 2026-06-01 | 2026-06-02 |
| HK.CASH | long | bullish_harami | 2026-03-23->2026-05-14 | 34/9 (3.78:1) | 2026-05-28 | 95130119942063 | [📈](https://stooq.pl/q/a2/?s=%5Ehsi&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c HK.CASH --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-05-14 --fibo-right | ❌ | 2026-06-01 | 2026-06-02 |
