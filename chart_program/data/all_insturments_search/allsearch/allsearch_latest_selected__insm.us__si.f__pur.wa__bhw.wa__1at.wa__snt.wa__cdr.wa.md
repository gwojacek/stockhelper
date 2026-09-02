ALLSEARCH COMBO REPORT

Legenda (progi): 🟨 Fibo: próg płynności Th10d (ostatnie 10 świeczek) = bazowo 500000 PLN × mnożnik PKB kraju (WIG/PL: ×1.00 = 500 000 PLN, DAX/DE: ×2.98 = 1 490 999 PLN, US100/US: ×15.01 = 7 503 008 PLN). ☁️ Ichimoku: próg płynności = 700000 PLN × mnożnik PKB kraju (WIG/PL: ×1.00 = 700 000 PLN, DAX/DE: ×2.98 = 2 087 398 PLN, US100/US: ×15.01 = 10 504 211 PLN). 🧪 Low<Th20: liczba dni z ostatnich 20 poniżej progu 300000 PLN × mnożnik kraju (WIG/PL: ×1.00 = 300 000 PLN, DAX/DE: ×2.98 = 894 599 PLN, US100/US: ×15.01 = 4 501 805 PLN) — nie może być więcej niż 2.


■■■■■■■■■■■■■■■■■■■■ 📊 SELECTED__INSM.US__SI.F__PUR.WA__BHW.WA__1AT.WA__SNT.WA__CDR.WA ■■■■■■■■■■■■■■■■■■■■■

------------------------------------------- ICHIMOKU -------------------------------------------

## WYNIKI

WYNIKI 1: instrumenty pozostające po jednej stronie chmury Ichimoku (above/below) z kontrolą płynności (Avg10d oraz Ichimoku status).

| Ticker | Pozycja | Świece | Mies. | Start | Close | Avg10d PLN | Ichimoku status | Valid retests from | 4m qualification status | Retest count | Latest Retest date | Latest Retest pattern | Risk | TK cross | Dynamic | Cloud | Chikou | Twist | TK plus | Tenkan in cloud | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI 2

WYNIKI 2: instrumenty po flipie (zmiana strony chmury po wcześniejszym długim trendzie), z podsumowaniem retestów i patternów po wybiciu.

| Ticker | Było | Jest | Data wybicia | Mies. od wybicia | Mies. respektu przed wybiciem | Valid retests from | 4m qualification status | Latest Retest status | Retest count | Avg10d PLN | Latest Retest date | Latest Retest pattern | Ichimoku status | Risk | TK cross | Dynamic | Cloud | Chikou | Twist | TK plus | Tenkan in cloud | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| INSM.US | below | ⚪ above | 2026-08-06 | 0.9 | 7.6 | - | standard_4m_breakout | no_breakout | 0 | 782647900 | - | - | Over Kijun-sen | - | bullish TK cross | aggressive | shallow | ↑ over | green | yes | no | [📈](https://stooq.pl/q/a2/?s=insm.us&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c INSM.US --ichimoku-mode on | ✅ | 2026-09-01 | 2026-09-01 |
| BHW.WA | above | 🔴 below | 2026-09-01 | 0.1 | 5.0 | - | standard_4m_breakout | returned_to_cloud_waiting_for_pattern | 0 | 4080866 | - | - | Inside the cloud | - | bearish TK cross | high | normal | ↓ under | red | yes | yes | [📈](https://stooq.pl/q/a2/?s=bhw.wa&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BHW.WA --ichimoku-mode on | ✅ | 2026-09-02 | 2026-09-01 |

--------------------------------------------- FIBO ---------------------------------------------

## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Pattern date | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Saved by user | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SNT.WA | long | reached_23_6_waiting_for_61_8 | none |  | 2026-06-01->2026-07-15 | 31/35 (0.89:1) |  | 13444811 |  82.9% | no | [📈](https://stooq.pl/q/a2/?s=snt.wa&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c SNT.WA --fibo-lines 5 --fibo-anchor-start 2026-06-01 --fibo-anchor-end 2026-07-15 --fibo-right | ✅ | 2026-09-02 | 2026-09-01 |
## WYNIKI FIBO #2 (valid pattern up to 2 weeks)

| Ticker | Dir | Pattern | Pattern date | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Saved by user | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CDR.WA | long | bullish_harami | 2026-08-28 | 2026-06-26->2026-08-13 | 34/10 (3.40:1) | 2026-08-27 | 114056687 | no | [📈](https://stooq.pl/q/a2/?s=cdr.wa&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c CDR.WA --fibo-lines 5 --fibo-anchor-start 2026-06-26 --fibo-anchor-end 2026-08-13 --fibo-right --scanner-pattern-date 2026-08-28 --scanner-pattern-name bullish_harami | ✅ | 2026-09-02 | 2026-09-01 |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Saved by user | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SNT.WA | 🚀 breakout | 2026-07-09->2026-09-02 | 40 | 1.9 | 2026-08-06@384.4->2026-08-20@360.2 | 2026-07-09@368.2->2026-07-30@351.2 | 2 | 3 | 12.03% | 4.46% | strong | 2026-09-02 | short | 754.64 | 13444811 | no | [📈](https://stooq.pl/q/a2/?s=snt.wa&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c SNT.WA --wedge-lines --wedge-upper-start 2026-08-06,384.4 --wedge-upper-end 2026-08-20,360.2 --wedge-lower-start 2026-07-09,368.2 --wedge-lower-end 2026-07-30,351.2 --wedge-right | ✅ | 2026-09-02 | 2026-09-01 |
| CDR.WA | ⏳ unbroken | 2026-04-22->2026-09-02 | 94 | 4.5 | 2026-04-22@297.0->2026-08-13@269.0 | 2026-07-23@225.0->2026-08-27@230.3 | 2 | 2 | 21.23% | 14.16% | strong | - | - | 166.50 | 114056687 | no | [📈](https://stooq.pl/q/a2/?s=cdr.wa&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c CDR.WA --wedge-lines --wedge-upper-start 2026-04-22,297.0 --wedge-upper-end 2026-08-13,269.0 --wedge-lower-start 2026-07-23,225.0 --wedge-lower-end 2026-08-27,230.3 --wedge-right | ✅ | 2026-09-02 | 2026-09-01 |


Źródło danych CSV instrumentów: /app/data/csv
