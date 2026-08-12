## WYNIKI

WYNIKI 1: instrumenty pozostające po jednej stronie chmury Ichimoku (above/below) z kontrolą płynności (Avg10d oraz Ichimoku status).

| Ticker | Pozycja | Świece | Mies. | Start | Close | Avg10d PLN | Ichimoku status | Retest count | Latest Retest date | Latest Retest pattern | Risk | TK cross | Dynamic | Cloud | Chikou | Twist | TK plus | Tenkan in cloud | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PLATINUM | 🔴 below | 117 | 5.3 | 2026-03-11 | 1768.7000 | - | Inside the cloud | 3 | 2026-08-06 | bearish_engulfing | - | bullish TK cross | slow | thick | ↑ over | red | no | yes | [📈](https://stooq.pl/q/a2/?s=pl.f&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c PLATINUM --ichimoku-mode on | ✅ | 2026-08-11 | 2026-08-11 |
| SILVER | 🔴 below | 116 | 5.3 | 2026-03-12 | 65.0200 | - | Inside the cloud | 5 | 2026-06-03 | bearish_engulfing | - | bullish TK cross | mild | thick | ↑ over | red | no | no | [📈](https://stooq.pl/q/a2/?s=xagusd&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c SILVER --ichimoku-mode on | ✅ | 2026-08-11 | 2026-08-11 |
## WYNIKI 2

WYNIKI 2: instrumenty po flipie (zmiana strony chmury po wcześniejszym długim trendzie), z podsumowaniem retestów i patternów po wybiciu.

| Ticker | Było | Jest | Data wybicia | Mies. od wybicia | Mies. respektu przed wybiciem | Latest Retest status | Retest count | Avg10d PLN | Latest Retest date | Latest Retest pattern | Ichimoku status | Risk | TK cross | Dynamic | Cloud | Chikou | Twist | TK plus | Tenkan in cloud | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COCOA | below | ⚪ above | 2026-05-06 | 3.2 | 5.9 | no_breakout | 0 | - | - | - | Touched Kijun-sen | - | bearish TK cross | mild | thick | ↑ over | green | no | no | [📈](https://stooq.pl/q/a2/?s=cc.f&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c COCOA --ichimoku-mode on | ✅ | 2026-08-11 | 2026-08-11 |
| PALLADIUM | below | ⚪ above | 2026-08-06 | 0.2 | 5.3 | shallow_retest_pattern | 2 | - | 2026-08-10 | hammer | Touched the cloud | 3% | bullish TK cross | slow | thick | ↑ over | green | yes | yes | [📈](https://stooq.pl/q/a2/?s=pa.f&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c PALLADIUM --ichimoku-mode on | ✅ | 2026-08-11 | 2026-08-11 |
| GOLD | below | ⚪ above | 2026-08-10 | 0.1 | 4.8 | breakout_confirmed | 0 | - | - | - | Over Kijun-sen | 2% | bullish TK cross | high | normal | ↑ over | red | yes | yes | [📈](https://stooq.pl/q/a2/?s=xauusd&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c GOLD --ichimoku-mode on | ✅ | 2026-08-11 | 2026-08-11 |
