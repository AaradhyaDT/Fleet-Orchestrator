"""
AI Fellowship 2026 Batch Recording Downloader
Extracts recording URLs from the official calendar iCal feed and downloads them using authenticated session/cookies.
"""

import os
import sys
import re
import argparse
import urllib.request
from collections import defaultdict

ICAL_URL = "https://calendar.google.com/calendar/ical/c_classroom9685d89d%40group.calendar.google.com/public/basic.ics"

def parse_calendar(ical_url):
    req = urllib.request.Request(ical_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        raw = resp.read().decode('utf-8')

    unfolded = re.sub(r'\r?\n[ \t]', '', raw)
    events = unfolded.split("BEGIN:VEVENT")

    records = []
    for block in events[1:]:
        end_idx = block.find("END:VEVENT")
        if end_idx != -1:
            block = block[:end_idx]

        summary_match = re.search(r'^SUMMARY:(.*)$', block, re.M)
        summary = summary_match.group(1).strip() if summary_match else "Untitled"
        summary = summary.replace(r'\,', ',').replace(r'\;', ';')

        dtstart_match = re.search(r'^DTSTART.*?:(\d{8}(?:T\d{6}Z?)?)', block, re.M)
        dtstart = dtstart_match.group(1) if dtstart_match else ""
        date_str = f"{dtstart[:4]}-{dtstart[4:6]}-{dtstart[6:8]}" if len(dtstart) >= 8 else "Unknown"

        videos = []
        for line in block.splitlines():
            if line.startswith("ATTACH"):
                fn_match = re.search(r'FILENAME="?([^;":]+)"?', line)
                fn = fn_match.group(1) if fn_match else ""
                url_match = re.search(r'https?://[^\s]+', line)
                att_url = url_match.group(0) if url_match else ""
                fmt_match = re.search(r'FMTTYPE=([^;:]+)', line)
                fmt = fmt_match.group(1) if fmt_match else ""
                if "video" in fmt or "Recording" in fn:
                    # extract file ID
                    fid_match = re.search(r'/d/([a-zA-Z0-9_-]+)', att_url)
                    fid = fid_match.group(1) if fid_match else ""
                    videos.append({
                        "filename": fn or f"{summary} - {date_str}.mp4",
                        "url": att_url,
                        "file_id": fid
                    })

        if not videos:
            continue

        summary_lower = summary.lower()
        if "guest" in summary_lower:
            cat = "guest"
        elif "week" in summary_lower or "wk" in summary_lower:
            cat = "lectures"
        elif "office hour" in summary_lower or "kss" in summary_lower:
            cat = "office-hours"
        elif "ta" in summary_lower:
            cat = "ta"
        else:
            cat = "other"

        records.append({
            "summary": summary,
            "date": date_str,
            "raw_date": dtstart,
            "category": cat,
            "videos": videos
        })

    records.sort(key=lambda x: (x["raw_date"], x["summary"]))
    return records

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', '_', name).strip()

def main():
    parser = argparse.ArgumentParser(description="Batch download AI Fellowship recordings.")
    parser.add_argument("--category", choices=["all", "lectures", "office-hours", "ta", "guest"], default="lectures",
                        help="Category of recordings to download (default: lectures)")
    parser.add_argument("--outdir", default="./downloads", help="Directory where files will be saved")
    parser.add_argument("--cookies", help="Path to cookies.txt (exported from browser with fellowship login)")
    parser.add_argument("--export-urls", help="Path to save a plain text list of direct Drive URLs", default=None)
    args = parser.parse_args()

    records = parse_calendar(ICAL_URL)
    
    if args.category != "all":
        selected = [r for r in records if r["category"] == args.category]
    else:
        selected = records

    total_videos = sum(len(r["videos"]) for r in selected)
    print(f"Selected category: '{args.category}' -> Found {len(selected)} sessions with {total_videos} video recordings.")

    if args.export_urls:
        with open(args.export_urls, "w", encoding="utf-8") as f:
            for r in selected:
                for v in r["videos"]:
                    f.write(f"{v['url']}\t{r['date']}_{sanitize_filename(r['summary'])}_{sanitize_filename(v['filename'])}\n")
        print(f"URLs exported to {args.export_urls}")
        return

    print("\nTo download these Google Drive recordings automatically:")
    print("1. Because Fusemachines restricts recordings to fellowship accounts, export cookies from Chrome into 'cookies.txt'")
    print("   (e.g., using 'Get cookies.txt LOCALLY' extension while logged into Google Drive).")
    print("2. Run aria2c or yt-dlp:")
    print(f"   aria2c --load-cookies cookies.txt -i urls.txt -j 4")
    print(f"   or use gdown with cookies.")

if __name__ == "__main__":
    main()
