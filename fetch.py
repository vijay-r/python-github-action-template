import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
import json
import re

numberToFetch = "50"

def fetchXML():
    # URL to fetch XML
    url = f"https://np.tritondigital.com/public/nowplaying?mountName=OLI968FMAAC&numberToFetch={numberToFetch}&eventType=ad"

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

    report(sorted_data)

def report(unique_data):

    # ===========================
    titleTxtArray = []
    for epoch, details in unique_data.items():
        str = getTitleForAI(details["Title"], details["StartTime"], details["Duration"])
        if(str != ''):
            titleTxtArray.append(str)
            # titleTxt = titleTxt + str + '\n'

    # print(titleTxtArray)

    all_items = parse_schedule(titleTxtArray)

    # Example usage
    start = "7:00PM"
    end = "9:00PM"

    reportTxt = ""
    reportTxt = filter_and_sort(all_items, start, end, "Credit Mention", reportTxt, True)
    reportTxt = filter_and_sort(all_items, start, end, "Ad", reportTxt, True)
    reportTxt = filter_and_sort(all_items, start, end, "Credit Mention", reportTxt, True)
    reportTxt = filter_and_sort(all_items, start, end, "Ad", reportTxt, True)

    print(reportTxt)
    # reportTxt = filter_and_sort(all_items, pm1, pm5, "Credit Mention", reportTxt)
    # reportTxt = filter_and_sort(all_items, pm1, pm5, "Ad", reportTxt)
    # reportTxt = filter_and_sort(all_items, pm5, pm9, "Credit Mention", reportTxt)
    # reportTxt = filter_and_sort(all_items, pm5, pm9, "Ad", reportTxt)

    # with open(reportTxtPath, "w", encoding="utf-8") as f:
    #     f.write(reportTxt)

def parse_time(time_str):
    """Convert time string like '1:14PM' to datetime object"""
    return datetime.strptime(time_str.strip().upper(), '%I:%M%p')

def parse_schedule(titleTxtArray):
    """
    Extract all items (Credit Mentions and Ads) with their time
    Returns a list of tuples: (time_obj, item_type, description)
    """
    items = []

    for line in titleTxtArray:
        match = re.match(r'(\d{1,2}:\d{2}[AP]M)\s*:\s*(.+)', line)
        if not match:
            continue
        time_str, description = match.groups()
        time_obj = parse_time(time_str)

        # Credit Mention
        if '(Credit Mention' in description or description.startswith('INFO-ED'):
            # Extract description
            credit_match = re.search(r'\(Credit Mention[^)]*\)\s*(.+)', description)

            if credit_match:
                desc = credit_match.group(1).strip()


                cmMatch = re.search(r'\(Credit Mention - ([^)]+)\)', description)
                if cmMatch:
                    credit_type = cmMatch.group(1).strip()
                    desc = "(" + credit_type + ") " + desc

            else:
                desc = description.replace('INFO-ED -', '(INFO)').strip()

            items.append((time_obj, 'Credit Mention', desc))
        # Ad
        elif description.startswith('Ad -'):
            desc = description.replace('Ad -', '').strip()
            items.append((time_obj, 'Ad', desc))
    return items

def filter_and_sort(items, start_time, end_time, item_type, reportTxt, removeTimeFlag=False):
    """Filter items by type and time range, remove duplicates, and return sorted list"""
    start_obj = parse_time(start_time)
    end_obj = parse_time(end_time)

    seen = set()  # To track unique descriptions
    filtered = []

    for t, typ, desc in items:
        if typ.lower() != item_type.lower():
            continue
        if not (start_obj <= t < end_obj):
            continue
        if desc not in seen:
            seen.add(desc)
            filtered.append((t, desc))

    # Sort by time
    filtered.sort(key=lambda x: x[0])

    report = print_report(filtered, start_time, end_time, item_type, removeTimeFlag)
    # print(report)

    return reportTxt + report

def print_report(items, start_time, end_time, item_type, removeTimeFlag):
    """
    Return a formatted report string instead of printing
    """
    lines = []

    lines.append(f"\nFrom {start_time} to {end_time} - {item_type}")
    if(removeTimeFlag==False):
        lines.append("=" * 80)    
        lines.append(f"{'Time':<10} {'Description':<70}")
    lines.append("-" * 80)

    if items:
        for t, desc in items:
            time_str = t.strftime('%I:%M%p').lstrip('0').lower()
            if(removeTimeFlag==False):
                lines.append(f"{time_str:<10} {desc:<70}")
            else:
                lines.append(f"{desc:<70}")
    else:
        lines.append("No items found")

    lines.append("")  # Extra newline at the end

    return "\n".join(lines)

def getTitleForAI(title, startTime, duration):
    title = title.replace("CM/", "Credit Mention - ")
    title = title.replace("$SPON - ", "")

    str = ''
    leadThreshold = 10
    adThreshold = 30
    spThreshold = 45
    minutes, seconds = map(int, duration.split(":"))
    total_seconds = minutes * 60 + seconds
    if total_seconds > spThreshold:
        str = "Special -"
    elif total_seconds == adThreshold:
        str = "Ad -"

    dt = datetime.strptime(startTime, "%Y-%m-%d %H:%M:%S")
    time_12hr = dt.strftime("%I:%M%p").lstrip("0")
    if total_seconds < leadThreshold:
        return ''
    else:
        return f"{time_12hr} : {str}{title}"

def main():
    fetchXML()

if __name__ == "__main__":
    main()