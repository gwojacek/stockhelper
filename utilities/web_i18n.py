from __future__ import annotations

import json


# Product names, symbols, currencies, and indicator names (for example
# Ichimoku, Fibo, and Stooq) stay unchanged; descriptive statuses and position
# directions are localized.
POLISH_TRANSLATIONS = {
    "StockHelper Scanner Report": "Raport skanera StockHelper",
    "StockHelper scanner workspace": "Panel skanera StockHelper",
    "Ichimoku continuation": "Kontynuacja Ichimoku",
    "Ichimoku reversal": "Odwrócenie Ichimoku",
    "Ichimoku status": "Status Ichimoku",
    "StockHelper Transaction Journal": "Dziennik transakcji StockHelper",
    "Generated:": "Wygenerowano:",
    "Search": "Szukaj",
    "Market": "Rynek",
    "Scanner": "Skaner",
    "Direction": "Kierunek",
    "Status": "Status",
    "Favorites": "Ulubione",
    "Open journal": "Otwórz dziennik",
    "Show": "Pokaż",
    "Hide": "Ukryj",
    "📈 Show": "📈 Pokaż",
    "📈 Hide": "📈 Ukryj",
    "Legends": "Legendy",
    "Ichimoku legend": "Legenda Ichimoku",
    "Threshold legend": "Legenda progów",
    "Liquidity legend": "Legenda płynności",
    "liquidity threshold": "próg płynności",
    "last 10 candles": "ostatnie 10 świec",
    "country GDP multiplier": "mnożnik PKB kraju",
    "country multiplier": "mnożnik kraju",
    "base": "wartość bazowa",
    "base 500 000 PLN": "wartość bazowa 500 000 PLN",
    "number of days in the last 20 below the threshold": "liczba dni z ostatnich 20 poniżej progu",
    "There cannot be more than 2 days.": "Nie mogą wystąpić więcej niż 2 takie dni.",
    "Checked": "Sprawdzone",
    "Current balance": "Aktualny kapitał",
    "Top choices": "Najlepsze wybory",
    "Trade Summary": "Podsumowanie transakcji",
    "RESULTS": "WYNIKI",
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
    "Closing Price": "Cena zamknięcia",
    "Close Price": "Cena zamknięcia",
    "Close position": "Zamknij pozycję",
    "Save & Close": "Zapisz i zamknij",
    "Open": "Otwarte",
    "Closed": "Zamknięte",
    "completed · loss": "zamknięta · strata",
    "completed · profit": "zamknięta · zysk",
    "completed · pending": "zamknięta · oczekująca",
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
    "Position Value": "Wartość pozycji",
    "Position type": "Kierunek pozycji",
    "Position size": "Wielkość pozycji",
    "Position Size": "Wielkość pozycji",
    "Position calculation": "Obliczenie pozycji",
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
    "Interactive Level Selector": "Interaktywny wybór poziomów",
    "Line tool": "Narzędzie linii",
    "Line color": "Kolor linii",
    "Reset scanner": "Resetuj skaner",
    "Reset scanner drawings": "Resetuj rysunki skanera",
    "Selected values": "Wybrane wartości",
    "Manual inputs": "Dane ręczne",
    "Position calculator": "Kalkulator pozycji",
    "Calculate": "Oblicz",
    "Calculate position": "Oblicz pozycję",
    "Capital": "Kapitał",
    "Risk": "Ryzyko",
    "Entry price": "Cena wejścia",
    "Take profit": "Take profit",
    "Engaged capital": "Zaangażowany kapitał",
    "Engaged Capital": "Zaangażowany kapitał",
    "Potential loss with spread": "Potencjalna strata ze spreadem",
    "Potential Loss With Spread": "Potencjalna strata ze spreadem",
    "Loss %": "Strata %",
    "Reset all": "Resetuj wszystko",
    "Delete object": "Usuń obiekt",
    "Download chart PNG": "Pobierz wykres PNG",
    "Find new wedge": "Znajdź nowy klin",
    "Delete selected object": "Usuń wybrany obiekt",
    "Quick charts from": "Szybkie wykresy z",
    "Filter charts": "Filtruj wykresy",
    "Open another instrument": "Otwórz inny instrument",
    "Instrument type": "Typ instrumentu",
    "Source": "Źródło",
    "Setup information": "Informacje o układzie",
    "Add journal entry": "Dodaj wpis do dziennika",
    "Transaction journal": "Dziennik transakcji",
    "Transaction amount": "Wartość transakcji",
    "Notes / why entry": "Notatki / powód wejścia",
    "Save journal + screenshot": "Zapisz dziennik i zrzut",
    "Calculation currency": "Waluta obliczeń",
    "Lot cost": "Koszt lota",
    "Pip value": "Wartość pipsa",
    "Spread multiplier": "Mnożnik spreadu",
    "Setup": "Układ",
    "Technique": "Technika",
    "Manual": "Ręczne",
    "CFD mode": "Tryb CFD",
    "Name / Ticker": "Nazwa / ticker",
    "Current": "Obecnie",
    "Last": "Ostatni",
    "Sold / Close": "Sprzedaż / zamknięcie",
    "Chart - Opened Position": "Wykres – otwarta pozycja",
    "Chart - Closed Position": "Wykres – zamknięta pozycja",
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
    "Dir": "Kierunek",
    "Dir.": "Kierunek",
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
    "Months since breakout": "Miesiące od wybicia",
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
    "Waiting 23.6→61.8 and patterns": "Oczekiwanie 23,6→61,8 i formacje",
    "Steep incline / no major bearish signal": "Stromy wzrost / brak istotnego sygnału spadkowego",
    "Pattern ≤14d / SL intact": "Formacja ≤14 dni / SL nienaruszony",
    "Recent dropouts": "Ostatnio odrzucone",
    "Ratio": "Stosunek",
    "Near 61.8": "Blisko 61,8",
    "Touched 61.8 date": "Data dotknięcia 61,8",
    "Wedge": "Klin",
    "Falling wedge": "Klin opadający",
    "Start width": "Szerokość początkowa",
    "End width": "Szerokość końcowa",
    "Slope": "Nachylenie",
    "Score": "Ocena",
    "Saved by user": "Zapisane przez użytkownika",
    "Fibo information": "Informacje Fibo",
    "after cloud flip: retest/pattern after breakout": "po zmianie strony chmury: retest/formacja po wybiciu",
    "outside the cloud, with liquidity conditions": "poza chmurą, z warunkami płynności",
    "Max capital engagement": "Maksymalne zaangażowanie kapitału",
    "Max capital to engage": "Maksymalny kapitał do zaangażowania",
    "Max capital": "Maksymalny kapitał",
    "10-day average turnover": "10-dniowego średniego obrotu",
    "1% of 10-day average turnover": "1% z 10-dniowego średniego obrotu",
    "NO PLAY UNTIL": "BEZ TRANSAKCJI DO",
    "Strong / continuation": "Silny sygnał / kontynuacja",
    "Kijun / watch": "Kijun / obserwacja",
    "Cloud / retest / breakout": "Chmura / retest / wybicie",
    "Cloud/retest/breakout rows have priority and appear in the third column.": "Wiersze chmury/retestu/wybicia mają pierwszeństwo i znajdują się w trzeciej kolumnie.",
    "Early breakouts are hidden from 3P Ichimoku until four months after the preceding breakout; afterward they return and are treated normally.": "Wczesne wybicia są ukryte w 3P Ichimoku przez cztery miesiące od poprzedniego wybicia; później wracają i są traktowane standardowo.",
    "Risk/grading details are shown only in the": "Szczegóły ryzyka i oceny są wyświetlane tylko w kolumnach",
    "Risk icons": "Ikony ryzyka",
    "number of days in the last 20 below the Ichimoku liquidity threshold; no more than 2 days are allowed.": "liczba dni z ostatnich 20 poniżej progu płynności Ichimoku; dozwolone są najwyżej 2 dni.",
    "Chikou uses arrow-only direction": "Kierunek Chikou jest oznaczany wyłącznie strzałką",
    "over price and": "nad ceną, a",
    "under price": "pod ceną",
    "TK values use the latest actionable Tenkan/Kijun direction": "Wartości TK używają najnowszego aktywnego kierunku Tenkan/Kijun",
    "with neutral only when equal": "neutralnego tylko przy równości",
    "placement is context-aware": "położenie zależy od kontekstu",
    "Tenkan is inside the cloud": "Tenkan znajduje się w chmurze",
    "kumo color is the projected cloud to the right of the latest candle": "kolor kumo oznacza prognozowaną chmurę na prawo od ostatniej świecy",
    "lines are qualitative context only": "linie stanowią wyłącznie kontekst jakościowy",
    "is the current scanner status/note; missing source fields stay as": "oznacza bieżący status/uwagę skanera; brakujące pola źródłowe pozostają jako",
    "Recent breakout": "Ostatnie wybicie",
    "Breakout": "Wybicie",
    "breakout": "wybicie",
    "Retest": "Retest",
    "Above the cloud": "Nad chmurą",
    "Below the cloud": "Pod chmurą",
    "Above": "Nad chmurą",
    "Below": "Pod chmurą",
    "above": "nad chmurą",
    "below": "pod chmurą",
    "Inside the cloud": "W chmurze",
    "Inside the cloud - PATTERN!": "W chmurze – FORMACJA!",
    "PATTERN!": "FORMACJA!",
    "Touched the cloud": "Dotknięcie chmury",
    "Over Kijun-sen": "Nad Kijun-sen",
    "Under Kijun-sen": "Pod Kijun-sen",
    "Touched Kijun-sen": "Dotknięcie Kijun-sen",
    "Unsuccessful breakout to the other side": "Nieudane wybicie na drugą stronę",
    "Returned to cloud waiting for pattern": "Powrót do chmury – oczekiwanie na formację",
    "Breakout confirmed": "Wybicie potwierdzone",
    "breakout_confirmed": "wybicie_potwierdzone",
    "medium_retest_pattern": "średni_retest_z_formacją",
    "returned_to_cloud_waiting_for_pattern": "powrót_do_chmury_oczekiwanie_na_formację",
    "Waiting for pattern": "Oczekiwanie na formację",
    "Valid reversal": "Prawidłowe odwrócenie",
    "Strong trend": "Silny trend",
    "Long trend": "Długotrwały trend",
    "Short trend": "Krótkotrwały trend",
    "Latest retest": "Ostatni retest",
    "Last valid retest": "Ostatni prawidłowy retest",
    "No major bearish signal": "Brak istotnego sygnału spadkowego",
    "3p_steep_incline": "3P_stromy_wzrost",
    "3p_steep_decline": "3P_stromy_spadek",
    "3P steep incline": "3P stromy wzrost",
    "3P steep decline": "3P stromy spadek",
    "3p_steep_23_6_zone": "3P_stromy_wzrost_strefa_23,6",
    "reached_23_6_waiting_for_61_8": "osiągnięto_23,6_oczekiwanie_na_61,8",
    "returned_before_61_8": "powrót_przed_61,8",
    "returned_above_23_6": "powrót_nad_23,6",
    "returned_below_23_6": "powrót_pod_23,6",
    "touched_61_8_no_pattern": "dotknięto_61,8_brak_formacji",
    "valid_reversal": "prawidłowe_odwrócenie",
    "Bearish hammer": "Spadkowy młot",
    "Bullish hammer": "Młot",
    "Hammer": "Młot",
    "bearish_hammer": "spadkowy_młot",
    "bullish_hammer": "młot",
    "Bearish engulfing": "Objęcie bessy",
    "Bullish engulfing": "Objęcie hossy",
    "bearish_engulfing": "objęcie_bessy",
    "bullish_engulfing": "objęcie_hossy",
    "Shooting star": "Spadająca gwiazda",
    "shooting_star": "spadająca_gwiazda",
    "Morning star": "Gwiazda poranna",
    "Evening star": "Gwiazda wieczorna",
    "morning_star": "gwiazda_poranna",
    "evening_star": "gwiazda_wieczorna",
    "Morning doji star": "Gwiazda poranna doji",
    "Evening doji star": "Gwiazda wieczorna doji",
    "morning_doji_star": "gwiazda_poranna_doji",
    "evening_doji_star": "gwiazda_wieczorna_doji",
    "Piercing pattern": "Formacja przenikania",
    "piercing_pattern": "formacja_przenikania",
    "piercing_line": "formacja_przenikania",
    "bullish_piercing_line": "formacja_przenikania",
    "Bullish piercing line": "Formacja przenikania",
    "Bullish harami": "Harami prowzrostowe",
    "Bearish harami": "Harami prospadkowe",
    "bullish_harami": "harami_prowzrostowe",
    "bearish_harami": "harami_prospadkowe",
    "Dark cloud cover": "Zasłona ciemnej chmury",
    "dark_cloud_cover": "zasłona_ciemnej_chmury",
    "Fibo pattern": "Formacja Fibo",
    "Show 3P debug": "Pokaż diagnostykę 3P",
    "Hide 3P debug": "Ukryj diagnostykę 3P",
    "BULLISH": "WZROSTOWY",
    "BEARISH": "SPADKOWY",
    "FX conversion fee 1%": "Opłata za przewalutowanie 1%",
    "FX conversion fee 1%: OFF": "Opłata za przewalutowanie 1%: WYŁ.",
    "FX conversion fee 1%: ON": "Opłata za przewalutowanie 1%: WŁ.",
    "OFF": "WYŁ.",
    "ON": "WŁ.",
    "Bullish": "Wzrostowy",
    "Bearish": "Spadkowy",
    "bullish": "wzrostowy",
    "bearish": "spadkowy",
    "Long": "Długa",
    "Short": "Krótka",
    "LONG": "DŁUGA",
    "SHORT": "KRÓTKA",
    "long": "długa",
    "short": "krótka",
    "Shares": "Akcje",
    "Lots": "Loty",
    "shallow_retest_pattern": "płytki_retest_z_formacją",
    "deep_retest_pattern": "głęboki_retest_z_formacją",
    "Mild": "Łagodne",
    "Moderate": "Umiarkowane",
    "Strong": "Silne",
    "Very strong": "Bardzo silne",
    "mild": "łagodne",
    "moderate": "umiarkowane",
    "strong": "silne",
    "very strong": "bardzo silne",
}

