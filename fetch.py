import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
import json
import re
from zoneinfo import ZoneInfo

numberToFetch = "50"

rawJsonPath = f"json/"

def fetchXML():

    start, end = get_time_window()
    print(f"Time Window: {start} to {end}")

    now_sg = datetime.now(ZoneInfo("Asia/Singapore"))
    fileName = now_sg.strftime("%Y%m%d_%H%M%S")
    jsonPath = f"{rawJsonPath}{fileName}.json"
    print("Raw JSON Path:", jsonPath)

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
    
    # Save JSON
    with open(jsonPath, "w", encoding="utf-8") as f:
        json.dump(sorted_data, f, indent=2, ensure_ascii=False)

    report(sorted_data)

def get_time_window(now_sg=None):
    if not now_sg:
        now_sg = datetime.now(ZoneInfo("Asia/Singapore"))

    hour = now_sg.hour  # 0–23

    print("Current Time:", now_sg.strftime("%I:%M %p"))
    print("Current Hour:", hour)

    if hour in (9, 10, 11):        # 9am, 10am, 11am
        return "6:00AM", "10:00AM"

    elif hour in (13, 14):    # 1pm, 2pm
        return "10:00AM", "2:00PM"

    elif hour in (16, 17):    # 4pm, 5pm
        return "2:00PM", "5:00PM"

    elif hour in (21, 22, 23, 0):    # 9pm, 10pm, 11pm
        return "5:00PM", "9:00PM"

    else:
        return None, None

