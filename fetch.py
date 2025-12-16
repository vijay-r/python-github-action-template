import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
import json

numberToFetch = "100"

def fetchXML():
    # URL to fetch XML
    url = f"https://np.tritondigital.com/public/nowplaying?mountName=OLI968FMAAC&numberToFetch={numberToFetch}&eventType=track"

    # Download XML
    response = requests.get(url)
    if response.status_code != 200:
        print("Error fetching XML:", response.status_code)
        exit()

    xml_data = response.text

    json_array = []
    result_map = {}

    root = ET.fromstring(xml_data)

    for track in root.findall("nowplaying-info"):
        properties = {}
        for prop in track.findall("property"):
            properties[prop.attrib['name']] = prop.text

        # Convert times
        start_time_ms = int(properties.get("cue_time_start", "0"))
        duration_ms = int(properties.get("cue_time_duration", "0"))

        # Duration in min:sec
        minutes = duration_ms // 60000
        seconds = (duration_ms % 60000) // 1000
        duration_formatted = f"{minutes}:{seconds:02d}"

        # Convert to Singapore Time (UTC+8)
        dt_utc = datetime.fromtimestamp(start_time_ms / 1000, tz=timezone.utc)
        dt_sg = dt_utc.astimezone(timezone(timedelta(hours=8)))
        start_time_sg = dt_sg.strftime("%Y-%m-%d %H:%M:%S")

        json_array.append({
            "Title": properties.get("cue_title", ""),
            "Start Time (SGT)": start_time_sg,
            "Duration (min:sec)": duration_formatted
        })

        result_map[start_time_ms] = {
            "Title": properties.get("cue_title", ""),
            "StartTime": start_time_sg,
            "Duration": duration_formatted
        }


        sorted_data = dict(
            sorted(result_map.items(), key=lambda x: int(x[0]))
        )
    
    print(f"data={json.dumps(sorted_data, ensure_ascii=False)}")

def main():
    fetchXML()

if __name__ == "__main__":
    main()