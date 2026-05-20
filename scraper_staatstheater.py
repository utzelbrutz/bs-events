import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

BASE = "https://www.staatstheater-braunschweig.de"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
           "Accept-Language": "de-DE,de;q=0.9"}

MONATE = {
    "jan": 1, "feb": 2, "mär": 3, "mar": 3, "apr": 4,
    "mai": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "okt": 10, "nov": 11, "dez": 12,
    "januar": 1, "februar": 2, "märz": 3, "april": 4,
    "juni": 6, "juli": 7, "august": 8,
    "september": 9, "oktober": 10, "november": 11, "dezember": 12
}

SPARTEN = {
    "oper": "Musik", "operette": "Musik", "konzert": "Musik", "sinfoniekonzert": "Musik",
    "kammerkonzert": "Musik", "liederabend": "Musik",
    "schauspiel": "Theater", "theater": "Theater", "komödie": "Theater",
    "tragödie": "Theater", "uraufführung": "Theater",
    "ballett": "Theater", "tanz": "Theater",
    "kinder": "Familie", "jugend": "Familie", "familienvorstellung": "Familie",
}


def kategorie_aus_sparte(text):
    t = text.lower()
    for k, v in SPARTEN.items():
        if k in t:
            return v
    return "Theater"


def parse_datum(text):
    if not text:
        return None
    text = text.strip().lower()
    m = re.search(r"(\d{1,2})[.\s]+(\w+)(?:[.\s]+(\d{4}))?", text)
    if m:
        tag, monat_str, jahr_str = m.group(1), m.group(2)[:3], m.group(3)
        monat = MONATE.get(monat_str)
        if monat:
            jahr = int(jahr_str) if jahr_str and len(jahr_str) == 4 else datetime.now().year
            try:
                return datetime(jahr, monat, int(tag)).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None


def parse_zeit(text):
    if not text:
        return None
    m = re.search(r"(\d{1,2})[.:](\d{2})\s*(?:Uhr)?", text)
    return f"{m.group(1).zfill(2)}:{m.group(2)}" if m else None


def scrape_staatstheater():
    url = f"{BASE}/spielplan/"
    print(f"Scraping: {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  Fehler: {e}")
        return []

    soup = BeautifulSoup(r.content, "lxml")
    events = []

    # Staatstheater-Braunschweig nutzt TYPO3 mit typischen Klassen
    # Strategie 1: spielplan-spezifische Selektoren
    kandidaten = (
        soup.select(".tx-bs-spielplan__item, .spielplan-item, .event-item")
        or soup.select("article.event, article.spielplan")
        or soup.select(".list-item, .production-item, .programme-item")
        or soup.select("article")
    )

    for item in kandidaten:
        titel_el = (item.select_one(".event-title, .spielplan__title, h2, h3, .title, .headline")
                    or item.select_one("[class*='title'], [class*='headline']"))
        datum_el = (item.select_one(".event-date, .spielplan__date, .date, time, [datetime]")
                    or item.select_one("[class*='date'], [class*='datum']"))
        zeit_el  = (item.select_one(".event-time, .spielplan__time, .time, .uhrzeit")
                    or item.select_one("[class*='time'], [class*='uhr']"))
        sparte_el = item.select_one(".sparte, .genre, .kategorie, [class*='sparte']")
        link_el   = item.select_one("a[href]")

        titel  = titel_el.get_text(strip=True) if titel_el else None
        datum  = parse_datum(datum_el.get_text(strip=True) if datum_el else None)
        zeit   = (parse_zeit(zeit_el.get_text(strip=True)) if zeit_el
                  else parse_zeit(datum_el.get_text(strip=True) if datum_el else None))
        sparte = sparte_el.get_text(strip=True) if sparte_el else ""

        href = link_el.get("href") if link_el else None
        if href and href.startswith("/"):
            href = BASE + href

        if titel and len(titel) > 3:
            events.append({
                "titel": titel,
                "beschreibung": sparte or None,
                "datum": datum,
                "datum_text": None,
                "startzeit": zeit,
                "endzeit": None,
                "ort": "Staatstheater Braunschweig",
                "link": href,
                "quelle": "staatstheater-braunschweig.de",
                "kategorie": kategorie_aus_sparte(sparte or titel)
            })

    print(f"  {len(events)} Events gefunden")
    return events


def debug():
    """Zeigt Seitenstruktur zur Anpassung der Selektoren."""
    url = f"{BASE}/spielplan/"
    r = requests.get(url, headers=HEADERS, timeout=12)
    soup = BeautifulSoup(r.content, "lxml")
    print(f"Titel: {soup.title.string if soup.title else 'kein Titel'}")
    print(f"Status: {r.status_code}")

    print("\nKlassen mit 'spielplan', 'event', 'production':")
    klassen = set()
    for t in soup.find_all(class_=True):
        for c in t.get("class", []):
            if any(x in c.lower() for x in ["spielplan", "event", "production", "item", "programme"]):
                klassen.add(f"{t.name}.{c}")
    for k in sorted(klassen)[:20]:
        print(f"  {k}")

    print("\nErste 3 <article>:")
    for a in soup.select("article")[:3]:
        print(f"  {a.get_text(separator=' | ', strip=True)[:150]}")


if __name__ == "__main__":
    import sys
    if "--debug" in sys.argv:
        debug()
    else:
        events = scrape_staatstheater()
        with open("events_staatstheater.json", "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
        for e in events[:5]:
            print(f"  {e.get('datum','?')} {e.get('startzeit','?')} | {e['titel'][:50]}")
