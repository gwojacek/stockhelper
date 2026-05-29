## WYNIKI

WYNIKI 1: instrumenty pozostające po jednej stronie chmury Ichimoku (above/below) z kontrolą płynności (Avg10d oraz Ichimoku status).

| Ticker | Pozycja | Świece | Mies. | Start | Close | Avg10d PLN | Ichimoku status | Retest count | Latest Retest date | Latest Retest pattern | Link | Python command |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALUMINIUM | ⚪ above | 178 | 8.5 | 2025-09-11 | 3646.5000 | - | Over Kijun-sen | 1 | 2026-02-13 | hammer | https://stooq.pl/q/a2/?s=al.f&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c ALUMINIUM --ichimoku-mode on |
| COFFEE | 🔴 below | 127 | 5.8 | 2025-12-02 | 274.2500 | - | Under Kijun-sen | 3 | 2026-04-16 | evening_star | https://stooq.pl/q/a2/?s=kc.f&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c COFFEE --ichimoku-mode on |
| SOYOIL | ⚪ above | 98 | 4.5 | 2026-01-13 | 76.7000 | - | Over Kijun-sen | 0 | - | - | https://stooq.pl/q/a2/?s=zl.f&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c SOYOIL --ichimoku-mode on |
| WHEAT | ⚪ above | 87 | 4.0 | 2026-01-28 | 624.0000 | - | Under Kijun-sen | 1 | 2026-02-11 | morning_star | https://stooq.pl/q/a2/?s=zw.f&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c WHEAT --ichimoku-mode on |
| SOYBEAN | ⚪ above | 82 | 3.7 | 2026-02-04 | 1194.5000 | - | Under Kijun-sen | 0 | - | - | https://stooq.pl/q/a2/?s=zs.f&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c SOYBEAN --ichimoku-mode on |
## WYNIKI 2

WYNIKI 2: instrumenty po flipie (zmiana strony chmury po wcześniejszym długim trendzie), z podsumowaniem retestów i patternów po wybiciu.

| Ticker | Było | Jest | Data wybicia | Mies. od wybicia | Latest Retest status | Retest count | Avg10d PLN | Latest Retest date | Latest Retest pattern | Link | Python command |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COCOA | below | ⚪ above | 2026-05-06 | 0.8 | breakout_confirmed | 0 | - | - | - | https://stooq.pl/q/a2/?s=cc.f&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c COCOA --ichimoku-mode on |
