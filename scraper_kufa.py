"""
Scraper für KufA Haus Braunschweig (kufa.haus)
Strategie:
  1. WP REST API: alle ajde_events-Posts in einem Aufruf
  2. Für jeden Post: JSON-LD auf der Event-Seite → exaktes Datum + Uhrzeit
"""
import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "de-DE,de;q=0.9",
}

# EventOn-Taxonomie-IDs → Kategorie
EVENT_TYPE_MAP = {
    5:   "Musik",       # Konzert
    6:   "Party",       # Party
    7:   "Vortrag",     # Lesung
    8:   "Theater",     # Theater
    9:   "Sonstiges",   # Anderes
    10:  "Musik",       # Jam Session
    148: "Theater",     # Tanz
    150: "Ausstellung", # Finissage
    154: "Vortrag",     # Workshop
    187: "Ausstellung", # Vernissage
    197: "Sonstiges",   # Essen & Trinken
}


def _parse_jsonld_date(startdate_str):
    """
    Parst EventOn-JSON-LD-Datumsformat: '2026-6-30T18:30+2:00'
    Gibt (datum_str, zeit_str) als ('YYYY-MM-DD', 'HH:MM') zurück.
    """
    if not startdate_str:
        return None, None
    # Zeitzone abschneiden, dann parsen
    # Format: 2026-6-30T18:30+2:00  oder  2026-06-30T18:30:00+02:00
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})T(\d{1,2}):(\d{2})", startdate_str)
    if m:
        jahr, monat, tag, std, minute = [int(x) for x in m.groups()]
        try:
            dt = datetime(jahr, monat, tag, std, minute)
            return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
        except ValueError:
            pass
    return None, None


def _fetch_event_details(post):
    """
    Holt die Event-Seite und extrahiert Datum/Zeit aus JSON-LD schema.org.
    Gibt ein fertiges Event-Dict zurück oder None.
    """
    url   = post.get("link", "")
    titel = post.get("title", {}).get("rendered", "").strip()
    # HTML-Entities dekodieren
    titel = BeautifulSoup(titel, "lxml").get_text()

    event_type_ids = post.get("event_type", [])
    kategorie = "Sonstiges"
    for tid in event_type_ids:
        if tid in EVENT_TYPE_MAP:
            kategorie = EVENT_TYPE_MAP[tid]
            break

    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        r.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(r.content, "lxml")

    # JSON-LD suchen
    datum, zeit = None, None
    enddatum, endzeit = None, None
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if data.get("@type") == "Event":
                datum, zeit   = _parse_jsonld_date(data.get("startDate"))
                enddatum, endzeit = _parse_jsonld_date(data.get("endDate"))
                break
        except (json.JSONDecodeError, AttributeError):
            pass

    # Fallback: evoet_dayblock im HTML
    if not datum:
        span = soup.find("span", class_="evoet_dayblock")
        if span:
            d = span.find("em", class_="date")
            m = span.find("em", class_="month")
            t = span.find("em", class_="time")
            yr = span.get("data-syr")
            MONATE = {"jan":1,"feb":2,"mär":3,"mar":3,"apr":4,"mai":5,"jun":6,
                      "jul":7,"aug":8,"sep":9,"okt":10,"nov":11,"dez":12}
            if d and m and yr:
                mon = MONATE.get(m.get_text(strip=True).lower())
                try:
                    datum = datetime(int(yr), mon, int(d.get_text(strip=True))).strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    pass
            if t:
                zeit = t.get_text(strip=True)

    # Nur zukünftige Events behalten
    if datum:
        try:
            if datetime.strptime(datum, "%Y-%m-%d").date() < datetime.now().date():
                return None  # vergangenes Event überspringen
        except ValueError:
            pass

    if not titel or len(titel) < 2:
        return None

    return {
        "titel":       titel,
        "beschreibung": None,
        "datum":       datum,
        "datum_text":  None,
        "startzeit":   zeit,
        "endzeit":     endzeit if enddatum == datum else None,
        "ort":         "KufA Haus Braunschweig",
        "link":        url,
        "quelle":      "kufa.haus",
        "kategorie":   kategorie,
    }


def scrape_kufa():
    print("Scraping: kufa.haus (WP REST API + JSON-LD)")

    # 1) Alle Event-Posts über WP REST API
    api_url = "https://kufa.haus/wp-json/wp/v2/ajde_events"
    try:
        r = requests.get(
            api_url,
            params={"per_page": 100, "status": "publish",
                    "_fields": "id,slug,link,title,event_type"},
            headers=HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        posts = r.json()
    except requests.RequestException as e:
        print(f"  API-Fehler: {e}")
        return []

    if not isinstance(posts, list):
        print(f"  Unerwartete Antwort: {str(posts)[:200]}")
        return []

    print(f"  {len(posts)} Posts gefunden — lade Event-Seiten ...")

    # 2) Parallel die Event-Seiten abrufen
    events = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_event_details, p): p for p in posts}
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                events.append(result)

    # Sortieren nach Datum
    events.sort(key=lambda e: (e.get("datum") or "9999", e.get("startzeit") or ""))

    print(f"  {len(events)} zukünftige Events")
    return events


if __name__ == "__main__":
    import sys
    events = scrape_kufa()
    with open("events_kufa.json", "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
    for e in events[:10]:
        print(f"  {e.get('datum','?')} {e.get('startzeit','?'):6} | {e['titel'][:50]} [{e['kategorie']}]")
