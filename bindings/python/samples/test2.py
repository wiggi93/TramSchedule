import requests
from datetime import datetime

TRIAS_ENDPOINT = "https://v4-api.efa.de/api/1/trias"
REQUESTOR_REF = "2F6D7548-DF40-44EE-8293-4A4656F2F5D"
STOP_POINT_REF = "de:03241:255"  # Example: Hannover-Nordstadt
NUMBER_OF_RESULTS = 5

def get_trias_departures():
    now = datetime.utcnow().isoformat(timespec='seconds') + 'Z'

    xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Trias version="1.2" xmlns="http://www.vdv.de/trias"
       xmlns:ns2="http://www.siri.org.uk/siri">
  <ServiceRequest>
    <ns2:RequestTimestamp>{now}</ns2:RequestTimestamp>
    <ns2:RequestorRef>{REQUESTOR_REF}</ns2:RequestorRef>
    <RequestPayload>
      <StopEventRequest>
        <Location>
          <LocationRef>
            <StopPointRef>{STOP_POINT_REF}</StopPointRef>
          </LocationRef>
          <DepArrTime>{now}</DepArrTime>
        </Location>
        <Params>
          <NumberOfResults>{NUMBER_OF_RESULTS}</NumberOfResults>
          <StopEventType>departure</StopEventType>
        </Params>
      </StopEventRequest>
    </RequestPayload>
  </ServiceRequest>
</Trias>"""

    headers = {
        "Content-Type": "application/xml",
        # "Authorization": "apiKey=YOUR_API_KEY",  # ← Uncomment and replace if needed
        # "X-API-Key": "YOUR_API_KEY"             # ← Alternative header
    }

    response = requests.post(TRIAS_ENDPOINT, data=xml.encode("utf-8"), headers=headers)

    print("Response status:", response.status_code)
    print(response.text)

if __name__ == "__main__":
    get_trias_departures()
