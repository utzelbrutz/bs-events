"""
BS Events - Was ist heute in Braunschweig?
"""
import json
import http.server
import socketserver
import webbrowser
import threading
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

SCRAPER = [
    ("braunschweig.de",         "scraper_braunschweig",   "scrape_stadt_braunschweig", {}),
    ("die-region.de",           "scraper_die_region",     "scrape_die_region",          {"max_seiten": 20}),
    ("eventbrite.de",           "scraper_eventbrite",     "scrape_eventbrite",          {}),
    ("3landesmuseen",           "scraper_landesmuseen",   "scrape_landesmuseen",        {"max_seiten": 10}),
    ("staatstheater",           "scraper_staatstheater",  "scrape_staatstheater",       {}),
    ("venues (VW Halle etc.)",  "scraper_venues",         "alle_venues",               {}),
]


def events_sammeln():
    print("=" * 55)
    print("  BS Events — Scraper startet")
    print(f"  {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    print("=" * 55)

    alle = []
    for name, modul, funktion, kwargs in SCRAPER:
        try:
            mod = __import__(modul)
            fn  = getattr(mod, funktion)
            results = fn(**kwargs)
            alle += results
            print(f"  OK {name}: {len(results)} Events")
        except Exception as e:
            print(f"  -- {name}: {e}")

    # Deduplizieren
    gesehen = set()
    sauber  = []
    for e in alle:
        key = e["titel"].lower().strip()
        if key not in gesehen and len(key) > 3:
            gesehen.add(key)
            sauber.append(e)

    # Sortieren: mit Datum+Zeit zuerst, dann ohne
    def sort_key(e):
        return (e.get("datum") or "9999-99-99", e.get("startzeit") or "99:99")

    sauber.sort(key=sort_key)
    print(f"\n  Gesamt: {len(sauber)} Events\n")
    return sauber


class StillerHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args): pass


def server_starten(port=8000):
    with socketserver.TCPServer(("", port), StillerHandler) as httpd:
        print(f"Server: http://localhost:{port}  (Beenden: Ctrl+C)")
        httpd.serve_forever()


if __name__ == "__main__":
    nur_scrapen = "--nur-scrapen" in sys.argv

    events = events_sammeln()

    with open("events.json", "w", encoding="utf-8") as f:
        json.dump({
            "aktualisiert": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "anzahl": len(events),
            "events": events
        }, f, ensure_ascii=False, indent=2)

    print("events.json gespeichert")

    if nur_scrapen:
        sys.exit(0)

    t = threading.Thread(target=server_starten, daemon=True)
    t.start()
    time.sleep(0.5)
    webbrowser.open("http://localhost:8000")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nServer gestoppt.")
