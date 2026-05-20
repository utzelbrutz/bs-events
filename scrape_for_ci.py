"""Wird von GitHub Actions täglich ausgeführt — kein Server, nur scrapen + speichern."""
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SCRAPER = [
    ("braunschweig.de",   "scraper_braunschweig",  "scrape_stadt_braunschweig", {}),
    ("die-region.de",     "scraper_die_region",     "scrape_die_region",         {"max_seiten": 5}),
    ("eventbrite.de",     "scraper_eventbrite",     "scrape_eventbrite",         {}),
    ("3landesmuseen",     "scraper_landesmuseen",   "scrape_landesmuseen",       {"max_seiten": 10}),
    ("staatstheater",     "scraper_staatstheater",  "scrape_staatstheater",      {}),
    ("venues",            "scraper_venues",         "alle_venues",               {}),
]

alle = []
for name, modul, funktion, kwargs in SCRAPER:
    try:
        mod = __import__(modul)
        fn  = getattr(mod, funktion)
        results = fn(**kwargs)
        alle += results
        print(f"OK {name}: {len(results)} Events")
    except Exception as e:
        print(f"-- {name}: {e}")

# Deduplizieren
gesehen = set()
sauber  = []
for e in alle:
    key = e["titel"].lower().strip()
    if key not in gesehen and len(key) > 3:
        gesehen.add(key)
        sauber.append(e)

sauber.sort(key=lambda e: (e.get("datum") or "9999-99-99", e.get("startzeit") or "99:99"))

with open("events.json", "w", encoding="utf-8") as f:
    json.dump({
        "aktualisiert": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "anzahl": len(sauber),
        "events": sauber
    }, f, ensure_ascii=False, indent=2)

print(f"\nGesamt: {len(sauber)} Events gespeichert")
