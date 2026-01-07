import httpx
import random
import os
import re
# ================= CONFIG =================
MIN_EVENTS = 1
MAX_EVENTS = 7
REQUEST_TIMES = 500
STAKE_AMOUNT = 500
PARTNER_ID = 55

# Choose ONE sport only (VERY IMPORTANT)
# Common IDs (may vary slightly):
# Football = 1, Basketball = 3, Tennis = 4, Hockey = 2
TARGET_SPORT_ID = 3   # 🏀 Basketball (example)

# Express-safe market types (START CONSERVATIVE)
ALLOWED_MARKET_TYPES = {
    1,    # Win 1
    2,    # Draw
    3,    # Win 2
    7,    # Handicap / basic
    8,    # Totals
}

EXPRESS_URL = "https://1xbet.cm/service-api/main-line-feed/v1/expressDay"
SAVE_URL = "https://1xbet.cm/service-api/LiveBet/Open/SaveCoupon"

PARAMS = {
    "cfView": 3,
    "country": 84,
    "gr": 654,
    "lng": "fr",
    "ref": PARTNER_ID
}

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Content-Type": "application/json"
}
# =========================================


def flatten_events(feed):
    """Remove duplicates by GameId"""
    events = []
    seen = set()

    for exp in feed:
        for ev in exp.get("events", []):
            gid = ev["id"]
            if gid not in seen:
                seen.add(gid)
                events.append(ev)

    return events


def filter_events(events):
    filtered = []

    for ev in events:
        # 🔒 HARD VALIDATION (mandatory fields)
        sport = ev.get("sport")
        event_data = ev.get("event")

        if not sport or not event_data:
            continue

        if "id" not in sport or "type" not in event_data or "cf" not in event_data:
            continue

        # 🎯 RULES
        if sport["id"] != TARGET_SPORT_ID:
            continue

        if ev.get("kind") != 3:  # prematch only
            continue

        if event_data["type"] not in ALLOWED_MARKET_TYPES:
            continue

        filtered.append(ev)

    return filtered


def build_event(ev):
    return {
        "GameId": ev["id"],
        "Type": ev["event"]["type"],
        "Coef": ev["event"]["cf"],
        "Param": 0,
        "PV": None,
        "PlayerId": 0,
        "Kind": ev["kind"],
        "InstrumentId": 0,
        "Seconds": 0,
        "Price": 0,
        "Expired": 0,
        "PlayersDuel": []
    }

def split_codes_among_files(nletter, n=1):
    random.shuffle(nletter)
    base_size = len(nletter) // n
    remainder = len(nletter) % n
    result = []
    start = 0
    for i in range(n):
        extra = 1 if i < remainder else 0
        end = start + base_size + extra
        result.append(nletter[start:end])
        start = end
    return result

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

WORKER_FILES = [os.path.join(BASE_DIR, f"AV{i}.py") for i in range(1, 19)]

def update_bxx_file(fname, new_codes):
    if not os.path.exists(fname):
        print(f"⚠️ {os.path.basename(fname)} not found, skipping.")
        return

    with open(fname, 'r', encoding='utf-8') as f:
        content = f.read()

    new_list_str = f"PREFIXES = {new_codes!r}"
    content, count = re.subn(r'PREFIXES\s*=\s*\[.*?]', new_list_str, content, flags=re.DOTALL)


    if count == 0:
        print("Fails")
        return

    # Remove pop_random_code_from_file and loading loop
    content = re.sub(
        r'def\s+pop_random_code_from_file\s*\(.*?\)\s*:\s*(?:\n\s+.*)+?(?=\n\S)',
        '',
        content,
        flags=re.DOTALL
    )
    content = re.sub(
        r'print\("⏳ Loading real prefixes.*?print\(f"✅ Loaded.*?\n',
        '',
        content,
        flags=re.DOTALL
    )

    with open(fname, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ {fname}: updated list with {len(new_codes)} codes and removed unused logic.")

def update_all_bxx(prefixes):
    if not prefixes:
        print("❌ No prefixes to distribute")
        return

    n = len(WORKER_FILES)
    groups = split_codes_among_files(prefixes, n=n)

    for fname, group in zip(WORKER_FILES, groups):
        update_bxx_file(fname, group)

    print("\n✅ PREFIX DISTRIBUTION COMPLETE")
    for fname, group in zip(WORKER_FILES, groups):
        print(f"{fname}: {len(group)} prefixes")
def fetcher():
    prefix_set = set()  # 🔹 store unique first-two-letter prefixes

    with httpx.Client(headers=HEADERS, timeout=20) as client:
        # 1️⃣ Fetch express feed
        response = client.get(EXPRESS_URL, params=PARAMS)
        response.raise_for_status()
        feed = response.json()

        # 2️⃣ Flatten & filter events
        all_events = flatten_events(feed)
        usable_events = filter_events(all_events)

        total_events = len(all_events)
        usable_count = len(usable_events)

        print()

        # 3️⃣ Hard guard
        if usable_count < MIN_EVENTS:
            print("❌ NOT ENOUGH VALID EVENTS TO BUILD A COUPON")
            return

        # 4️⃣ Cap selection size
        actual_max = min(MAX_EVENTS, usable_count)

        # 5️⃣ Generate coupons
        for i in range(REQUEST_TIMES):
            count = random.randint(MIN_EVENTS, actual_max)
            selected = random.sample(usable_events, count)

            payload_events = []

            for idx, ev in enumerate(selected, start=1):
                payload_events.append(build_event(ev))

            payload = {
                "notWait": True,
                "CheckCf": 1,
                "partner": PARTNER_ID,
                "Summ": STAKE_AMOUNT,
                "Events": payload_events,
                "Vid": 1
            }

            save_resp = client.post(SAVE_URL, json=payload)
            save_resp.raise_for_status()
            data = save_resp.json()

            print("\n--- SAVE COUPON RESPONSE ---")

            if data.get("Success"):
                code = data["Value"]
                print(f"✅ GENERATED CODE: {code}")

                # 🔹 collect first two letters
                prefix_set.add(code[:2])
            else:
                print("❌ COUPON FAILED")

            print("=" * 70)

    # 6️⃣ Final result
    prefix_list = list(prefix_set)

    print("\n================ FINAL PREFIX RESULT ================")
    print("PREFIX LIST :", prefix_list)
    print("PREFIX COUNT:", len(prefix_list))
    print("=====================================================")
    return prefix_list

def main():
    prefixes = fetcher()
    update_all_bxx(prefixes)



if __name__ == "__main__":
    main()
