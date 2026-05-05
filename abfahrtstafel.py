#!/usr/bin/env python3

import argparse
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import requests

# Parse --debug early so we can skip hardware imports on non-Pi machines.
_pre = argparse.ArgumentParser(add_help=False)
_pre.add_argument("--debug", action="store_true")
_pre_args, _ = _pre.parse_known_args()
DEBUG: bool = _pre_args.debug

if not DEBUG:
    from samplebase import SampleBase  # type: ignore
    from rgbmatrix import graphics     # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

STOP_ID          = "de:03241:1091"
API_URL          = "https://efa.de/efa/XML_DM_REQUEST"
API_VERSION      = "10.6.14.22"
STADTBAHN_CLASS  = 3     # product.class value for Stadtbahn lines

DISPLAY_ROWS     = 4
MAX_DEST_LEN     = 9     # destination characters shown at once in the debug terminal
FONT_PATH        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts/4x6.bdf")

LED_COLS         = 64    # pixel width of the LED matrix
CHAR_WIDTH       = 4     # pixels per character in the 4x6 font

FETCH_INTERVAL   = 30    # seconds between API polls
REQUEST_TIMEOUT  = 10    # seconds before an HTTP request is abandoned

SCROLL_PAUSE     = 3.5   # seconds to hold before scrolling begins
SCROLL_SPEED     = 0.38  # seconds per character shift
SCROLL_HOLD      = 2.0   # seconds to hold at end before resetting
SCROLL_STAGGER   = 2.5   # per-row time offset so rows don't scroll simultaneously

DISPLAY_WIDTH    = 22    # character width of the debug terminal frame

# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Departure:
    line: str
    destination: str
    minutes: int


# ── Shared board state ────────────────────────────────────────────────────────

