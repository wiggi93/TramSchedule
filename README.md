# TramSchedule — Abfahrtstafel

Real-time Stadtbahn departure board for an RGB LED matrix panel, driven by a Raspberry Pi. Fetches live data from the EFA transit API every 30 seconds and displays the next four departures with line number, destination, and minutes until departure.

---

## Debug output

Run on any machine with `--debug` to get a colour terminal preview instead of driving the LED hardware:

```
python3 abfahrtstafel.py --debug
```

```
┌──────────────────────┐
│10 Ahlem               3│
│17 Rethen              7│
│10 Ahlem              33│
│17 Rethen             37│
│       10:42:07        │
└──────────────────────┘
  [debug]  refreshes every 0.5s, data every 30s
```

- **Badge** (left, blue background) — tram line number
- **Destination** (middle, orange) — scrolls horizontally when the name is long
- **Minutes** (right, white → yellow flash on change) — minutes until departure
- **Clock** (bottom, grey) — current time

---

## Hardware

- Raspberry Pi (any model with GPIO)
- RGB LED matrix panel — defaults to 64 × 32, HUB75 interface
- [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix) C library with Python bindings

---

## Setup

```bash
# Install Python dependency
pip install requests

# Build and install the LED matrix library (on the Pi)
# Follow https://github.com/hzeller/rpi-rgb-led-matrix#python-bindings
```

---

## Usage

### Debug mode (no hardware required)

```bash
python3 abfahrtstafel.py --debug
```

### LED display (run as root on the Pi)

```bash
sudo python3 abfahrtstafel.py
```

Common flags (passed through to the matrix library):

| Flag | Default | Description |
|------|---------|-------------|
| `--led-rows` | 32 | Panel row count |
| `--led-cols` | 64 | Panel column count |
| `--led-brightness` | 70 | Brightness (1–100) |
| `--led-gpio-mapping` | — | `regular`, `adafruit-hat`, etc. |
| `--led-slowdown-gpio` | 2 | GPIO write slowdown (0–4) |

---

## Configuration

All tuneable values are constants at the top of [`abfahrtstafel.py`](abfahrtstafel.py):

| Constant | Default | Description |
|----------|---------|-------------|
| `STOP_ID` | `de:03241:1091` | EFA stop identifier |
| `FETCH_INTERVAL` | `30` s | How often to poll the API |
| `REQUEST_TIMEOUT` | `10` s | HTTP request timeout |
| `SCROLL_PAUSE` | `3.5` s | Hold time before scrolling |
| `SCROLL_SPEED` | `0.38` s/char | Scrolling speed |
| `SCROLL_HOLD` | `2.0` s | Hold time at end of scroll |
| `LED_COLS` | `64` | Matrix pixel width |
