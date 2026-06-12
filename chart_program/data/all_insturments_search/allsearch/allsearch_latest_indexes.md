ALLSEARCH COMBO REPORT

Legenda (progi): 🟨 Fibo: próg płynności Th10d (ostatnie 10 świeczek) = bazowo 500000 PLN × mnożnik PKB kraju (WIG/PL: ×1.00 = 500 000 PLN, DAX/DE: ×2.98 = 1 490 999 PLN, US100/US: ×15.01 = 7 503 008 PLN). ☁️ Ichimoku: próg płynności = 700000 PLN × mnożnik PKB kraju (WIG/PL: ×1.00 = 700 000 PLN, DAX/DE: ×2.98 = 2 087 398 PLN, US100/US: ×15.01 = 10 504 211 PLN). 🧪 Low<Th20: liczba dni z ostatnich 20 poniżej progu 300000 PLN × mnożnik kraju (WIG/PL: ×1.00 = 300 000 PLN, DAX/DE: ×2.98 = 894 599 PLN, US100/US: ×15.01 = 4 501 805 PLN) — nie może być więcej niż 2.


■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■ 📊 INDEXES ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■

------------------------------------------- ICHIMOKU -------------------------------------------

## WYNIKI

WYNIKI 1: instrumenty pozostające po jednej stronie chmury Ichimoku (above/below) z kontrolą płynności (Avg10d oraz Ichimoku status).

| Ticker | Pozycja | Świece | Mies. | Start | Close | Avg10d PLN | Ichimoku status | Retest count | Latest Retest date | Latest Retest pattern | Risk | TK cross | Dynamic | Cloud | Chikou | Twist | TK plus | Tenkan in cloud | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WIG20 | ⚪ above | 162 | 7.9 | 2025-10-20 | 3723.9399 | - | Over Kijun-sen | 2 | 2026-04-02 | bullish_piercing_line | - | bullish TK cross | high | shallow | ↑ over | green | yes | no | [📈](https://stooq.pl/q/a2/?s=wig20&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c WIG20 --ichimoku-mode on | ✅ | 2026-06-12 | 2026-06-12 |
## WYNIKI 2

WYNIKI 2: instrumenty po flipie (zmiana strony chmury po wcześniejszym długim trendzie), z podsumowaniem retestów i patternów po wybiciu.

| Ticker | Było | Jest | Data wybicia | Mies. od wybicia | Mies. respektu przed wybiciem | Latest Retest status | Retest count | Avg10d PLN | Latest Retest date | Latest Retest pattern | Ichimoku status | Risk | TK cross | Dynamic | Cloud | Chikou | Twist | TK plus | Tenkan in cloud | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

--------------------------------------------- FIBO ---------------------------------------------

## WYNIKI FIBO #0 (3P steep incline)

| Ticker | Dir | Status | Incline | Ratio(d) | Near61.8 | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| US100 | long | 🚀 3p_steep_incline | 2026-03-30->2026-06-03 | 45/1 (34.68:1) | - | 307788329554352 | [📈](https://stooq.pl/q/a2/?s=%5Endx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c US100 --fibo-lines 5 --fibo-anchor-start 2026-03-30 --fibo-anchor-end 2026-06-03 --fibo-right | ❌ | 2026-06-11 | 2026-06-12 |
| ITA40 | long | 🚀 3p_steep_incline | 2026-03-23->2026-06-12 | 56/1 (24.05:1) | - | 17217877353540 | [📈](https://stooq.pl/q/a2/?s=%5Efmib&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c ITA40 --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-06-12 --fibo-right | ✅ | 2026-06-12 | 2026-06-12 |
## WYNIKI FIBO #1 (status waiting 23.6->61.8, bez starych valid_reversal)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BRACOMP | long | reached_23_6_waiting_for_61_8 | none | 2025-10-10->2026-04-14 | 124/24 (5.17:1) |  | 1612869430370 |  61.6% | [📈](https://stooq.pl/q/a2/?s=%5Ebvp&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c BRACOMP --fibo-lines 5 --fibo-anchor-start 2025-10-10 --fibo-anchor-end 2026-04-14 --fibo-right | ❌ | 2026-06-11 | 2026-06-12 |
## WYNIKI FIBO #2 (valid formation, last 4 months)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CHN.CASH | ⏳ unbroken | 2026-03-30->2026-06-12 | 50 | 2.4 | 2026-02-23@9235.67969->2026-05-12@8957.7998 | 2026-03-30@8286.24023->2026-06-11@8217.08008 | 4 | 2 | 9.74% | 7.46% | mild | - | - | 32.16 | 19374805010 | [📈](https://stooq.pl/q/a2/?s=0el.c&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c CHN.CASH --wedge-lines --wedge-upper-start 2026-02-23,9235.67969 --wedge-upper-end 2026-05-12,8957.7998 --wedge-lower-start 2026-03-30,8286.24023 --wedge-lower-end 2026-06-11,8217.08008 --wedge-right | ✅ | 2026-06-12 | 2026-06-12 |
| UK100 | ⏳ unbroken | 2026-05-12->2026-06-12 | 23 | 1.1 | 2026-04-20@10683.7002->2026-05-26@10557.2002 | 2026-05-12@10152.09961->2026-06-10@10127.59961 | 3 | 3 | 4.33% | 3.48% | mild | - | - | 17.78 | 7666198072709 | [📈](https://stooq.pl/q/a2/?s=%5Eukx&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c UK100 --wedge-lines --wedge-upper-start 2026-04-20,10683.7002 --wedge-upper-end 2026-05-26,10557.2002 --wedge-lower-start 2026-05-12,10152.09961 --wedge-lower-end 2026-06-10,10127.59961 --wedge-right | ✅ | 2026-06-12 | 2026-06-12 |


Źródło danych CSV instrumentów: /home/jacek/PycharmProjects/stockhelper/data
