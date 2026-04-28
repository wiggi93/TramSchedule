import requests
from datetime import datetime
import time

def fetch_departures():
    stop_id = "de:03241:1091"
    print(f"\U0001F50D Fetching departures for stop ID: {stop_id}...")

    url = "https://efa.de/efa/XML_DM_REQUEST"
    params = {
        "outputFormat": "rapidJSON",
        "type_dm": "any",
        "name_dm": stop_id,
        "mode": "direct",
        "useRealtime": "1",
        "depType": "stopEvents",
        "limit": "14",
        "version": "10.6.14.22"
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("stopEvents", [])
    except Exception as e:
        print(f"Error fetching departures: {e}")
        return []

def parse_departures(stop_events):
    departures = []
    now = datetime.now(datetime.utcnow().astimezone().tzinfo)
    for event in stop_events:
        prod_class = event.get("transportation", {}).get("product", {}).get("class", None)
        if prod_class == 3:  # 3 = Stadtbahn
            line = event["transportation"].get("number", "?")
            direction = event["transportation"].get("destination", {}).get("name", "?")
            departure_time = event.get("departureTimeEstimated") or event.get("departureTimePlanned")
            if departure_time:
                dt = datetime.fromisoformat(departure_time.replace("Z", "+00:00"))
                minutes = max(0, int((dt - now).total_seconds() / 60))
                departures.append((line, direction, minutes))
    return departures

def display_console_loop():
    while True:
        events = fetch_departures()
        parsed = sorted(parse_departures(events), key=lambda x: x[2], reverse=False)

        print("\n🟠 Upcoming Stadtbahn Departures (sorted by time left descending):")
        if parsed:
            for i, (line, dest, mins) in enumerate(parsed[:4]):
                print(f"{i+1}. {line} → {dest[:20]:20} in {mins} min")
        else:
            print("No departures found.")

        print("-" * 50)
        time.sleep(30)

if __name__ == "__main__":
    display_console_loop()
