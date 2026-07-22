ALLSEARCH COMBO REPORT

Legenda (progi): 🟨 Fibo: próg płynności Th10d (ostatnie 10 świeczek) = bazowo 500000 PLN × mnożnik PKB kraju (WIG/PL: ×1.00 = 500 000 PLN, DAX/DE: ×2.98 = 1 490 999 PLN, US100/US: ×15.01 = 7 503 008 PLN). ☁️ Ichimoku: próg płynności = 700000 PLN × mnożnik PKB kraju (WIG/PL: ×1.00 = 700 000 PLN, DAX/DE: ×2.98 = 2 087 398 PLN, US100/US: ×15.01 = 10 504 211 PLN). 🧪 Low<Th20: liczba dni z ostatnich 20 poniżej progu 300000 PLN × mnożnik kraju (WIG/PL: ×1.00 = 300 000 PLN, DAX/DE: ×2.98 = 894 599 PLN, US100/US: ×15.01 = 4 501 805 PLN) — nie może być więcej niż 2.


■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■ 💱 FOREX ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■

------------------------------------------- ICHIMOKU -------------------------------------------

## WYNIKI

WYNIKI 1: instrumenty pozostające po jednej stronie chmury Ichimoku (above/below) z kontrolą płynności (Avg10d oraz Ichimoku status).

| Ticker | Pozycja | Świece | Mies. | Start | Close | Avg10d PLN | Ichimoku status | Retest count | Latest Retest date | Latest Retest pattern | Risk | TK cross | Dynamic | Cloud | Chikou | Twist | TK plus | Tenkan in cloud | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI 2

WYNIKI 2: instrumenty po flipie (zmiana strony chmury po wcześniejszym długim trendzie), z podsumowaniem retestów i patternów po wybiciu.

| Ticker | Było | Jest | Data wybicia | Mies. od wybicia | Mies. respektu przed wybiciem | Latest Retest status | Retest count | Avg10d PLN | Latest Retest date | Latest Retest pattern | Ichimoku status | Risk | TK cross | Dynamic | Cloud | Chikou | Twist | TK plus | Tenkan in cloud | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

--------------------------------------------- FIBO ---------------------------------------------

## WYNIKI FIBO #1 (Waiting 23.6→61.8 and patterns)

| Ticker | Dir | Status | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Near61.8 | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GBPUSD | short | reached_23_6_waiting_for_61_8 | none | 2026-01-27->2026-06-24 | 106/18 (5.89:1) |  | 0 |  57.2% | [📈](https://stooq.pl/q/a2/?s=gbpusd&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c GBPUSD --fibo-lines 5 --fibo-anchor-start 2026-01-27 --fibo-anchor-end 2026-06-24 --fibo-right | ✅ | 2026-07-20 | 2026-07-20 |
| AUDUSD | short | reached_23_6_waiting_for_61_8 | none | 2026-04-17->2026-06-30 | 52/14 (3.71:1) |  | 0 |  44.3% | [📈](https://stooq.pl/q/a2/?s=audusd&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c AUDUSD --fibo-lines 5 --fibo-anchor-start 2026-04-17 --fibo-anchor-end 2026-06-30 --fibo-right | ✅ | 2026-07-20 | 2026-07-20 |
## WYNIKI FIBO #2 (valid pattern up to 2 weeks)

| Ticker | Dir | Pattern | Incline | Ratio(d) | Touched_61.8_date | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
## WYNIKI KLINY OPADAJĄCE (unbroken falling wedges)

| Ticker | Status | Wedge | Days | Months | Upper line | Lower line | Upper touches | Lower touches | Start width | End width | Slope | Breakout date | Breakout direction | Score | Avg10d PLN | Link | Python command | Latest data? | Latest date | Expected date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EURJPY | 🚀 breakout | 2026-04-30->2026-07-20 | 58 | 2.8 | 2026-04-30@187.539->2026-06-17@186.318 | 2026-05-06@182.059->2026-06-24@183.172 | 3 | 2 | 2.88% | 0.94% | mild | 2026-07-15 | long | 351.30 | 0 | [📈](https://stooq.pl/q/a2/?s=eurjpy&i=d&t=c&a=ln&z=224&ft=20251204&l=234&d=1&ch=0&f=1&lt=56&r=0&o=1) | python run -c EURJPY --wedge-lines --wedge-upper-start 2026-04-30,187.539 --wedge-upper-end 2026-06-17,186.318 --wedge-lower-start 2026-05-06,182.059 --wedge-lower-end 2026-06-24,183.172 --wedge-right | ✅ | 2026-07-20 | 2026-07-20 |


Źródło danych CSV instrumentów: /app/data/csv
