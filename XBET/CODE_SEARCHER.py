import sys
import httpx
import asyncio
import sqlite3
from datetime import datetime, timedelta, timezone
import smtplib
from email.message import EmailMessage
from pathlib import Path
import random

# ================= CONFIG =================

sys.stdout.reconfigure(line_buffering=True)


MAX_RUNTIME_MINUTES = 355  # ⏱️ CHANGE THIS
START_TIME = datetime.now()
END_TIME = START_TIME + timedelta(minutes=MAX_RUNTIME_MINUTES)

STOP_EVENT = asyncio.Event()
MAX_INITIAL_INVALID = 40
GET_COUPON_URL = "https://1xbet.cm/service-api/LiveBet/Open/GetCoupon"

USER_AGENTS = [
    # Desktop browsers
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/118.0",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:102.0) Gecko/20100101 Firefox/102.0",
    # Mobile browsers
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 11; Pixel 4 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36",
]
# Example list of codes (replace with yours)

SEM_LIMIT = 2  # safe concurrency
# =========================================
def init_db(db_name="XBETOUTPUT.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA cache_size=-50000;")  # ~50MB memory
    cursor.execute("PRAGMA temp_store=MEMORY;")  # faster
    cursor.execute("PRAGMA locking_mode=EXCLUSIVE;")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS codes (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Worker_Id TEXT,
            Label TEXT,
            Code TEXT UNIQUE,
            Teams TEXT,   -- store teams as string, e.g. "Man Utd vs Chelsea"
            Events TEXT,
            Score TEXT,
            Time TEXT,
            Odds TEXT,
            Total_odds TEXT,
            Last_change TEXT,
            Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

PREFIXES = ['7N']

SUFFIX_CHARS = [
    '0','1','2','3','4','5','6','7','8','9',
    'A','B','C','D','E','F','G',"H",'J','K','L',
    'M','N','P','Q','R','S','T','U','V','W',
    'X','Y','Z'
]

MAX_PARALLEL_PREFIXES = int(len(PREFIXES))  # start with 2–4

PREFIX_SEMAPHORE = asyncio.Semaphore(MAX_PARALLEL_PREFIXES)

FAILED_CODES_FILE = "failed_403_codes.log"

def save_failed_code(worker_id, code, reason):
    line = f"{datetime.now().isoformat()} | {worker_id} | {code} | {reason}\n"
    with open(FAILED_CODES_FILE, "a", buffering=1) as f:
        f.write(line)


def ts_to_utc(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


async def fetch_coupon(client, code, sem):
    async with sem:
        payload = {
            "Guid": code,
            "Lng": "fr",
            "partner": "55"
        }

        try:
            r = await client.post(GET_COUPON_URL, json=payload)
            data = r.json()

        except Exception as e:
            print(f"[{code}] ❌ NETWORK ERROR:", e)
            return

        # ❌ Invalid code
        if not data.get("Success"):
            print(f"[{code}] ❌ INVALID — {data.get('Error')}")
            return

        value = data.get("Value")
        if not value:
            print(f"[{code}] ❌ EMPTY RESPONSE")
            return

        events = value.get("Events", [])

        print("\n" + "=" * 70)
        print(f"✅ COUPON {code}")
        print("=" * 70)
        print("Stake      :", value.get("Summ"))
        print("Events     :", len(events))
        print("Partner    :", value.get("partner"))
        print("-" * 70)

        for i, ev in enumerate(events, 1):
            print(f"[{i}] {ev.get('Opp1')} vs {ev.get('Opp2')}")
            print("    Sport  :", ev.get("SportNameEng"))
            print("    League :", ev.get("Liga"))
            print("    Market :", ev.get("GroupName"), "-", ev.get("MarketName"))
            print("    Odds   :", ev.get("Coef"))
            print("    Start  :", ts_to_utc(ev.get("Start")))
            print("    GameId :", ev.get("GameId"))
            print()

        print("=" * 70)


async def main():
    sem = asyncio.Semaphore(SEM_LIMIT)

    async with httpx.AsyncClient(
        headers=HEADERS,
        timeout=15,
    ) as client:

        tasks = [
            fetch_coupon(client, code, sem)
            for code in COUPON_CODES
        ]

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
