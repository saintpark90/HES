import requests
import json
import sys
import re

GID = "20260422HHLG0"
BASE_WS = "https://www.koreabaseball.com/ws"

endpoints = [
    ("Schedule.asmx/GetTeamRecord",        {"gameId": GID}),
    ("Schedule.asmx/GetTeamKeyPlayer",     {"gameId": GID}),
    ("Schedule.asmx/GetPitcherRecordAnalysis", {"gameId": GID}),
]

for path, payload in endpoints:
    url = f"{BASE_WS}/{path}"
    r = requests.post(url, data=payload, timeout=10,
                      headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.koreabaseball.com/"})
    try:
        txt = r.content.decode("utf-8-sig")
    except Exception:
        txt = r.content.decode("euc-kr", errors="replace")

    print(f"\n=== {path.split('/')[-1]} ({r.status_code}, len={len(txt)}) ===")
    
    if txt.strip().startswith("{") or txt.strip().startswith("["):
        data = json.loads(txt)
        sys.stdout.buffer.write((json.dumps(data, ensure_ascii=False, indent=2)[:1500] + "\n").encode("utf-8"))
    else:
        # Try XML
        sys.stdout.buffer.write(txt[:1000].encode("utf-8", errors="replace"))
        print()
