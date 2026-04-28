from deutsche_bahn_api import ApiAuthentication, StationHelper, TimetableHelper
from datetime import datetime

# Use your valid API credentials here
CLIENT_ID = "0f7f2040e88e69737c0e6c109fa94ba9"
CLIENT_SECRET = "dba98f06a7aa43d3e64373ecd121031c"

api_auth = ApiAuthentication(CLIENT_ID, CLIENT_SECRET)
station_helper = StationHelper()

# Try different variants of the station name if necessary
stations = station_helper.find_stations_by_name("Hannover-Kleefeld")

if not stations:
    print("❌ No stations found.")
    exit()

station = stations[0]
print(f"📍 Using station: {station.NAME} (EVA_NR: {station.EVA_NR})")

timetable_helper = TimetableHelper(station, api_auth)

# Get current hour
now = datetime.now()
hour = now.hour

# Get current timetable
trains = timetable_helper.get_timetable(hour)

if not trains:
    print("❌ No departures found.")
else:
    print("\n🚋 Upcoming tram/train departures:")
    for train in trains[:4]:  # Show only first 4 entries
        time = train.departure[-4:]  # e.g., '1045'
        print(f"{train.train_type} {train.train_number} → {train.stations} at {time}")
