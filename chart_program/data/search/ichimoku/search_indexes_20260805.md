## WYNIKI

WYNIKI 1: instrumenty pozostające po jednej stronie chmury Ichimoku (above/below) z kontrolą płynności (Avg10d oraz Ichimoku status).

| Ticker | Pozycja | Świece | Mies. | Start | Close | Avg10d PLN | Ichimoku status | Retest count | Latest Retest date | Latest Retest pattern | Risk | TK cross | Dynamic | Cloud | Chikou | Twist | TK plus | Tenkan in cloud | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ITA40 | ⚪ above | 88 | 3.9 | 2025-10-24 | 53742.7188 | - | Over Kijun-sen | 0 | - | - | - | neutral TK cross | high | normal | ↑ over | green | no | no | [📈](https://stooq.pl/q/a2/?s=%5Efmib&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c ITA40 --ichimoku-mode on --scanner-breakout-date 2025-10-24 | ✅ | 2026-08-05 | 2026-08-05 |
| NED25 | ⚪ above | 85 | 3.9 | 2026-04-10 | 1117.6100 | - | Over Kijun-sen | 0 | - | - | - | bullish TK cross | high | shallow | ↑ over | green | yes | no | [📈](https://stooq.pl/q/a2/?s=%5Eaex&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c NED25 --ichimoku-mode on --scanner-breakout-date 2026-04-10 | ✅ | 2026-08-05 | 2026-08-05 |
| SPA35 | ⚪ above | 85 | 3.9 | 2025-07-21 | 20122.5996 | - | Over Kijun-sen | 0 | - | - | - | bullish TK cross | mild | normal | ↑ over | green | yes | no | [📈](https://stooq.pl/q/a2/?s=%5Eibex&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c SPA35 --ichimoku-mode on --scanner-breakout-date 2025-07-21 | ✅ | 2026-08-05 | 2026-08-05 |
## WYNIKI 2

WYNIKI 2: instrumenty po flipie (zmiana strony chmury po wcześniejszym długim trendzie), z podsumowaniem retestów i patternów po wybiciu.

| Ticker | Było | Jest | Data wybicia | Mies. od wybicia | Mies. respektu przed wybiciem | Latest Retest status | Retest count | Avg10d PLN | Latest Retest date | Latest Retest pattern | Ichimoku status | Risk | TK cross | Dynamic | Cloud | Chikou | Twist | TK plus | Tenkan in cloud | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BRACOMP | above | 🔴 below | 2026-05-15 | 2.7 | 8.6 | returned_to_cloud_waiting_for_pattern | 0 | - | - | - | Inside the cloud | - | bullish TK cross | slow | thick | ↑ over | green | no | yes | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --ichimoku-mode on --scanner-breakout-date 2026-05-15 | ❌ | 2026-08-04 | 2026-08-05 |
