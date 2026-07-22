## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| JP225 | long | 🚀 3p_steep_incline | 2025-07-17->2026-06-22 | 224/1 (84.99:1) | - | 10712059843672 | [📈](https://stooq.pl/q/a2/?s=%5Enkx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c JP225 --fibo-lines 5 --fibo-anchor-start 2025-07-17 --fibo-anchor-end 2026-06-22 --fibo-right | ❌ | 2026-07-21 | 2026-07-22 |
| ITA40 | long | 🚀 3p_steep_incline | 2026-03-23->2026-07-07 | 73/1 (27.89:1) | - | 10783875794260 | [📈](https://stooq.pl/q/a2/?s=%5Efmib&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c ITA40 --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-07-07 --fibo-right | ✅ | 2026-07-22 | 2026-07-22 |
## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HK.CASH | short | reached_23_6_waiting_for_61_8 | none | 2026-01-29->2026-06-26 | 97/16 (6.06:1) |  | 85064820496934 |  61.8% | [📈](https://stooq.pl/q/a2/?s=%5Ehsi&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c HK.CASH --fibo-lines 5 --fibo-anchor-start 2026-01-29 --fibo-anchor-end 2026-06-26 --fibo-right | ❌ | 2026-07-21 | 2026-07-22 |
| BRACOMP | short | reached_23_6_waiting_for_61_8 | none | 2026-04-14->2026-06-19 | 45/18 (2.50:1) |  | 1050290700160 |   8.8% | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --fibo-lines 5 --fibo-anchor-start 2026-04-14 --fibo-anchor-end 2026-06-19 --fibo-right | ✅ | 2026-07-22 | 2026-07-22 |
## WYNIKI FIBO #2 (valid pattern up to 2 weeks)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MEXCOMP | ⏳ unbroken | 2025-11-24->2026-07-22 | 165 | 7.9 | 2026-02-12@72111.40625->2026-02-27@71890.34375 | 2025-11-24@61840.51172->2026-06-09@64666.23828 | 3 | 2 | 13.55% | 6.80% | mild | - | - | 341.74 | 7730396955414 | [📈](https://stooq.pl/q/a2/?s=%5Eipc&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c MEXCOMP --wedge-lines --wedge-upper-start 2026-02-12,72111.40625 --wedge-upper-end 2026-02-27,71890.34375 --wedge-lower-start 2025-11-24,61840.51172 --wedge-lower-end 2026-06-09,64666.23828 --wedge-right | ✅ | 2026-07-22 | 2026-07-22 |
| US100 | ⏳ unbroken | 2026-05-04->2026-07-22 | 55 | 2.6 | 2026-06-22@30642.57031->2026-06-30@30328.78906 | 2026-05-04@27504.08984->2026-07-17@28231.32031 | 2 | 2 | 9.15% | 4.36% | strong | - | - | 95.63 | 199414341001438 | [📈](https://stooq.pl/q/a2/?s=%5Endx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c US100 --wedge-lines --wedge-upper-start 2026-06-22,30642.57031 --wedge-upper-end 2026-06-30,30328.78906 --wedge-lower-start 2026-05-04,27504.08984 --wedge-lower-end 2026-07-17,28231.32031 --wedge-right | ✅ | 2026-07-22 | 2026-07-22 |
| US500 | ⏳ unbroken | 2026-06-02->2026-07-22 | 35 | 1.7 | 2026-06-02@7620.8999->2026-07-15@7581.5 | 2026-07-08@7421.81982->2026-07-17@7431.25977 | 2 | 2 | 2.21% | 1.85% | mild | - | - | 30.60 | 34128838097667 | [📈](https://stooq.pl/q/a2/?s=%5Espx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c US500 --wedge-lines --wedge-upper-start 2026-06-02,7620.8999 --wedge-upper-end 2026-07-15,7581.5 --wedge-lower-start 2026-07-08,7421.81982 --wedge-lower-end 2026-07-17,7431.25977 --wedge-right | ✅ | 2026-07-22 | 2026-07-22 |