COLUMN_POLISH_TRANSLATIONS = {
    "Dir": "Kierunek",
    "Dir.": "Kierunek",
    "Close": "Cena zamknięcia",
    "Open": "Cena otwarcia",
    "High": "Najwyższa cena",
    "Low": "Najniższa cena",
    "Current": "Obecnie",
    "Position": "Pozycja",
    "Direction": "Kierunek",
    "Mo.": "Mies.",
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


def language_controls_html(*, show_controls: bool = True) -> str:
    """Return reusable EN/PL controls and runtime for generated web views."""
    translations = json.dumps(POLISH_TRANSLATIONS, ensure_ascii=False)
    column_translations = json.dumps(COLUMN_POLISH_TRANSLATIONS, ensure_ascii=False)
    normalizations = json.dumps(ENGLISH_NORMALIZATIONS, ensure_ascii=False)
    controls = """<nav class="stockhelper-language-switcher" aria-label="Language / Język">
  <button type="button" data-stockhelper-language="en" aria-label="English" title="English">🇬🇧 EN</button>
  <button type="button" data-stockhelper-language="pl" aria-label="Polski" title="Polski">🇵🇱 PL</button>
</nav>""" if show_controls else ""
    return f"""
<style>
.stockhelper-language-switcher{{display:flex;gap:6px;width:max-content;margin:0 0 8px auto;padding:5px;border:1px solid rgba(148,163,184,.45);border-radius:12px;background:rgba(15,23,42,.92)}}
.stockhelper-language-switcher button{{min-width:42px;padding:6px 8px;border:1px solid transparent;border-radius:8px;background:transparent;color:#cbd5e1;cursor:pointer;font:700 14px/1.2 Inter,system-ui,sans-serif}}
.stockhelper-language-switcher button.active{{border-color:#60a5fa;background:#1d4ed8;color:#fff}}
.top-choice-compact .top-choice-direction{{width:92px!important;min-width:92px!important}}
.top-choice-compact th:nth-child(2),.top-choice-compact td:nth-child(2){{min-width:92px;font-size:13px!important;white-space:normal}}
.troj-table th,.troj-table td{{overflow-wrap:anywhere;word-break:normal}}
</style>
{controls}
<script>
(()=>{{
const PL={translations};
const COLUMN_PL={column_translations};
const TO_EN={normalizations};
const ATTRS=['title','aria-label','placeholder'];
let language='en',translating=false;
function savedLanguage(){{
  const cookie=document.cookie.split('; ').find(item=>item.startsWith('stockhelper-language='))?.split('=')[1];
  if(cookie==='en'||cookie==='pl')return cookie;
  try{{const stored=localStorage.getItem('stockhelper-language');if(stored==='en'||stored==='pl')return stored;}}catch(error){{}}
  return 'en';
}}
function rememberLanguage(value){{
  try{{localStorage.setItem('stockhelper-language',value);}}catch(error){{}}
  if(location.protocol!=='file:')document.cookie=`stockhelper-language=${{value}}; Max-Age=31536000; Path=/; SameSite=Lax`;
}}
function translate(value){{
  if(!value)return value;
  let output=value;
  Object.entries(TO_EN).sort((a,b)=>b[0].length-a[0].length).forEach(([source,en])=>output=output.replaceAll(source,en));
  if(language!=='pl')return output;
  Object.entries(PL).sort((a,b)=>b[0].length-a[0].length).forEach(([en,pl])=>{{
    if(en.length<=4&&output.trim()!==en)return;
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
    const original=node.__stockhelperEnglish;
    const direction=node.parentElement?.closest('[data-troj-direction]')?.dataset?.trojDirection;
    const directionalOriginal=direction==='short'
      ? original.replaceAll('3p_steep_incline','3p_steep_decline').replaceAll('3P steep incline','3P steep decline')
      : original;
    const trimmed=directionalOriginal.trim();
    const columnKey=trimmed.replace(/\\s*[↕↑↓]\\s*$/,'');
    if(language==='pl'&&node.parentElement?.closest('th')&&COLUMN_PL[columnKey]){{
      node.nodeValue=directionalOriginal.replace(columnKey,COLUMN_PL[columnKey]);
    }}else node.nodeValue=translate(directionalOriginal);
  }});
  if(root.querySelectorAll){{[root,...root.querySelectorAll('*')].forEach(el=>ATTRS.forEach(attr=>{{
    if(!el.hasAttribute?.(attr)||el.closest('[data-market-language]'))return;
    const key='stockhelperEnglish'+attr.replace('-','');
    if(el.dataset[key]===undefined)el.dataset[key]=el.getAttribute(attr)||'';
    el.setAttribute(attr,translate(el.dataset[key]));
  }}));}}
}}
window.setStockhelperLanguage=(lang,remember=true)=>{{
  language=lang==='pl'?'pl':'en';translating=true;
  if(remember)rememberLanguage(language);
  document.documentElement.lang=language;
  document.querySelectorAll('[data-stockhelper-language]').forEach(btn=>btn.classList.toggle('active',btn.dataset.stockhelperLanguage===language));
  translateNode(document.body);translating=false;
}};
const languageControls=document.querySelector('.stockhelper-language-switcher');
const reportHero=document.querySelector('.troj-hero');
if(languageControls&&reportHero)reportHero.parentNode.insertBefore(languageControls,reportHero);
document.querySelectorAll('[data-stockhelper-language]').forEach(btn=>btn.addEventListener('click',()=>window.setStockhelperLanguage(btn.dataset.stockhelperLanguage)));
new MutationObserver(changes=>{{if(translating)return;translating=true;changes.forEach(change=>change.addedNodes.forEach(translateNode));translating=false;}}).observe(document.body,{{childList:true,subtree:true}});
window.setStockhelperLanguage(savedLanguage(),false);
}})();
</script>"""
