#!/home/philip/rpi-rgb-led-matrix/venv/bin/python

from samplebase import SampleBase
from rgbmatrix import graphics
from datetime import datetime
import requests
import time
import os
import threading

script_dir = os.path.dirname(os.path.abspath(__file__))
font_path = os.path.join(script_dir, '../../../fonts/4x6.bdf')

# Just static strings (no scrolling offsets)
tram_lines = ["waiting for departures", "", "", ""]
lock = threading.Lock()

class RunText(SampleBase):
    def __init__(self, *args, **kwargs):
        super(RunText, self).__init__(*args, **kwargs)
        self.parser.set_defaults(
            led_slowdown_gpio=2,
            led_pwm_bits=11,
            led_brightness=70
        )

    def run(self):
        global tram_lines
        offscreen_canvas = self.matrix.CreateFrameCanvas()
        font = graphics.Font()
        try:
            font.LoadFont(font_path)
        except Exception as e:
            print(f"Error loading font: {e}")
            return

        textColor = graphics.Color(255, 127, 80)
        line_height = 6

        while True:
            offscreen_canvas.Clear()
            with lock:
                for i, text in enumerate(tram_lines):
                    graphics.DrawText(offscreen_canvas, font, 0, (i + 1) * line_height, textColor, text)
            time.sleep(0.1)
            offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)

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
        if prod_class == 3:  # Stadtbahn
            line = event["transportation"].get("number", "?")
            direction = event["transportation"].get("destination", {}).get("name", "?")
            departure_time = event.get("departureTimeEstimated") or event.get("departureTimePlanned")
            if departure_time:
                dt = datetime.fromisoformat(departure_time.replace("Z", "+00:00"))
                minutes = max(0, int((dt - now).total_seconds() / 60))
                departures.append((line, direction, minutes))
    return departures

def additional_task():
    global tram_lines, lock
    max_dest_len = 9  # optional: limit to prevent overflow

    while True:
        events = fetch_departures()
        parsed = sorted(parse_departures(events), key=lambda x: x[2])

        with lock:
            for i in range(4):
                if i < len(parsed):
                    line, dest, mins = parsed[i]
                    tram_lines[i] = f"{line:<2} {dest[:max_dest_len]:<{max_dest_len}} {mins:>2} min"
                    print(f"→ {line} to {dest} in {mins} min")
                else:
                    tram_lines[i] = ""

            if not parsed:
                tram_lines[0] = "waiting for departures"
                for j in range(1, 4):
                    tram_lines[j] = ""

        time.sleep(30)

if __name__ == "__main__":
    print("Starting main script...")

    run_text = RunText()

    print("Starting background thread...")
    additional_thread = threading.Thread(target=additional_task)
    additional_thread.daemon = True
    additional_thread.start()

    print("Starting display loop...")
    if not run_text.process():
        run_text.print_help()