def report(unique_data):

    start, end = get_time_window()
    print(f"Time Window: {start} to {end}")

    # ===========================
    titleTxtArray = []
    for epoch, details in unique_data.items():
        str = getTitleForAI(details["Title"], details["StartTime"], details["Duration"])
        if(str != ''):
            titleTxtArray.append(str)

    print(titleTxtArray)

    all_items = parse_schedule(titleTxtArray)


    reportTxt = ""
    reportTxt = filter_and_sort(all_items, start, end, "Credit Mention", reportTxt, True)
    reportTxt = filter_and_sort(all_items, start, end, "Ad", reportTxt, True)
    reportTxt = filter_and_sort(all_items, start, end, "Credit Mention", reportTxt)
    reportTxt = filter_and_sort(all_items, start, end, "Ad", reportTxt)

    print(reportTxt)

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
    # data={"1765971562446": {"Title": "$SPON - NHB - TAMIL YOUTH FESTIVAL 2026", "StartTime": "2025-12-17 19:39:22", "Duration": "0:29"}, "1765971592384": {"Title": "$SPON - JOYALUKKAS JEWELLERY BRANDING (SCRATCH & WIN CAMPAIGN)", "StartTime": "2025-12-17 19:39:52", "Duration": "0:30"}, "1765971622130": {"Title": "$SPON - INFO-ED - KNP - COOKING TIPS - WEDNESDAY", "StartTime": "2025-12-17 19:40:22", "Duration": "1:03"}, "1765972000870": {"Title": "$SPON - (CM/TRAFFIC WATCH) SRI AMBIKAS - OOTY GOLD PONNI RICE", "StartTime": "2025-12-17 19:46:40", "Duration": "0:12"}, "1765972012567": {"Title": "$SPON - MDDI - ANTI VAPE EXPLAINER (CAPSULE #2: VAPING IS HARMFUL)", "StartTime": "2025-12-17 19:46:52", "Duration": "1:00"}, "1765972072618": {"Title": "$SPON - PIZZAHUT - CHRISTMAS CHEESY BITES PERFORMANCE CAMPAIGN (PH 2B- MOLLY PWP WITH CHEESY BITES BUNDLE)", "StartTime": "2025-12-17 19:47:52", "Duration": "0:40"}, "1765972777716": {"Title": "$SPON - RKG GHEE - TIMEBELT JINGLE", "StartTime": "2025-12-17 19:59:37", "Duration": "0:16"}, "1765972793947": {"Title": "$SPON - (CM/BEFORE NEWS TIME CHECK) GAYATRI RESTAURANT VER 1", "StartTime": "2025-12-17 19:59:53", "Duration": "0:12"}, "1765973223537": {"Title": "$SPON - (CM/AFTER NEWS TIME CHECK) GAYATRI RESTAURANT VER 2", "StartTime": "2025-12-17 20:07:03", "Duration": "0:11"}, "1765973233367": {"Title": "$SPON - (PRE PUB TRA - EB EXTENTED) HALEON SG - CALTRATE - FUN & FIT 2026 [15/12/25-01/01/26]", "StartTime": "2025-12-17 20:07:13", "Duration": "1:05"}, "1765973298222": {"Title": "$SPON - SG MOTORSHOW - MOTORSHOW 2026 (TEASER/SAVE THE DATE)", "StartTime": "2025-12-17 20:08:18", "Duration": "0:30"}, "1765973854579": {"Title": "$SPON - M1 - CHRISTMAS SALE - EOY CAMPAIGN (FOMO-RRP V1)", "StartTime": "2025-12-17 20:17:34", "Duration": "0:35"}, "1765973889541": {"Title": "$SPON - TV(5) - CARABAO CUP 2025/26 (QUARTER FINALS V.)", "StartTime": "2025-12-17 20:18:09", "Duration": "0:30"}, "1765975074804": {"Title": "$SPON - COTHAS COFFEE", "StartTime": "2025-12-17 20:37:54", "Duration": "0:30"}, "1765975105444": {"Title": "$SPON - VANTAGE AUTOMOTIVE - BYD (SCRIPT 1)", "StartTime": "2025-12-17 20:38:25", "Duration": "0:30"}, "1765976101630": {"Title": "$SPON - TRANS ORIENT - MILKY MIST THAYIR (CURD)", "StartTime": "2025-12-17 20:55:01", "Duration": "0:30"}, "1765976131061": {"Title": "$SPON - TAJ EMPLOYMENT AGENCY ", "StartTime": "2025-12-17 20:55:31", "Duration": "0:30"}, "1765976160706": {"Title": "$SPON - TV(5) - CARABAO CUP 2025/26 (QUARTER FINALS V.)", "StartTime": "2025-12-17 20:56:00", "Duration": "0:30"}, "1765976826525": {"Title": "$SPON - M1 - CHRISTMAS SALE - EOY CAMPAIGN (FOMO-RRP V1)", "StartTime": "2025-12-17 21:07:06", "Duration": "0:35"}, "1765977296219": {"Title": "$SPON - (CM/MOTIVATIONAL QUOTES) SP MUTHIAH & SONS - GOLD PONNI RICE", "StartTime": "2025-12-17 21:14:56", "Duration": "0:12"}, "1765977511737": {"Title": "$SPON - (CM/YOUTH'S CHOICE SONGS) ALKA JEWELLERS - GENERIC VER 2", "StartTime": "2025-12-17 21:18:31", "Duration": "0:17"}, "1765977549760": {"Title": "$SPON - (CM/TRAFFIC WATCH) SRI AMBIKAS - OOTY GOLD PONNI RICE", "StartTime": "2025-12-17 21:19:09", "Duration": "0:12"}, "1765977789981": {"Title": "$SPON - (CM/ALL DAY HITS) SYED - ANARKALI CLASSIC BASMATI RICE VASANTHAM", "StartTime": "2025-12-17 21:23:09", "Duration": "0:16"}, "1765977806160": {"Title": "$SPON - TAJ EMPLOYMENT AGENCY ", "StartTime": "2025-12-17 21:23:26", "Duration": "0:30"}, "1765977835887": {"Title": "$SPON - A2B SWEETS & VEG RESTAURANT VER 2 (SONG)", "StartTime": "2025-12-17 21:23:55", "Duration": "0:30"}, "1765978749228": {"Title": "$SPON - (CM/TRAFFIC WATCH) SRI AMBIKAS - OOTY GOLD PONNI RICE", "StartTime": "2025-12-17 21:39:09", "Duration": "0:12"}, "1765978760937": {"Title": "$SPON - (PUB TRA) BYD VANTAGE AUTO 7AM-8AM SPONSOR ", "StartTime": "2025-12-17 21:39:20", "Duration": "0:45"}, "1765978805615": {"Title": "$SPON - GOODAY IMPEX 2025 (VER 1)", "StartTime": "2025-12-17 21:40:05", "Duration": "0:29"}, "1765979573007": {"Title": "$SPON - (CM/TRAFFIC WATCH) SRI AMBIKAS - OOTY GOLD PONNI RICE", "StartTime": "2025-12-17 21:52:53", "Duration": "0:12"}, "1765979865205": {"Title": "$SPON - (CM/LOVE SONGS) COTHAS COFFEE", "StartTime": "2025-12-17 21:57:45", "Duration": "0:11"}, "1765979877167": {"Title": "$SPON - TAJ EMPLOYMENT AGENCY ", "StartTime": "2025-12-17 21:57:57", "Duration": "0:30"}, "1765979906813": {"Title": "$SPON - A2B SWEETS & VEG RESTAURANT VER 2 (SONG)", "StartTime": "2025-12-17 21:58:26", "Duration": "0:30"}, "1765980151425": {"Title": "$SPON - (CM/ENDRO KETTA NYABAGAM 50S & 60S) SRI AMBIKAS - OOTY GOLD PONNI RICE", "StartTime": "2025-12-17 22:02:31", "Duration": "0:12"}, "1765980163700": {"Title": "$SPON - M1 - CHRISTMAS SALE - EOY CAMPAIGN (FOMO-RRP V1)", "StartTime": "2025-12-17 22:02:43", "Duration": "0:35"}, "1765980198657": {"Title": "$SPON - PIZZAHUT - CHRISTMAS CHEESY BITES PERFORMANCE CAMPAIGN (PH 2B- MOLLY PWP WITH CHEESY BITES BUNDLE)", "StartTime": "2025-12-17 22:03:18", "Duration": "0:40"}, "1765980506560": {"Title": "$SPON - (CM/ALL DAY HITS) SYED - ANARKALI PREMIUM BASMATI RICE", "StartTime": "2025-12-17 22:08:26", "Duration": "0:15"}, "1765980976320": {"Title": "$SPON - INFO-ED - GOODAY - BEAUTY TIPS - WEDNESDAY", "StartTime": "2025-12-17 22:16:16", "Duration": "0:41"}, "1765981016552": {"Title": "$SPON - INFO-ED - JOY - JEWELLERY TIPS - WEDNESDAY", "StartTime": "2025-12-17 22:16:56", "Duration": "1:01"}, "1765981364473": {"Title": "$SPON - (CM/MEENDUM MEENDUM 70S & 80S) SP MUTHIAH & SONS - GOLD PONNI RICE", "StartTime": "2025-12-17 22:22:44", "Duration": "0:15"}, "1765982767914": {"Title": "$SPON - INFO-ED - LKF HEALTH TIPS LEAD-OUT ", "StartTime": "2025-12-17 22:46:07", "Duration": "0:13"}, "1765982780841": {"Title": "$SPON - NHB - TAMIL YOUTH FESTIVAL 2026", "StartTime": "2025-12-17 22:46:20", "Duration": "0:29"}, "1765982812299": {"Title": "$SPON - PIZZAHUT - CHRISTMAS CHEESY BITES PERFORMANCE CAMPAIGN (PH 2B- MOLLY PWP WITH CHEESY BITES BUNDLE)", "StartTime": "2025-12-17 22:46:52", "Duration": "0:40"}, "1765983524019": {"Title": "$SPON - GOODAY IMPEX 2025 (VER 2)", "StartTime": "2025-12-17 22:58:44", "Duration": "0:29"}, "1765983553766": {"Title": "$SPON - TRANS ORIENT - MILKY MIST THAYIR (CURD)", "StartTime": "2025-12-17 22:59:13", "Duration": "0:30"}, "1765985512186": {"Title": "$SPON - (CM/ENDRO KETTA NYABAGAM 50S & 60S) SRI AMBIKAS - OOTY GOLD PONNI RICE", "StartTime": "2025-12-17 23:31:52", "Duration": "0:12"}, "1765985524484": {"Title": "$SPON - PIZZAHUT - CHRISTMAS CHEESY BITES PERFORMANCE CAMPAIGN (PH 2B- MOLLY PWP WITH CHEESY BITES BUNDLE)", "StartTime": "2025-12-17 23:32:04", "Duration": "0:40"}, "1765986399364": {"Title": "$SPON - INFO-ED - ANIMANI - ENTERTAINMENT - LEADOUT ", "StartTime": "2025-12-17 23:46:39", "Duration": "0:14"}, "1765986421322": {"Title": "$SPON - TRANS ORIENT - MILKY MIST THAYIR (CURD)", "StartTime": "2025-12-17 23:47:01", "Duration": "0:30"}, "1765986450723": {"Title": "$SPON - M1 - CHRISTMAS SALE - EOY CAMPAIGN (FOMO-RRP V1)", "StartTime": "2025-12-17 23:47:30", "Duration": "0:35"}, "1765986485714": {"Title": "$SPON - INFO-ED - KNP - COOKING TIPS - WEDNESDAY", "StartTime": "2025-12-17 23:48:05", "Duration": "1:03"}}
    # report(data)

if __name__ == "__main__":
    main()