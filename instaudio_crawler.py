#!/usr/bin/env python3
"""
Modernized instaud.io crawler (asyncio + aiohttp)
Much lower memory & CPU usage, better concurrency
"""
import asyncio
import csv
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

import aiohttp
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm_asyncio

# ────────────────────────────────────────────────
#  CONFIG
# ────────────────────────────────────────────────

BASE_URL = "https://instaud.io/"
OUTPUT_FILE = Path("instaudio_results.csv")
CONCURRENT = 80              # tune: 40–150 depending on your connection
BATCH_SIZE = 2000            # save every X items
INCLUDE_3DIGIT = True
MIN_CODE_LENGTH = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
}

CHARS = "0123456789abcdefghijklmnopqrstuvwxyz"

# ────────────────────────────────────────────────

@dataclass
class AudioEntry:
    code: str
    url: str
    status: int | str
    title: str = ""
    duration: str = ""
    duration_sec: int = 0
    listens: str = "0"
    downloads: str = "0"
    error: str = ""

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "url": self.url,
            "status": self.status,
            "title": self.title,
            "duration": self.duration,
            "duration_seconds": self.duration_sec,
            "listens": self.listens,
            "downloads": self.downloads,
            "error": self.error,
        }


def parse_duration(text: str) -> tuple[int, str]:
    if not text or ":" not in text:
        return 0, "?:??"
    try:
        parts = [float(p) for p in text.strip().split(":")]
        if len(parts) == 3:  # h:mm:ss
            sec = int(parts[0] * 3600 + parts[1] * 60 + parts[2])
        else:  # mm:ss
            sec = int(parts[0] * 60 + parts[1])
        return sec, f"{sec // 60:02d}:{sec % 60:02d}"
    except:
        return 0, "?:??"


async def fetch_metadata(
    session: aiohttp.ClientSession, code: str
) -> AudioEntry:
    url = f"{BASE_URL}{code}"
    entry = AudioEntry(code=code, url=url, status="UNKNOWN")

    try:
        async with session.get(url, headers=HEADERS, timeout=ClientTimeout(total=12)) as resp:
            entry.status = resp.status
            if resp.status != 200:
                return entry

            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")

            # Title
            title_tag = soup.find("title")
            if title_tag:
                entry.title = (
                    title_tag.get_text(strip=True)
                    .removesuffix(" - Instaudio")
                    .strip()
                ) or "Unknown"

            # Duration
            time_tag = soup.find("time")
            if time_tag:
                dur_text = time_tag.get_text(strip=True)
                entry.duration_sec, entry.duration = parse_duration(dur_text)

            # Listens & downloads (fallback to regex if structure changed)
            text = soup.get_text(separator=" ", strip=True)
            import re

            if m := re.search(r"(\d+(?:,\d+)?)\s*listen", text, re.I):
                entry.listens = m.group(1).replace(",", "")
            if m := re.search(r"(\d+(?:,\d+)?)\s*download", text, re.I):
                entry.downloads = m.group(1).replace(",", "")

    except Exception as e:
        entry.status = "ERROR"
        entry.error = str(e)[:120]

    return entry


def code_generator(min_len: int = 3, max_len: int = 4) -> AsyncGenerator[str, None]:
    """Generate base36 codes from length min_len to max_len"""
    for length in range(min_len, max_len + 1):
        if length == 3 and not INCLUDE_3DIGIT:
            continue
        # We could skip "000" etc. here if desired
        for i in range(36**length):
            code = ""
            n = i
            for _ in range(length):
                code = CHARS[n % 36] + code
                n //= 36
            # Optional: skip padded zeros if you want
            # if code.lstrip("0") == "": continue
            yield code


async def main():
    OUTPUT_FILE.unlink(missing_ok=True)  # optional: start fresh

    total = 0
    batch: list[AudioEntry] = []
    start_time = time.monotonic()

    connector = aiohttp.TCPConnector(limit=CONCURRENT + 10)
    async with aiohttp.ClientSession(connector=connector) as session:
        codes = code_generator(MIN_CODE_LENGTH, 4)
        tasks = []

        async for code in tqdm_asyncio(codes, desc="Scanning codes", unit="code"):
            tasks.append(fetch_metadata(session, code))

            if len(tasks) >= CONCURRENT * 2:  # oversubscribe a bit
                done, tasks = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )
                for fut in done:
                    entry = await fut
                    total += 1
                    if entry.status == 200:
                        print(f"  HIT → {entry.code}  {entry.title[:48]}", flush=True)
                    batch.append(entry)

                    if len(batch) >= BATCH_SIZE:
                        await save_batch(batch)
                        batch.clear()

        # Drain remaining tasks
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    continue
                batch.append(r)
                total += 1

        if batch:
            await save_batch(batch)

    elapsed = time.monotonic() - start_time
    print(f"\nFinished. Found {total:,} checked codes in {elapsed:.1f} s")
    print(f"Results → {OUTPUT_FILE}")


async def save_batch(entries: list[AudioEntry]):
    if not entries:
        return

    fieldnames = [
        "code",
        "url",
        "status",
        "title",
        "duration",
        "duration_seconds",
        "listens",
        "downloads",
        "error",
    ]

    mode = "a" if OUTPUT_FILE.exists() else "w"
    with OUTPUT_FILE.open(mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if mode == "w":
            writer.writeheader()
        writer.writerows(e.as_dict() for e in entries)

    print(f"  Saved {len(entries):,} rows", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted. Partial results saved.")
