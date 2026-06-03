## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| US100 | long | 🚀 3p_steep_incline | 2026-03-30->2026-06-03 | 45/1 (34.65:1) |   0.0% | 36703216663756 | [📈](https://stooq.pl/q/a2/?s=%5Endx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c US100 --fibo-lines 5 --fibo-anchor-start 2026-03-30 --fibo-anchor-end 2026-06-03 --fibo-right | ✅ | 2026-06-03 | 2026-06-03 |
| ITA40 | long | 🚀 3p_steep_incline | 2026-03-23->2026-06-02 | 48/1 (21.54:1) |   0.0% | 17675277237826 | [📈](https://stooq.pl/q/a2/?s=%5Efmib&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c ITA40 --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-06-02 --fibo-right | ✅ | 2026-06-03 | 2026-06-03 |
## WYNIKI FIBO #1 (status waiting 23.6->61.8, bez starych valid_reversal)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BRACOMP | long | reached_23_6_waiting_for_61_8 | none | 2025-10-10->2026-04-14 | 124/24 (5.17:1) |  | 146056960334080 |  66.7% | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --fibo-lines 5 --fibo-anchor-start 2025-10-10 --fibo-anchor-end 2026-04-14 --fibo-right | ✅ | 2026-06-03 | 2026-06-03 |
## WYNIKI FIBO #2 (valid formation, last 4 months)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FRA40 | short | dark_cloud_cover | 2026-01-09->2026-03-23 | 51/9 (5.67:1) | 2026-04-07 | 549330898382 | [📈](https://stooq.pl/q/a2/?s=%5Ecac&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c FRA40 --fibo-lines 5 --fibo-anchor-start 2026-01-09 --fibo-anchor-end 2026-03-23 --fibo-right | ✅ | 2026-06-03 | 2026-06-03 |
| HK.CASH | long | bullish_harami | 2026-03-23->2026-05-14 | 34/9 (3.78:1) | 2026-05-28 | 98092707070158 | [📈](https://stooq.pl/q/a2/?s=%5Ehsi&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c HK.CASH --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-05-14 --fibo-right | ✅ | 2026-06-03 | 2026-06-03 |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MEXCOMP | ⏳ unbroken | 2026-04-08->2026-06-03 | 40 | 1.9 | 2026-04-08@71221.55->2026-05-07@70708.53 | 2026-03-30@66728.97->2026-04-29@66861.93 | 4 | 2 | 6.53% | 4.69% | mild | - | - | 27.41 | 15182428338914 | [📈](https://stooq.pl/q/a2/?s=%5Eipc&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c MEXCOMP --wedge-lines --wedge-upper-start 2026-04-08,71221.55 --wedge-upper-end 2026-05-07,70708.53 --wedge-lower-start 2026-03-30,66728.97 --wedge-lower-end 2026-04-29,66861.93 --wedge-right | ✅ | 2026-06-03 | 2026-06-03 |
