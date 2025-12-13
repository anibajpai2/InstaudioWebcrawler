Instaudio.io Full Crawler

A fast, multithreaded Python crawler that discovers and extracts metadata from every existing public audio on instaud.io (3-digit and 4-digit codes).

Note (as of December 2025): The current instaud.io appears to be a revived or cloned version of the original site, which officially shut down in 2019. The crawler should still work if the URL structure and page layout remain similar, but results may vary (e.g., fewer or different audios).

It systematically checks all possible short codes, fetches the page only for valid ones, and saves:

    URL
    Code
    Title
    Duration (formatted + seconds)
    Listens count
    Downloads count

Results are saved progressively to instaudio_results.csv so the script can be stopped and resumed at any time without losing progress.
Features

    Scans all 3-digit codes (optional) and all 4-digit codes (1000–3ZZZ in base36)
    Super fast with multithreading (default 15 threads)
    Auto-resumes: already processed batches stay in the CSV
    Polite delays between batches to reduce risk of temporary blocks
    Handles errors gracefully
    Outputs clean CSV ready for Excel/Google Sheets analysis

Requirements

    Python 3.6+
    Required packages:
    Bash

    pip install requests beautifulsoup4

Usage

    Save the crawler script as instaudio_crawler.py (or similar).
    (Optional) Edit configuration in the script:
    Python

THREADS = 15          # Increase for faster crawling (20+ is very fast, but higher risk of temp block)
INCLUDE_3DIGIT = True # Set to False if you only want 4-digit codes
BATCH_SIZE = 500      # How many URLs per batch before saving

Run the script:
Bash

    python3 instaudio_crawler.py

The script will immediately start processing and printing progress like:
text

+ for valid audio found
. for non-existent code

Progress is saved every batch (~500 URLs) to instaudio_results.csv.

You can safely stop with Ctrl+C at any time — just rerun the script later and it will continue (already saved rows remain).
Output Example (instaudio_results.csv)
url	code	title	duration	duration_seconds	listens	downloads	status	error
https://instaud.io/abc	abc	Funny cat meow	00:12	12	5421	892	200	
https://instaud.io/1000	1000	Test recording	01:45	105	123	45	200	
Important Notes & Disclaimer

    This tool is for research and archival purposes only.
    Instaud.io is a public anonymous audio hosting service. Only public audios (those with short codes) are accessed.
    The script respects basic crawling etiquette (User-Agent header, delays between batches).
    Running with very high thread counts or without delays may result in temporary IP blocking by the site.
    The site may have changed since the original shutdown in 2019; test on a small batch first.
    Use responsibly and at your own risk.
