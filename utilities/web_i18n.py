from __future__ import annotations

import json


# Product names, symbols, currencies, and established market vocabulary (for
# example Ichimoku, Fibo, Stooq, Long and Short) intentionally stay unchanged.
POLISH_TRANSLATIONS = {
    "StockHelper Scanner Report": "Raport skanera StockHelper",
    "StockHelper scanner workspace": "Panel skanera StockHelper",
    "StockHelper Transaction Journal": "Dziennik transakcji StockHelper",
    "Generated:": "Wygenerowano:",
    "Search": "Szukaj",
    "Market": "Rynek",
    "Direction": "Kierunek",
    "Status": "Status",
    "Favorites": "Ulubione",
    "Open journal": "Otwórz dziennik",
    "Show": "Pokaż",
    "Hide": "Ukryj",
    "Legends": "Legendy",
    "Checked": "Sprawdzone",
    "Current balance": "Aktualny kapitał",
    "Top choices": "Najlepsze wybory",
    "Why top choice": "Dlaczego wybrano",
    "Instrument": "Instrument",
    "Chart": "Wykres",
    "Open chart": "Otwórz wykres",
    "Wedges": "Kliny",
    "All markets": "Wszystkie rynki",
    "All results": "Wszystkie wyniki",
    "Ichimoku only": "Tylko Ichimoku",
    "Fibo only": "Tylko Fibo",
    "No results.": "Brak wyników.",
    "Sort": "Sortuj",
    "Close": "Zamknij",
    "Open": "Otwarte",
    "Closed": "Zamknięte",
    "Profit": "Zysk",
    "Loss": "Strata",
    "Transactions": "Transakcje",
    "Estimated P/L": "Szacowany Z/S",
    "Year": "Rok",
    "All years": "Wszystkie lata",
    "Compress all": "Zwiń wszystko",
    "Expand all": "Rozwiń wszystko",
    "Delete selected": "Usuń wybrane",
    "Delete all": "Usuń wszystko",
    "Download PDF": "Pobierz PDF",
    "Entry screenshot": "Zrzut wejścia",
    "Close screenshot": "Zrzut zamknięcia",
    "No screenshot": "Brak zrzutu",
    "Position summary": "Podsumowanie pozycji",
    "Trade review": "Ocena transakcji",
    "Edit transaction": "Edytuj transakcję",
    "Notes": "Notatki",
    "Amount": "Liczba",
    "Entry": "Wejście",
    "Stop loss": "Stop loss",
    "Exit price": "Cena wyjścia",
    "Outcome": "Wynik",
    "Reason": "Powód",
    "Touches": "Dotknięcia",
    "Update": "Aktualizuj",
    "Delete": "Usuń",
    "Save": "Zapisz",
    "Cancel": "Anuluj",
    "Select level": "Wybierz poziom",
    "Position calculator": "Kalkulator pozycji",
    "Calculate": "Oblicz",
    "Capital": "Kapitał",
    "Risk": "Ryzyko",
    "Entry price": "Cena wejścia",
    "Take profit": "Take profit",
    "Reset all": "Resetuj wszystko",
    "Delete object": "Usuń obiekt",
    "Download chart PNG": "Pobierz wykres PNG",
    "Find new wedge": "Znajdź nowy klin",
    "Instrument universe is unavailable for this saved report.": "Lista instrumentów jest niedostępna dla zapisanego raportu.",
    "Instruments checked for this report": "Instrumenty sprawdzone w tym raporcie",
    "Show recent dropouts": "Pokaż ostatnie odrzucone",
    "Hide recent dropouts": "Ukryj ostatnie odrzucone",
    "Saved by me": "Zapisane przeze mnie",
    "Show all": "Pokaż wszystkie",
    "Name only": "Tylko nazwa",
    "Default": "Domyślne",
    "Full": "Pełne",
    "Ticker": "Ticker",
    "Dir": "Kier.",
    "Position": "Pozycja",
    "Previous": "Poprzednia",
    "Price to cloud": "Cena względem chmury",
    "Candles": "Świece",
    "Mo.": "Mies.",
    "Start": "Początek",
    "Close price": "Cena zamknięcia",
    "Retest count": "Liczba retestów",
    "Latest retest date": "Data ostatniego retestu",
    "Latest retest pattern": "Formacja ostatniego retestu",
    "Latest Retest date": "Data ostatniego retestu",
    "Latest Retest pattern": "Formacja ostatniego retestu",
    "Latest Retest status": "Status ostatniego retestu",
    "Valid retests from": "Ważne retesty od",
    "Qualification status": "Status kwalifikacji",
    "Previous respect months": "Miesiące wcześniejszego respektowania",
    "Risk level": "Poziom ryzyka",
    "Dynamic status": "Status dynamiczny",
    "Cloud status": "Status chmury",
    "Tenkan in cloud": "Tenkan w chmurze",
    "Python command": "Polecenie Python",
    "Latest date": "Najnowsza data",
    "Expected date": "Oczekiwana data",
    "Latest data?": "Aktualne dane?",
    "Breakout date": "Data wybicia",
    "Breakout direction": "Kierunek wybicia",
    "Upper line": "Górna linia",
    "Lower line": "Dolna linia",
    "Upper touches": "Górne dotknięcia",
    "Lower touches": "Dolne dotknięcia",
    "Days": "Dni",
    "Months": "Miesiące",
    "Pattern": "Formacja",
    "Incline": "Wzrost",
    "Waiting": "Oczekujące",
    "Ratio": "Stosunek",
    "Near 61.8": "Blisko 61,8",
    "Touched 61.8 date": "Data dotknięcia 61,8",
    "Wedge": "Klin",
    "Start width": "Szerokość początkowa",
    "End width": "Szerokość końcowa",
    "Slope": "Nachylenie",
    "Score": "Ocena",
    "Saved by user": "Zapisane przez użytkownika",
}

