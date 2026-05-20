"""
Scraper für lokale Braunschweiger Venues:
- VW Halle
- Stadtbibliothek
- Kammerspiele
- Eintracht Braunschweig (Spielplan)
- 3Landesmuseen
- Brunsviga
"""
import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "de-DE,de;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

MONATE = {
    "januar":1,"februar":2,"märz":3,"april":4,"mai":5,"juni":6,
    "juli":7,"august":8,"september":9,"oktober":10,"november":11,"dezember":12,
    "jan":1,"feb":2,"mär":3,"apr":4,"jun":6,"jul":7,"aug":8,
    "sep":9,"okt":10,"nov":11,"dez":12
}


def parse_datum(text):
    if not text: return None
    m = re.search(r"(\d{1,2})[.\s]+(\w+)(?:[.\s]+(\d{4}))?", text.lower())
    if m:
        monat = MONATE.get(m.group(2)) or MONATE.get(m.group(2)[:3])
        if monat:
            jahr = int(m.group(3)) if m.group(3) and len(m.group(3)) == 4 else datetime.now().year
            try:
                return datetime(jahr, monat, int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError: pass
    return None


def parse_zeit(text):
    if not text: return None
    m = re.search(r"(\d{1,2})[.:](\d{2})\s*(?:Uhr)?", text)
    return f"{m.group(1).zfill(2)}:{m.group(2)}" if m else None


def generischer_scraper(url, basis_url, quelle, ort, kategorie, selektoren):
    """Versucht mehrere Selektor-Strategien und gibt Events zurück."""
    print(f"Scraping: {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=5)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  Fehler: {e}")
        return []

    soup = BeautifulSoup(r.content, "lxml")
    events = []

    # Selektoren der Reihe nach probieren
    items = []
    for sel in selektoren:
        items = soup.select(sel)
        if items:
            print(f"  Selektor '{sel}' → {len(items)} Treffer")
            break

    if not items:
        print(f"  Keine Treffer — Seitenstruktur:")
        klassen = set()
        for t in soup.find_all(class_=True):
            for c in t.get("class", []):
                if any(x in c.lower() for x in ["event","veranstalt","item","card","list","termin","entry"]):
                    klassen.add(f"{t.name}.{c}")
        for k in sorted(klassen)[:15]:
            print(f"    {k}")
        return []

    for item in items:
        # Titel: h2 > h3 > h4 > .title > erster längerer Text
        titel_el = (item.select_one("h2, h3, h4")
                    or item.select_one("[class*='title'],[class*='headline'],[class*='name']"))
        titel = titel_el.get_text(strip=True) if titel_el else None
        if not titel:
            text_lines = [l.strip() for l in item.get_text().split("\n") if len(l.strip()) > 10]
            titel = text_lines[0] if text_lines else None

        # Datum
        datum_el = (item.select_one("time[datetime]")
                    or item.select_one("[class*='date'],[class*='datum'],[class*='time']"))
        raw_datum = (datum_el.get("datetime") or datum_el.get_text(strip=True)) if datum_el else None
        datum = parse_datum(raw_datum)

        # Zeit
        zeit_el = item.select_one("[class*='time'],[class*='uhr'],[class*='clock']")
        zeit = parse_zeit(zeit_el.get_text(strip=True) if zeit_el else (raw_datum or ""))

        # Link
        link_el = item.select_one("a[href]")
        href = link_el.get("href") if link_el else None
        if href and href.startswith("/"):
            href = basis_url + href

        if titel and len(titel) > 3:
            events.append({
                "titel": titel,
                "beschreibung": None,
                "datum": datum,
                "datum_text": None,
                "startzeit": zeit,
                "endzeit": None,
                "ort": ort,
                "link": href,
                "quelle": quelle,
                "kategorie": kategorie
            })

    print(f"  {len(events)} Events extrahiert")
    return events


# ── Einzelne Venue-Scraper ──────────────────────────────────────────────────

def scrape_vw_halle():
    return generischer_scraper(
        url="https://www.volkswagen-halle.de/veranstaltungen/",
        basis_url="https://www.volkswagen-halle.de",
        quelle="volkswagen-halle.de",
        ort="Volkswagen Halle Braunschweig",
        kategorie="Musik",
        selektoren=[
            ".event-list__item", ".event-card", ".veranstaltung-item",
            "article.event", "article", ".list-item",
            "[class*='event-item']", "[class*='EventCard']"
        ]
    )


def scrape_stadtbibliothek():
    return generischer_scraper(
        url="https://www.stadtbibliothek-braunschweig.de/veranstaltungen/",
        basis_url="https://www.stadtbibliothek-braunschweig.de",
        quelle="stadtbibliothek-braunschweig.de",
        ort="Stadtbibliothek Braunschweig",
        kategorie="Vortrag",
        selektoren=[
            ".tx-cal-event", ".event-list li", ".veranstaltung",
            "article", ".list-item", "[class*='event']", "[class*='termin']"
        ]
    )


def scrape_kammerspiele():
    # Kammerspiele Braunschweig
    return generischer_scraper(
        url="https://www.kammerspiele-braunschweig.de/spielplan/",
        basis_url="https://www.kammerspiele-braunschweig.de",
        quelle="kammerspiele-braunschweig.de",
        ort="Kammerspiele Braunschweig",
        kategorie="Theater",
        selektoren=[
            ".spielplan__item", ".event-item", "article.event",
            ".production", ".show-item", "article", "[class*='spielplan']"
        ]
    )


def scrape_landesmuseen():
    events = []
    for museum, url, ort in [
        ("braunschweigisches-landesmuseum", "https://3landesmuseen-braunschweig.de/braunschweigisches-landesmuseum/veranstaltungen/", "Braunschweigisches Landesmuseum"),
        ("herzog-anton-ulrich-museum",      "https://3landesmuseen-braunschweig.de/herzog-anton-ulrich-museum/veranstaltungen/",      "Herzog Anton Ulrich-Museum"),
        ("burg-dankwarderode",              "https://3landesmuseen-braunschweig.de/burg-dankwarderode/veranstaltungen/",              "Burg Dankwarderode"),
    ]:
        events += generischer_scraper(
            url=url,
            basis_url="https://3landesmuseen-braunschweig.de",
            quelle="3landesmuseen-braunschweig.de",
            ort=ort,
            kategorie="Ausstellung",
            selektoren=[
                ".event-list__item", ".veranstaltung", "article",
                ".ce-uploads li", "[class*='event']", "[class*='termin']",
                ".news-list-item", ".tx-news-pi1 article"
            ]
        )
    return events


def scrape_brunsviga():
    # Brunsviga Kulturzentrum — die Domain scheint weiterzuleiten
    for url in [
        "https://www.brunsviga.de/programm/",
        "https://brunsviga.de/programm/",
        "https://www.brunsviga-braunschweig.de/",
    ]:
        events = generischer_scraper(
            url=url,
            basis_url="https://www.brunsviga.de",
            quelle="brunsviga.de",
            ort="Brunsviga Braunschweig",
            kategorie="Musik",
            selektoren=[
                ".event", ".veranstaltung", "article",
                ".program-item", "[class*='event']", "li.item"
            ]
        )
        if events:
            return events
    return []


def scrape_eintracht():
    """Eintracht Braunschweig — nächste Heimspiele."""
    print("Scraping: eintracht.com/spiele/")
    try:
        r = requests.get("https://www.eintracht.com/spiele/spielplan/",
                         headers=HEADERS, timeout=5)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  Fehler: {e}")
        return []

    soup = BeautifulSoup(r.content, "lxml")
    events = []

    # Eintracht.com nutzt eine eigene Spielplan-Struktur
    for item in (soup.select(".matches__item, .match-item, .game-item, article")
                 or soup.select("tr")):
        text = item.get_text(separator=" | ", strip=True)
        if "braunschweig" not in text.lower() and "eintracht" not in text.lower():
            continue

        titel_el = item.select_one("h2,h3,.match-title,.opponent,.home,.away")
        datum_el = item.select_one("time,.date,.match-date")
        link_el  = item.select_one("a[href]")

        titel = titel_el.get_text(strip=True) if titel_el else None
        if not titel:
            titel = "Eintracht Braunschweig"

        raw = datum_el.get("datetime") or datum_el.get_text(strip=True) if datum_el else ""
        datum = parse_datum(raw)
        zeit  = parse_zeit(raw)
        href  = link_el.get("href") if link_el else "https://www.eintracht.com/spiele/"
        if href and href.startswith("/"):
            href = "https://www.eintracht.com" + href

        if datum:
            events.append({
                "titel": titel,
                "beschreibung": "Fußball — Eintracht Braunschweig",
                "datum": datum,
                "datum_text": None,
                "startzeit": zeit,
                "endzeit": None,
                "ort": "Eintracht-Stadion Braunschweig",
                "link": href,
                "quelle": "eintracht.com",
                "kategorie": "Sport"
            })

    print(f"  {len(events)} Spiele gefunden")
    return events


def alle_venues():
    alle = []
    alle += scrape_vw_halle()
    alle += scrape_stadtbibliothek()
    alle += scrape_kammerspiele()
    alle += scrape_landesmuseen()
    alle += scrape_brunsviga()
    alle += scrape_eintracht()
    return alle


if __name__ == "__main__":
    events = alle_venues()
    with open("events_venues.json", "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
    print(f"\nGesamt: {len(events)} Events")
    for e in events[:10]:
        print(f"  [{e['quelle']:30}] {e.get('datum','?')} {e.get('startzeit','?'):6} | {e['titel'][:40]}")
