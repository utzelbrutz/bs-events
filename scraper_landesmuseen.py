import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

BASE = "https://3landesmuseen-braunschweig.de"
AJAX = f"{BASE}/kalender/search-results-ajax"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{BASE}/kalender"
}

TYPEN_KAT = {
    "konzert": "Musik", "liederabend": "Musik", "musik": "Musik",
    "führung": "Führung & Tour", "kostümführung": "Führung & Tour",
    "kombüführung": "Führung & Tour", "stadtführung": "Führung & Tour",
    "vortrag": "Vortrag", "lesung": "Vortrag", "gespräch": "Vortrag",
    "kinderprogramm": "Familie", "familienrallye": "Familie",
    "ausstellung": "Ausstellung", "vernissage": "Ausstellung",
    "theater": "Theater", "schauspiel": "Theater",
    "workshop": "Vortrag", "seminar": "Vortrag",
}

MONATE = {
    "jan": 1, "feb": 2, "mär": 3, "apr": 4, "mai": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dez": 12
}


def kat_aus_typ(typ):
    t = (typ or "").lower()
    for k, v in TYPEN_KAT.items():
        if k in t:
            return v
    return "Ausstellung"


def parse_datum_ddmmyy(text):
    """Parst '21.05.26' → '2026-05-21'"""
    m = re.search(r"(\d{1,2})\.(\d{2})\.(\d{2,4})", text)
    if m:
        tag, mon, jahr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if jahr < 100:
            jahr += 2000
        try:
            return datetime(jahr, mon, tag).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def parse_datum_von_link(href):
    """Extrahiert Datum+Zeit aus href-Fragment '#2026-05-21T15:00:00+02:00'"""
    m = re.search(r"#(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})", href or "")
    if m:
        return m.group(1), m.group(2)
    return None, None


def parse_uhrzeit(info_texts):
    """Erstes info-item das wie eine Uhrzeit aussieht."""
    for t in info_texts:
        text = t.get_text(strip=True)
        m = re.search(r"(\d{1,2}):(\d{2})", text)
        if m:
            start = f"{m.group(1).zfill(2)}:{m.group(2)}"
            # Ende-Zeit suchen
            zeiten = re.findall(r"(\d{1,2}):(\d{2})", text)
            ende = f"{zeiten[-1][0].zfill(2)}:{zeiten[-1][1]}" if len(zeiten) > 1 else None
            return start, ende
    return None, None


def scrape_landesmuseen(max_seiten=10):
    print(f"Scraping: {AJAX}")
    events = []

    for seite in range(1, max_seiten + 1):
        params = {"page": seite} if seite > 1 else {}
        try:
            r = requests.get(AJAX, headers=HEADERS, params=params, timeout=12)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"  Seite {seite} Fehler: {e}")
            break

        soup = BeautifulSoup(r.content, "lxml")
        items = soup.select("div.event")

        if not items:
            break

        found = 0
        for item in items:
            titel_el  = item.select_one(".event-title")
            datum_el  = item.select_one(".event-date")
            typ_el    = item.select_one(".event-type")
            ort_items = item.select(".info-item")
            link_el   = item.select_one("a[href]")
            sticker_tag = item.select_one(".date-sticker-day")
            sticker_mon = item.select_one(".date-sticker-month")

            titel = titel_el.get_text(strip=True) if titel_el else None
            if not titel:
                continue

            event_typ = typ_el.get_text(strip=True) if typ_el else ""
            href = link_el.get("href") if link_el else None
            if href and href.startswith("/"):
                href = BASE + href

            # Datum: zuerst aus Link-Fragment, dann aus .event-date Text
            datum, startzeit = parse_datum_von_link(href)
            if not datum:
                datum_text = datum_el.get_text(strip=True) if datum_el else ""
                datum = parse_datum_ddmmyy(datum_text)

            # Uhrzeit: aus info-items
            info_texts = item.select(".info-item")
            if not startzeit:
                startzeit, endzeit = parse_uhrzeit(info_texts)
            else:
                _, endzeit = parse_uhrzeit(info_texts)

            # Ort: zweites info-item (erstes ist Uhrzeit)
            ort = None
            for info in info_texts:
                text = info.get_text(strip=True)
                if ":" not in text and "Uhr" not in text and len(text) > 3:
                    ort = text[:60]
                    break

            events.append({
                "titel": titel,
                "beschreibung": event_typ or None,
                "datum": datum,
                "datum_text": None,
                "startzeit": startzeit,
                "endzeit": endzeit,
                "ort": ort or "3Landesmuseen Braunschweig",
                "link": href,
                "quelle": "3landesmuseen-braunschweig.de",
                "kategorie": kat_aus_typ(event_typ)
            })
            found += 1

        print(f"  Seite {seite}: {found} Events")
        if found < 5:
            break

    print(f"  Gesamt: {len(events)} Events")
    return events


if __name__ == "__main__":
    events = scrape_landesmuseen()
    with open("events_landesmuseen.json", "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
    print("\n--- Vorschau ---")
    for e in events[:8]:
        print(f"  {e.get('datum','?')} {str(e.get('startzeit') or '?'):6} | {e['kategorie']:15} | {e['titel'][:45]}")