ENGLISH_NORMALIZATIONS = {
    "WYNIKI": "RESULTS",
    "Kliny": "Wedges",
    "Legenda progów": "Threshold legend",
    "Brak wyników.": "No results.",
    "poza chmurą, z warunkami płynności": "outside the cloud, with liquidity conditions",
    "po flipie chmury: retest/pattern po wybiciu": "after cloud flip: retest/pattern after breakout",
    "próg płynności": "liquidity threshold",
    "ostatnie 10 świeczek": "last 10 candles",
    "mnożnik PKB kraju": "country GDP multiplier",
    "mnożnik kraju": "country multiplier",
    "liczba dni z ostatnich 20 poniżej progu": "number of days in the last 20 below the threshold",
    "Nie może być więcej niż 2 dni.": "There cannot be more than 2 days.",
    "Pozycja": "Position",
    "Poprzednia": "Previous",
    "Świece": "Candles",
    "Mies.": "Mo.",
    "Data wybicia": "Breakout date",
    "Mies. od wybicia": "Months since breakout",
    "Mies. respektu przed wybiciem": "Previous respect months",
}


def language_controls_html() -> str:
    """Return reusable EN/PL controls and runtime for generated web views."""
    translations = json.dumps(POLISH_TRANSLATIONS, ensure_ascii=False)
    normalizations = json.dumps(ENGLISH_NORMALIZATIONS, ensure_ascii=False)
    return f"""
<style>
.stockhelper-language-switcher{{position:fixed;top:12px;right:14px;z-index:2147483647;display:flex;gap:6px;padding:5px;border:1px solid rgba(148,163,184,.45);border-radius:12px;background:rgba(15,23,42,.92);box-shadow:0 8px 24px rgba(0,0,0,.3);backdrop-filter:blur(8px)}}
.stockhelper-language-switcher button{{min-width:42px;padding:6px 8px;border:1px solid transparent;border-radius:8px;background:transparent;color:#cbd5e1;cursor:pointer;font:700 14px/1.2 Inter,system-ui,sans-serif}}
.stockhelper-language-switcher button.active{{border-color:#60a5fa;background:#1d4ed8;color:#fff}}
</style>
<nav class="stockhelper-language-switcher" aria-label="Language / Język">
  <button type="button" data-stockhelper-language="en" aria-label="English" title="English">🇬🇧 EN</button>
  <button type="button" data-stockhelper-language="pl" aria-label="Polski" title="Polski">🇵🇱 PL</button>
</nav>
<script>
(()=>{{
const PL={translations};
const TO_EN={normalizations};
const ATTRS=['title','aria-label','placeholder'];
let language='en',translating=false;
function translate(value){{
  if(!value)return value;
  let output=value;
  Object.entries(TO_EN).sort((a,b)=>b[0].length-a[0].length).forEach(([source,en])=>output=output.replaceAll(source,en));
  if(language!=='pl')return output;
  Object.entries(PL).sort((a,b)=>b[0].length-a[0].length).forEach(([en,pl])=>{{
    output=output.replaceAll(en,pl);
  }});
  return output;
}}
function translateNode(root){{
  if(!root||root.closest?.('[data-market-language],script,style'))return;
  const nodes=[];
  if(root.nodeType===Node.TEXT_NODE)nodes.push(root);
  else{{const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let node;while((node=walker.nextNode()))nodes.push(node);}}
  nodes.forEach(node=>{{
    if(node.parentElement?.closest('script,style,[data-market-language]'))return;
    if(node.__stockhelperEnglish===undefined)node.__stockhelperEnglish=node.nodeValue;
    node.nodeValue=translate(node.__stockhelperEnglish);
  }});
  if(root.querySelectorAll){{[root,...root.querySelectorAll('*')].forEach(el=>ATTRS.forEach(attr=>{{
    if(!el.hasAttribute?.(attr)||el.closest('[data-market-language]'))return;
    const key='stockhelperEnglish'+attr.replace('-','');
    if(el.dataset[key]===undefined)el.dataset[key]=el.getAttribute(attr)||'';
    el.setAttribute(attr,translate(el.dataset[key]));
  }}));}}
}}
window.setStockhelperLanguage=lang=>{{
  language=lang==='pl'?'pl':'en';translating=true;
  document.documentElement.lang=language;
  document.querySelectorAll('[data-stockhelper-language]').forEach(btn=>btn.classList.toggle('active',btn.dataset.stockhelperLanguage===language));
  translateNode(document.body);translating=false;
}};
document.querySelectorAll('[data-stockhelper-language]').forEach(btn=>btn.addEventListener('click',()=>window.setStockhelperLanguage(btn.dataset.stockhelperLanguage)));
new MutationObserver(changes=>{{if(translating)return;translating=true;changes.forEach(change=>change.addedNodes.forEach(translateNode));translating=false;}}).observe(document.body,{{childList:true,subtree:true}});
window.setStockhelperLanguage('en');
}})();
</script>"""
