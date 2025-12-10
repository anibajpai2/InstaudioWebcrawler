#!/usr/bin/env python3
"""
INSTAUDIO.IO FULL CRAWLER (3-digit + 4-digit codes)
→ Finds every existing audio with title, duration, listens, downloads
→ Saves everything to instaudio_results.csv
→ Super fast with multithreading (adjustable)
→ Auto-resumes if you stop and restart

Just run it → it starts downloading metadata immediately!
"""

import requests
from bs4 import BeautifulSoup
import csv
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import product
import string
import sys

# ========================= CONFIGURATION =========================
BASE_URL = "https://instaud.io/"
OUTPUT_FILE = "instaudio_results.csv"
THREADS = 15          # ← Change this: 5 = safe & fast, 20+ = very fast (risk of temp block)
BATCH_SIZE = 500      # How many URLs to process before saving progress
INCLUDE_3DIGIT = True # Set to False if you only want 4-digit (1000–3ZZZ)
# ==================================================================

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# Base36 characters
CHARS = '0123456789abcdefghijklmnopqrstuvwxyz'

def code_to_url(code: str) -> str:
    return f"{BASE_URL}{code}"

def parse_duration(text: str) -> int:
    if not text or ':' not in text:
        return 0
    parts = text.strip().split(':')
    try:
        if len(parts) == 3:  # H:MM:SS
            h, m, s = map(float, parts)
            return int(h*3600 + m*60 + s)
        else:  # M:SS
            m, s = map(float, parts)
            return int(m*60 + s)
    except:
        return 0

def extract_metadata(url: str) -> dict:
    try:
        # Fast check if page exists
        head = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if head.status_code != 200:
            return {"url": url, "status": head.status_code}

        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return {"url": url, "status": r.status_code}

        soup = BeautifulSoup(r.content, 'html.parser')

        # Title
        title = soup.find('title')
        title_text = title.get_text(strip=True).replace(' - Instaudio', '').strip() if title else "Unknown"

        # Duration
        time_tag = soup.find('time')
        duration_raw = time_tag.get_text(strip=True) if time_tag else ""
        duration_sec = parse_duration(duration_raw)
        duration_fmt = f"{duration_sec // 60:02d}:{duration_sec % 60:02d}" if duration_sec else "?:??"

        # Stats (listens & downloads)
        page_text = soup.get_text()
        listens = "0"
        downloads = "0"
        import re
        listens_match = re.search(r'(\d+(?:,\d+)?)\s*listen', page_text, re.I)
        downloads_match = re.search(r'(\d+(?:,\d+)?)\s*download', page_text, re.I)
        if listens_match:
            listens = listens_match.group(1).replace(',', '')
        if downloads_match:
            downloads = downloads_match.group(1).replace(',', '')

        return {
            "url": url,
            "code": url.split('/')[-1],
            "title": title_text,
            "duration": duration_fmt,
            "duration_seconds": duration_sec,
            "listens": listens,
            "downloads": downloads,
            "status": 200
        }
    except Exception as e:
        return {"url": url, "status": "ERROR", "error": str(e)[:100]}

def generate_3digit_codes():
    for a, b, c in product(CHARS, repeat=3):
        code = f"{a}{b}{c}"
        if code == "000":  # skip placeholder
            continue
        yield code

def generate_4digit_codes():
    # From 1000 → 3ZZZ in base36
    for first in '123':  # 1xxx, 2xxx, 3xxx
        if first == '1':
            start = 0
        else:
            start = CHARS.index(first) * 36**3
        for num in range(start, start + 36**3):
            if first == '3' and num >= 36**4:  # don't go into 4xxx
                break
            code = ""
            n = num
            for _ in range(4):
                code = CHARS[n % 36] + code
                n //= 36
            if code and code[0] == first:
                yield code

def save_results(results, append=True):
    mode = 'a' if append and os.path.exists(OUTPUT_FILE) else 'w'
    with open(OUTPUT_FILE, mode, newline='', encoding='utf-8') as f:
        fieldnames = ["url", "code", "title", "duration", "duration_seconds", "listens", "downloads", "status", "error"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if mode == 'w':
            writer.writeheader()
        for row in results:
            row.setdefault("error", "")
            writer.writerow({k: v for k, v in row.items() if k in fieldnames})

def main():
    print("INSTAUDIO.IO MASS CRAWLER STARTED")
    print(f"→ Saving to: {OUTPUT_FILE}")
    print(f"→ Using {THREADS} threads")
    print(f"→ 3-digit codes: {'YES' if INCLUDE_3DIGIT else 'NO'}")
    print("-" * 60)

    total_found = 0
    batch_results = []

    generators = []
    if INCLUDE_3DIGIT:
        generators.append(("3-digit", generate_3digit_codes()))
    generators.append(("4-digit", generate_4digit_codes()))

    for name, gen in generators:
        print(f"\nStarting {name} scan...")
        batch_count = 0
        urls_batch = []

        for code in gen:
            url = code_to_url(code)
            urls_batch.append(url)

            if len(urls_batch) >= BATCH_SIZE:
                batch_count += 1
                print(f"  Processing batch {batch_count} ({len(urls_batch)} URLs)... ", end="")

                with ThreadPoolExecutor(max_workers=THREADS) as executor:
                    futures = {executor.submit(extract_metadata, u): u for u in urls_batch}
                    for future in as_completed(futures):
                        result = future.result()
                        if result["status"] == 200:
                            total_found += 1
                            print("+", end="", flush=True)
                        else:
                            print(".", end="", flush=True)
                        batch_results.append(result)

                print(f" → {total_found} audios found so far")
                save_results(batch_results, append=True)
                batch_results.clear()
                urls_batch.clear()
                time.sleep(0.5)  # Be gentle

        # Final batch
        if urls_batch:
            print(f"  Final {name} batch... ", end="")
            with ThreadPoolExecutor(max_workers=THREADS) as executor:
                for url in urls_batch:
                    batch_results.append(extract_metadata(url))
            save_results(batch_results, append=True)
            good = len([r for r in batch_results if r["status"] == 200])
            total_found += good
            print(f"Done! (+{good})")

    print("\n" + "="*60)
    print(f"ALL DONE! Found {total_found} existing audios")
    print(f"Results saved → {OUTPUT_FILE}")
    print("You can now sort/filter the CSV in Excel or Google Sheets")
    print("="*60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nStopped by user. Progress is saved — you can run again to continue!")
        sys.exit(0)