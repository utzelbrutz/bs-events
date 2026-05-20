import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

BASE_URL = "https://www.eventbrite.de/d/germany--braunschweig/events/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

MONATE = {
    "januar": 1, "februar": 2, "märz": 3, "april": 4,
    "mai": 5, "juni": 6, "juli": 7, "august": 8,
    "september": 9, "oktober": 10, "november": 11, "dezember": 12,
    "jan": 1, "feb": 2, "mär": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dez": 12
}

KATEGORIE_MAP = {
    "konzert": "Musik", "musik": "Musik", "band": "Musik", "festival": "Markt & Fest",
    "theater": "Theater", "comedy": "Theater", "tanz": "Theater",
    "film": "Kino", "kino": "Kino",
    "ausstellung": "Ausstellung", "kunst": "Ausstellung",
    "sport": "Sport", "lauf": "Sport", "yoga": "Sport",
    "vortrag": "Vortrag", "seminar": "Vortrag", "workshop": "Vortrag",
    "markt": "Markt & Fest", "fest": "Markt & Fest",
    "kinder": "Familie", "familie": "Familie",
}


def kategorie_erkennen(titel):
    t = titel.lower()
    for k, v in KATEGORIE_MAP.items():
        if k in t:
            return v
    return "Sonstiges"


def parse_eb_datum(text):
    """Parst Eventbrite-Datumsformate: 'morgen um 10:00', 'Sa., 24. Mai', '24. Mai'"""
    if not text:
        return None, None
    text_lower = text.lower().strip()

    heute = datetime.now()

    if "heute" in text_lower:
        zeitm = re.search(r'(\d{1,2}):(\d{2})', text)
        uhrzeit = f"{zeitm.group(1).zfill(2)}:{zeitm.group(2)}" if zeitm else None
        return heute.strftime("%Y-%m-%d"), uhrzeit

    if "morgen" in text_lower:
        from datetime import timedelta
        morgen = heute + timedelta(days=1)
        zeitm = re.search(r'(\d{1,2}):(\d{2})', text)
        uhrzeit = f"{zeitm.group(1).zfill(2)}:{zeitm.group(2)}" if zeitm else None
        return morgen.strftime("%Y-%m-%d"), uhrzeit

    # "Sa., 24. Mai" oder "24. Mai 2026"
    match = re.search(r"(\d{1,2})\.\s*([\w]+)(?:\s+(\d{4}))?", text_lower)
    if match:
        tag, monat_str, jahr_str = match.group(1), match.group(2), match.group(3)
        # Abkürzungen normalisieren
        monat_str = monat_str[:3] if len(monat_str) >= 3 else monat_str
        monat = MONATE.get(monat_str) or MONATE.get(monat_str[:3])
        jahr = int(jahr_str) if jahr_str else heute.year
        if monat:
            try:
                d = datetime(jahr, monat, int(tag))
                zeitm = re.search(r'(\d{1,2}):(\d{2})', text)
                uhrzeit = f"{zeitm.group(1).zfill(2)}:{zeitm.group(2)}" if zeitm else None
                return d.strftime("%Y-%m-%d"), uhrzeit
            except ValueError:
                pass
    return None, None


def scrape_eventbrite():
    print(f"Scraping: {BASE_URL}")
    try:
        r = requests.get(BASE_URL, headers=HEADERS, timeout=12)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  Fehler: {e}")
        return []

    soup = BeautifulSoup(r.content, "lxml")
    events = []

    for card in soup.select("section.discover-vertical-event-card, div.discover-vertical-event-card"):
        # Titel
        title_el = card.select_one("h3, h2, [class*='title'], [class*='Title']")
        title = title_el.get_text(strip=True) if title_el else None

        # Datum+Zeit aus dem Volltext
        text = card.get_text(separator=" | ", strip=True)

        # Datum+Zeit parsen
        datum, uhrzeit = parse_eb_datum(text)

        # Link
        link_el = card.select_one("a[href]")
        href = link_el.get("href") if link_el else None

        # Ort
        ort_el = card.select_one("[class*='location'], [class*='Location'], [class*='venue']")
        ort = ort_el.get_text(strip=True) if ort_el else None

        if title and len(title) > 3:
            events.append({
                "titel": title,
                "beschreibung": None,
                "datum": datum,
                "datum_text": None,
                "startzeit": uhrzeit,
                "endzeit": None,
                "ort": ort,
                "link": href,
                "quelle": "eventbrite.de",
                "kategorie": kategorie_erkennen(title)
            })

    print(f"  {len(events)} Events gefunden")
    return events


if __name__ == "__main__":
    events = scrape_eventbrite()
    with open("events_eventbrite.json", "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
    print("\n--- Vorschau ---")
    for e in events[:8]:
        print(f"  {str(e.get('datum') or '?'):12} {str(e.get('startzeit') or '?'):6} | {e['titel'][:55]}")
