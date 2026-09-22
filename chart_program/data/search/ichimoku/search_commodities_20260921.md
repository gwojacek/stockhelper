## WYNIKI

WYNIKI 1: instrumenty pozostające po jednej stronie chmury Ichimoku (above/below) z kontrolą płynności (Avg10d oraz Ichimoku status).

| Ticker | Pozycja | Świece | Mies. | Start | Close | Avg10d PLN | Ichimoku status | Valid retests from | 4m qualification status | Retest count | Latest Retest date | Latest Retest pattern | Risk | TK cross | Dynamic | Cloud | Chikou | Twist | TK plus | Tenkan in cloud | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COCOA | ⚪ above | 101 | 4.6 | 2026-05-06 | 5345.0000 | - | Inside the cloud | - | standard_4m_breakout | 0 | - | - | - | bearish TK cross | high | thick | ↓ under | red | no | yes | [📈](https://stooq.pl/q/a2/?s=cc.f&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c COCOA --ichimoku-mode on | ✅ | 2026-09-21 | 2026-09-21 |
## WYNIKI 2

WYNIKI 2: instrumenty po flipie (zmiana strony chmury po wcześniejszym długim trendzie), z podsumowaniem retestów i patternów po wybiciu.

| Ticker | Było | Jest | Data wybicia | Mies. od wybicia | Mies. respektu przed wybiciem | Valid retests from | 4m qualification status | Latest Retest status | Retest count | Avg10d PLN | Latest Retest date | Latest Retest pattern | Ichimoku status | Risk | TK cross | Dynamic | Cloud | Chikou | Twist | TK plus | Tenkan in cloud | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| COCOA | below | ⚪ above | 2026-05-06 | 4.6 | 5.9 | - | standard_4m_breakout | returned_to_cloud_waiting_for_pattern | 0 | - | - | - | Inside the cloud | - | bearish TK cross | high | thick | ↓ under | red | no | yes | [📈](https://stooq.pl/q/a2/?s=cc.f&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c COCOA --ichimoku-mode on | ✅ | 2026-09-21 | 2026-09-21 |
| GOLD | below | ⚪ above | 2026-08-10 | 1.4 | 4.8 | - | standard_4m_breakout | shallow_retest_pattern | 2 | - | 2026-09-17 | bullish_engulfing | Under Kijun-sen | 3% | bearish TK cross | aggressive | shallow | ↑ over | green | no | no | [📈](https://stooq.pl/q/a2/?s=xauusd&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c GOLD --ichimoku-mode on | ✅ | 2026-09-21 | 2026-09-21 |
| PLATINUM | below | ⚪ above | 2026-08-21 | 1.1 | 5.6 | - | standard_4m_breakout | shallow_retest_pattern | 1 | - | 2026-09-03 | morning_star | Touched Kijun-sen | 3% | bullish TK cross | high | shallow | ↑ over | green | yes | no | [📈](https://stooq.pl/q/a2/?s=pl.f&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c PLATINUM --ichimoku-mode on | ✅ | 2026-09-21 | 2026-09-21 |
| SILVER | below | ⚪ above | 2026-09-03 | 0.6 | 6.0 | - | standard_4m_breakout | deep_retest_pattern | 1 | - | 2026-09-17 | bullish_engulfing | Touched Kijun-sen | 3% | bearish TK cross | high | normal | ↑ over | green | no | no | [📈](https://stooq.pl/q/a2/?s=xagusd&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c SILVER --ichimoku-mode on | ✅ | 2026-09-21 | 2026-09-21 |
