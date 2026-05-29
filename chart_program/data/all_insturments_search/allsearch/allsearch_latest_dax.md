ALLSEARCH COMBO REPORT

Legenda (progi): 🟨 Fibo: próg płynności Th10d (ostatnie 10 świeczek) = bazowo 500000 PLN × mnożnik PKB kraju (WIG/PL: ×1.00 = 500 000 PLN, DAX/DE: ×2.98 = 1 490 999 PLN, US100/US: ×15.01 = 7 503 008 PLN). ☁️ Ichimoku: próg płynności = 700000 PLN × mnożnik PKB kraju (WIG/PL: ×1.00 = 700 000 PLN, DAX/DE: ×2.98 = 2 087 398 PLN, US100/US: ×15.01 = 10 504 211 PLN). 🧪 Low<Th20: liczba dni z ostatnich 20 poniżej progu 300000 PLN × mnożnik kraju (WIG/PL: ×1.00 = 300 000 PLN, DAX/DE: ×2.98 = 894 599 PLN, US100/US: ×15.01 = 4 501 805 PLN) — nie może być więcej niż 2.


■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■ 🇩🇪 DAX ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■

------------------------------------------- ICHIMOKU -------------------------------------------

## WYNIKI

WYNIKI 1: instrumenty pozostające po jednej stronie chmury Ichimoku (above/below) z kontrolą płynności (Avg10d oraz Ichimoku status).

| Ticker | Pozycja | Świece | Mies. | Start | Close | Avg10d PLN | Ichimoku status | Retest count | Latest Retest date | Latest Retest pattern | Link | Python command |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HFG.DE | 🔴 below | 198 | 9.5 | 2026-01-27 | 4.3070 | 10822811 | Inside the cloud | 3 | 2026-05-12 | bearish_harami | https://stooq.pl/q/a2/?s=hfg.de&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c HFG.DE --ichimoku-mode on |
| ENR.DE | ⚪ above | 172 | 8.1 | 2025-11-24 | 174.3600 | 1528833052 | Under Kijun-sen | 1 | 2026-03-19 | hammer | https://stooq.pl/q/a2/?s=enr.de&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c ENR.DE --ichimoku-mode on |
| RWE.DE | ⚪ above | 171 | 8.1 | 2025-12-19 | 55.1800 | 317198548 | Inside the cloud | 2 | 2026-05-20 | hammer | https://stooq.pl/q/a2/?s=rwe.de&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c RWE.DE --ichimoku-mode on |
| SAP.DE | 🔴 below | 146 | 6.7 | 2026-01-14 | 150.0000 | 1620197059 | Touched the cloud | 1 | 2026-05-20 | bearish_harami | https://stooq.pl/q/a2/?s=sap.de&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c SAP.DE --ichimoku-mode on |
| SHL.DE | 🔴 below | 90 | 4.2 | 2026-01-21 | 35.0800 | 127145101 | Under Kijun-sen | 0 | - | - | https://stooq.pl/q/a2/?s=shl.de&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c SHL.DE --ichimoku-mode on |
| AIR.DE | 🔴 below | 84 | 3.9 | 2026-01-27 | 173.8000 | 193113889 | Inside the cloud | 2 | 2026-05-04 | shooting_star | https://stooq.pl/q/a2/?s=air.de&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c AIR.DE --ichimoku-mode on |
## WYNIKI 2

WYNIKI 2: instrumenty po flipie (zmiana strony chmury po wcześniejszym długim trendzie), z podsumowaniem retestów i patternów po wybiciu.

| Ticker | Było | Jest | Data wybicia | Mies. od wybicia | Latest Retest status | Retest count | Avg10d PLN | Latest Retest date | Latest Retest pattern | Link | Python command |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

--------------------------------------------- FIBO ---------------------------------------------

## WYNIKI FIBO #1 (status waiting 23.6->61.8, bez starych valid_reversal)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BAYN.DE | long | reached_23_6_waiting_for_61_8 | none | 2025-11-07->2026-02-17 | 67/28 (2.39:1) |  | 315512729 |  65.4% | https://stooq.pl/q/a2/?s=bayn.de&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c BAYN.DE --fibo-lines 5 --fibo-anchor-start 2025-11-07 --fibo-anchor-end 2026-02-17 --fibo-right |
| BNR.DE | long | reached_23_6_waiting_for_61_8 | none | 2026-03-09->2026-05-04 | 37/17 (2.18:1) |  | 83094578 |  33.3% | https://stooq.pl/q/a2/?s=bnr.de&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c BNR.DE --fibo-lines 5 --fibo-anchor-start 2026-03-09 --fibo-anchor-end 2026-05-04 --fibo-right |
| RWE.DE | long | reached_23_6_waiting_for_61_8 | none | 2025-10-02->2026-04-30 | 143/18 (7.94:1) |  | 317198548 |  14.4% | https://stooq.pl/q/a2/?s=rwe.de&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c RWE.DE --fibo-lines 5 --fibo-anchor-start 2025-10-02 --fibo-anchor-end 2026-04-30 --fibo-right |
| DB1.DE | long | reached_23_6_waiting_for_61_8 | none | 2026-02-04->2026-04-28 | 57/20 (2.85:1) |  | 404588387 |   4.5% | https://stooq.pl/q/a2/?s=db1.de&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c DB1.DE --fibo-lines 5 --fibo-anchor-start 2026-02-04 --fibo-anchor-end 2026-04-28 --fibo-right |
## WYNIKI FIBO #2 (valid formation, last 4 months)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MRK.DE | long | bullish_engulfing | 2026-03-23->2026-04-21 | 19/5 (3.80:1) | 2026-04-28 | 170419563 | https://stooq.pl/q/a2/?s=mrk.de&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1 | python run -c MRK.DE --fibo-lines 5 --fibo-anchor-start 2026-03-23 --fibo-anchor-end 2026-04-21 --fibo-right |


Źródło danych CSV instrumentów: /home/jacek/PycharmProjects/stockhelper/data
