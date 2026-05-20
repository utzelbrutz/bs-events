import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

BASE = "https://braunschweig.die-region.de"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

MONATE = {
    "januar": 1, "februar": 2, "märz": 3, "april": 4,
    "mai": 5, "juni": 6, "juli": 7, "august": 8,
    "september": 9, "oktober": 10, "november": 11, "dezember": 12
}

KATEGORIE_MAP = {
    "konzert": "Musik", "musik": "Musik", "band": "Musik", "jazz": "Musik",
    "rock": "Musik", "pop": "Musik", "chor": "Musik", "orchester": "Musik",
    "theater": "Theater", "schauspiel": "Theater", "oper": "Theater",
    "tanz": "Theater", "ballett": "Theater", "comedy": "Theater",
    "film": "Kino", "kino": "Kino", "filmvorführung": "Kino",
    "ausstellung": "Ausstellung", "galerie": "Ausstellung", "museum": "Ausstellung",
    "vernissage": "Ausstellung", "kunst": "Ausstellung",
    "sport": "Sport", "fußball": "Sport", "marathon": "Sport", "turnier": "Sport",
    "vortrag": "Vortrag", "lesung": "Vortrag", "diskussion": "Vortrag",
    "konferenz": "Vortrag", "salon": "Vortrag", "seminar": "Vortrag",
    "markt": "Markt & Fest", "festival": "Markt & Fest", "fest": "Markt & Fest",
    "flohmarkt": "Markt & Fest", "messe": "Markt & Fest",
    "führung": "Führung & Tour", "stadtführung": "Führung & Tour", "tour": "Führung & Tour",
    "kinder": "Familie", "familie": "Familie", "jugend": "Familie",
}


def kategorie_erkennen(titel):
    t = titel.lower()
    for keyword, kat in KATEGORIE_MAP.items():
        if keyword in t:
            return kat
    return "Sonstiges"


def parse_datum(text):
    if not text:
        return None
    match = re.search(
        r"(\d{1,2})\.\s*(januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember)(?:\s+(\d{4}))?",
        text.lower()
    )
    if match:
        tag, monat_str, jahr_str = match.group(1), match.group(2), match.group(3)
        monat = MONATE.get(monat_str)
        jahr = int(jahr_str) if jahr_str else datetime.now().year
        if monat:
            try:
                return datetime(jahr, monat, int(tag)).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None


def parse_zeiten(container):
    """Extrahiert Start- und Endzeit aus dem Container-Text."""
    text = container.get_text(separator=" ", strip=True)
    zeiten = re.findall(r'\b(\d{1,2})[:.:](\d{2})\b', text)
    if zeiten:
        startzeit = f"{zeiten[0][0].zfill(2)}:{zeiten[0][1]}"
        endzeit = f"{zeiten[-1][0].zfill(2)}:{zeiten[-1][1]}" if len(zeiten) > 1 else None
        return startzeit, endzeit
    return None, None


def scrape_die_region(max_seiten=5):
    print(f"Scraping: {BASE}/")
    events = []

    for seite in range(max_seiten):
        if seite == 0:
            url = f"{BASE}/"
        else:
            url = f"{BASE}/?tx_gcevents_eventlisting%5Bpage%5D={seite + 1}&tx_gcevents_eventlisting%5Baction%5D=list&tx_gcevents_eventlisting%5Bcontroller%5D=EventListing"

        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"  Seite {seite+1} Fehler: {e}")
            break

        soup = BeautifulSoup(r.content, "lxml")
        containers = soup.select("div.event-list__content")

        if not containers:
            break

        found = 0
        for container in containers:
            title_el = container.select_one("h2, h3, h4")
            title = title_el.get_text(strip=True) if title_el else None

            # Datum
            full_text = container.get_text(separator=" ", strip=True)
            datum_match = re.search(
                r"(\d{1,2}\.\s*(?:januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember)(?:\s+\d{4})?)",
                full_text, re.IGNORECASE
            )
            datum_text = datum_match.group(1).strip() if datum_match else None

            # Uhrzeiten
            startzeit, endzeit = parse_zeiten(container)

            # Ort
            ort_el = container.select_one(".event-list__location, .location, address")
            ort = ort_el.get_text(strip=True) if ort_el else None

            # Link
            link_el = container.select_one("a[href*='/veranstaltungen-detailseite/']")
            href = link_el.get("href") if link_el else None
            if href and href.startswith("/"):
                href = BASE + href

            if title:
                events.append({
                    "titel": title,
                    "beschreibung": None,
                    "datum": parse_datum(datum_text),
                    "datum_text": datum_text,
                    "startzeit": startzeit,
                    "endzeit": endzeit,
                    "ort": ort,
                    "link": href,
                    "quelle": "die-region.de",
                    "kategorie": kategorie_erkennen(title)
                })
                found += 1

        print(f"  Seite {seite+1}: {found} Events")
        if found == 0:
            break

    # Deduplizieren
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
    print("\n--- Vorschau ---")
    for e in events[:8]:
        uhr = e.get("startzeit") or "?"
        print(f"  {e.get('datum_text','?'):12} {uhr:5} | {e['kategorie']:15} | {e['titel'][:50]}")
