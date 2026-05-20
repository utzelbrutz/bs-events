import requests
import json
import re
from datetime import datetime

BASE = "https://braunschweig.die-region.de"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# AJAX-Endpunkt der die-region.de — gibt JSON zurück, kein cHash nötig
AJAX_URL = (
    f"{BASE}/?tx_gcevents_eventlisting%5Baction%5D=list"
    f"&tx_gcevents_eventlisting%5Bcontroller%5D=Event"
    f"&tx_gcevents_eventlisting%5BcUid%5D=27111"
    f"&tx_gcevents_eventlisting%5BdayFlag%5D=0"
    f"&tx_gcevents_eventlisting%5Bmore%5D={{more}}"
    f"&tx_gcevents_eventlisting%5Bstartdate%5D={{startdate}}"
    f"&type=672342022"
)

MONATE = {
    "januar":1,"februar":2,"märz":3,"april":4,"mai":5,"juni":6,
    "juli":7,"august":8,"september":9,"oktober":10,"november":11,"dezember":12
}

KATEGORIE_MAP = {
    "konzert":"Musik","musik":"Musik","band":"Musik","jazz":"Musik","rock":"Musik",
    "chor":"Musik","orchester":"Musik","festival":"Markt & Fest",
    "theater":"Theater","schauspiel":"Theater","oper":"Theater","tanz":"Theater",
    "comedy":"Theater","ballett":"Theater","kabarett":"Theater",
    "film":"Kino","kino":"Kino","filmvorführung":"Kino","premiere":"Kino",
    "ausstellung":"Ausstellung","galerie":"Ausstellung","museum":"Ausstellung",
    "vernissage":"Ausstellung","kunst":"Ausstellung",
    "sport":"Sport","fußball":"Sport","marathon":"Sport","turnier":"Sport","lauf":"Sport",
    "vortrag":"Vortrag","lesung":"Vortrag","diskussion":"Vortrag","salon":"Vortrag",
    "seminar":"Vortrag","workshop":"Vortrag","konferenz":"Vortrag",
    "markt":"Markt & Fest","fest":"Markt & Fest","flohmarkt":"Markt & Fest",
    "messe":"Markt & Fest","street food":"Markt & Fest",
    "führung":"Führung & Tour","stadtführung":"Führung & Tour","tour":"Führung & Tour",
    "kinder":"Familie","familie":"Familie","jugend":"Familie","kinderprogramm":"Familie",
}


def kategorie(titel):
    t = titel.lower()
    for k, v in KATEGORIE_MAP.items():
        if k in t:
            return v
    return "Sonstiges"


def parse_datum(startdate_str):
    """Parst '20.Mai' oder '20. Mai' → ISO-Datum."""
    if not startdate_str:
        return None
    m = re.search(r"(\d{1,2})\.\s*(\w+)", startdate_str.strip())
    if m:
        tag = int(m.group(1))
        monat = MONATE.get(m.group(2).lower())
        if monat:
            jahr = datetime.now().year
            # Wenn Monat bereits vergangen → nächstes Jahr
            if monat < datetime.now().month:
                jahr += 1
            try:
                return datetime(jahr, monat, tag).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None


def scrape_die_region(max_seiten=20):
    startdate = datetime.now().strftime("%Y-%m-%d")
    print(f"Scraping: die-region.de API (ab {startdate})")

    events = []
    page_size = 8   # Mindestanzahl echter Events zum Weitermachen (API hat Metadata-Felder)

    for seite in range(max_seiten):
        more = seite * page_size
        url = AJAX_URL.format(more=more, startdate=startdate)

        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"  Seite {seite+1} Fehler: {e}")
            break

        if not data:
            break

        found = 0
        items_iter = data.values() if isinstance(data, dict) else data
        for item in items_iter:
            if not isinstance(item, dict):
                continue
            titel = item.get("title", "").strip()
            if not titel:
                continue

            start_date_raw = item.get("startDate", "")
            href = item.get("uri", "")
            if href.startswith("/"):
                href = BASE + href

            events.append({
                "titel":       titel,
                "beschreibung": item.get("teaser") or item.get("subtitle") or None,
                "datum":       parse_datum(start_date_raw),
                "datum_text":  start_date_raw,
                "startzeit":   item.get("startTime") or None,
                "endzeit":     item.get("endTime") or None,
                "ort":         (item.get("city") or "").split(",")[0].strip() or None,
                "link":        href,
                "quelle":      "die-region.de",
                "kategorie":   kategorie(titel),
            })
            found += 1

        print(f"  Seite {seite+1} (offset {more}): {found} Events")

        if found < page_size:
            break  # letzte Seite erreicht

    # Deduplizieren nach Titel+Datum
    gesehen = set()
    result = []
    for e in events:
        key = (e["titel"].lower().strip(), e.get("datum") or "")
        if key not in gesehen:
            gesehen.add(key)
            result.append(e)

    print(f"  Gesamt: {len(result)} Events")
    return result


if __name__ == "__main__":
    events = scrape_die_region()
    with open("events_region.json", "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
    print("\n--- Vorschau (erste 10) ---")
    for e in events[:10]:
        print(f"  {e.get('datum','?'):12} {str(e.get('startzeit') or '?'):6} "
              f"| {e['kategorie']:15} | {e['titel'][:45]}")
