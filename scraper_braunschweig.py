import requests
from bs4 import BeautifulSoup
import json

BASE_BS = "https://www.braunschweig.de"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def scrape_stadt_braunschweig():
    url = f"{BASE_BS}/kultur/veranstaltungen/start.php"
    print(f"Scraping: {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  Fehler: {e}")
        return []

    soup = BeautifulSoup(r.content, "lxml")
    events = []

    for art in soup.select("article"):
        title_el = art.select_one(".bs-teaser__headline")
        desc_el = art.select_one(".bs-teaser__abstract")
        parent_a = art.find_parent("a")
        inner_a = art.select_one("a")

        title = title_el.get_text(strip=True) if title_el else None
        desc = desc_el.get_text(strip=True) if desc_el else None

        href = None
        if parent_a:
            href = parent_a.get("href", "")
        elif inner_a:
            href = inner_a.get("href", "")
        if href and href.startswith("/"):
            href = BASE_BS + href

        if title and title not in ("Seite vorlesen",):
            events.append({
                "titel": title,
                "beschreibung": desc,
                "datum": None,
                "link": href,
                "quelle": "braunschweig.de",
                "kategorie": "Veranstaltung"
            })

    print(f"  {len(events)} Events gefunden")
    return events


def scrape_die_region():
    """braunschweig.die-region.de - regionaler Eventkalender mit vielen Einträgen"""
    url = "https://braunschweig.die-region.de/veranstaltungen/"
    print(f"Scraping: {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  Fehler: {e}")
        return []

    soup = BeautifulSoup(r.content, "lxml")
    events = []

    # Selektoren für die-region.de
    for item in soup.select(".event-list-item, .teaser, article, .event-item"):
        title_el = item.select_one("h2, h3, .title, .event-title, .headline")
        date_el = item.select_one(".date, .datum, time, .event-date")
        link_el = item.select_one("a[href]")

        title = title_el.get_text(strip=True) if title_el else None
        date = date_el.get_text(strip=True) if date_el else None
        href = link_el.get("href") if link_el else None

        if title:
            events.append({
                "titel": title,
                "beschreibung": None,
                "datum": date,
                "link": href,
                "quelle": "die-region.de",
                "kategorie": "Veranstaltung"
            })

    print(f"  {len(events)} Events gefunden")
    return events


def alle_events_sammeln():
    print("=== Braunschweig Event-Scraper ===\n")
    alle = []
    alle += scrape_stadt_braunschweig()
    alle += scrape_die_region()

    # Duplikate raus (gleicher Titel)
    gesehen = set()
    dedupliziert = []
    for e in alle:
        key = e["titel"].lower().strip() if e["titel"] else ""
        if key and key not in gesehen:
            gesehen.add(key)
            dedupliziert.append(e)

    print(f"\nGesamt: {len(dedupliziert)} Events (nach Deduplizierung)")
    return dedupliziert


if __name__ == "__main__":
    events = alle_events_sammeln()

    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
    print(f"\nGespeichert in: events.json")

    print("\n--- Vorschau (erste 10) ---")
    for e in events[:10]:
        datum = e["datum"] or "kein Datum"
        print(f"  [{datum}] {e['titel']}")