class BoardState:
    """Thread-safe container for the current departure list."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._departures: list[Optional[Departure]] = [None] * DISPLAY_ROWS
        self._changed_at: list[float] = [0.0] * DISPLAY_ROWS

    def update(self, new: list[Departure]) -> None:
        with self._lock:
            for i in range(DISPLAY_ROWS):
                dep = new[i] if i < len(new) else None
                old = self._departures[i]
                if old is None or dep is None or old.minutes != dep.minutes:
                    self._changed_at[i] = time.time()
                self._departures[i] = dep

    def snapshot(self) -> tuple[list[Optional[Departure]], list[float]]:
        with self._lock:
            return list(self._departures), list(self._changed_at)


# ── API fetching ──────────────────────────────────────────────────────────────

def fetch_stop_events() -> list[dict]:
    log.info("Fetching departures for stop %s", STOP_ID)
    params = {
        "outputFormat": "rapidJSON",
        "type_dm":      "any",
        "name_dm":      STOP_ID,
        "mode":         "direct",
        "useRealtime":  "1",
        "depType":      "stopEvents",
        "limit":        "14",
        "version":      API_VERSION,
    }
    try:
        response = requests.get(API_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json().get("stopEvents", [])
    except Exception as e:
        log.error("Failed to fetch departures: %s", e)
        return []


def parse_departures(events: list[dict]) -> list[Departure]:
    now = datetime.now(timezone.utc)
    result: list[Departure] = []
    for event in events:
        transport = event.get("transportation", {})
        if transport.get("product", {}).get("class") != STADTBAHN_CLASS:
            continue
        line        = transport.get("number", "?")
        destination = transport.get("destination", {}).get("name", "?").rstrip("/ ")
        dep_str     = event.get("departureTimeEstimated") or event.get("departureTimePlanned")
        if not dep_str:
            continue
        dt      = datetime.fromisoformat(dep_str.replace("Z", "+00:00"))
        minutes = max(0, int((dt - now).total_seconds() / 60))
        result.append(Departure(line=line, destination=destination, minutes=minutes))
    return sorted(result, key=lambda d: d.minutes)


# ── Background fetch loop ─────────────────────────────────────────────────────

def fetch_loop(board: BoardState) -> None:
    while True:
        try:
            events     = fetch_stop_events()
            departures = parse_departures(events)
            board.update(departures)
            for dep in departures[:DISPLAY_ROWS]:
                log.info("→ %s to %s in %d min", dep.line, dep.destination, dep.minutes)
        except Exception as e:
            log.error("Fetch loop error: %s", e)
        time.sleep(FETCH_INTERVAL)


# ── Scroll helpers ────────────────────────────────────────────────────────────

def scroll_offset(row: int, dest_len: int, visible: int = MAX_DEST_LEN) -> int:
    max_off = max(0, dest_len - visible)
    if max_off == 0:
        return 0
    scroll_dur = max_off * SCROLL_SPEED
    cycle      = SCROLL_PAUSE + scroll_dur + SCROLL_HOLD
    t          = (time.time() - row * SCROLL_STAGGER) % cycle
    if t < SCROLL_PAUSE:
        return 0
    if t < SCROLL_PAUSE + scroll_dur:
        return int((t - SCROLL_PAUSE) / SCROLL_SPEED)
    return max_off


# ── LED display (hardware mode) ───────────────────────────────────────────────

if not DEBUG:
    class RunText(SampleBase):
        def __init__(self, board: BoardState, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.board = board
            self.parser.set_defaults(
                led_slowdown_gpio=2,
                led_pwm_bits=11,
                led_brightness=70,
            )

        def run(self) -> None:
            canvas = self.matrix.CreateFrameCanvas()
            font   = graphics.Font()
            try:
                font.LoadFont(FONT_PATH)
            except Exception as e:
                log.error("Failed to load font: %s", e)
                return

            dest_color  = graphics.Color(255, 127,  80)
            time_color  = graphics.Color(255, 255, 255)
            badge_bg    = graphics.Color(  0,  70, 200)
            badge_text  = graphics.Color(255, 255, 255)
            clock_color = graphics.Color(180, 180, 180)
            line_height = 6
            badge_width = 6   # 1-char number + 1px padding on each side
            dest_x      = badge_width + 1                      # 7 — destination text origin
            time_x      = LED_COLS - 2 * CHAR_WIDTH            # 56 — right-align 2-digit minutes
            # available pixels between dest_x and time_x, minus 1 leading-space char
            led_dest_visible = (time_x - dest_x) // CHAR_WIDTH - 1   # = 11

            while True:
                canvas.Clear()
                deps, changed_at = self.board.snapshot()

                for i, dep in enumerate(deps):
                    if dep is None:
                        continue
                    y = line_height + i * line_height
                    for fy in range(y - line_height + 1, y + 1):
                        graphics.DrawLine(canvas, 0, fy, badge_width - 1, fy, badge_bg)
                    graphics.DrawText(canvas, font, 1, y, badge_text, dep.line[:2])

                    off        = scroll_offset(i, len(dep.destination), led_dest_visible)
                    dest_shown = f" {dep.destination[off:off + led_dest_visible]:<{led_dest_visible}}"
                    graphics.DrawText(canvas, font, dest_x, y, dest_color, dest_shown)

                    elapsed = time.time() - changed_at[i]
                    if elapsed < 1.5:
                        b              = int(min(1.0, elapsed / 1.5) * 255)
                        row_time_color = graphics.Color(255, 255, b)
                    else:
                        row_time_color = time_color
                    graphics.DrawText(canvas, font, time_x, y, row_time_color, f"{dep.minutes:>2}")

                now_str = datetime.now().strftime("%H:%M:%S")
                clock_x = (64 - len(now_str) * 4) // 2
                graphics.DrawText(canvas, font, clock_x, 31, clock_color, now_str)

                time.sleep(0.1)
                canvas = self.matrix.SwapOnVSync(canvas)


# ── Debug terminal display ────────────────────────────────────────────────────

def debug_display(board: BoardState) -> None:
    ORANGE    = "\033[38;2;255;127;80m"
    WHITE     = "\033[38;2;255;255;255m"
    YELLOW    = "\033[38;2;255;255;0m"
    BADGE_BG  = "\033[48;2;0;70;200m"
    RESET     = "\033[0m"
    ERASE_EOL = "\033[K"
    border      = "─" * DISPLAY_WIDTH
    FRAME_LINES = 8

    first = True
    while True:
        deps, changed_at = board.snapshot()
        now_str    = datetime.now().strftime("%H:%M:%S")
        clock_line = f"{now_str:^{DISPLAY_WIDTH}}"

        if not first:
            sys.stdout.write(f"\033[{FRAME_LINES - 1}A\r")

        out = [f"┌{border}┐{ERASE_EOL}"]
        for j, dep in enumerate(deps):
            if dep is not None:
                off        = scroll_offset(j, len(dep.destination))
                dest_shown = dep.destination[off:off + MAX_DEST_LEN]
                dest_part  = f" {dest_shown:<{MAX_DEST_LEN}}"
                time_part  = f"{dep.minutes:>{DISPLAY_WIDTH - 12}}"
                badge      = f"{BADGE_BG}{WHITE}{dep.line[:2]:<2}{RESET}"
                t_color    = YELLOW if time.time() - changed_at[j] < 1.5 else WHITE
                out.append(f"│{badge}{ORANGE}{dest_part}{RESET}{t_color}{time_part}{RESET}│{ERASE_EOL}")
            else:
                out.append(f"│{' ' * DISPLAY_WIDTH}│{ERASE_EOL}")
        out.append(f"│{WHITE}{clock_line}{RESET}│{ERASE_EOL}")
        out.append(f"└{border}┘{ERASE_EOL}")
        out.append(f"  {ORANGE}[debug]{RESET}  refreshes every 0.5s, data every 30s{ERASE_EOL}")
        print("\n".join(out), end="", flush=True)
        first = False
        time.sleep(0.5)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    board = BoardState()
    fetch_thread = threading.Thread(target=fetch_loop, args=(board,), daemon=True)
    fetch_thread.start()

    if DEBUG:
        log.info("Debug mode — terminal display (Ctrl+C to quit)")
        try:
            debug_display(board)
        except KeyboardInterrupt:
            print("\033[0m\nExiting.")
    else:
        log.info("Starting LED display...")
        run_text = RunText(board)
        if not run_text.process():
            run_text.print_help()


if __name__ == "__main__":
    main()
