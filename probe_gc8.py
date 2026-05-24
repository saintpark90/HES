import requests
import json
import sys

GID = "20260422HHLG0"
# leId=1, srId=0, seasonId=2026, groupSc=SEASON and LAST5
BASE_WS = "https://www.koreabaseball.com/ws"

for group in ["SEASON", "LAST5"]:
    payload = {
        "leId": "1",
        "srId": "0",
        "seasonId": "2026",
        "gameId": GID,
        "groupSc": group,
    }
    r = requests.post(
        f"{BASE_WS}/Schedule.asmx/GetTeamRecord",
        data=payload,
        timeout=10,
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.koreabaseball.com/"},
    )
    txt = r.content.decode("utf-8-sig", errors="replace")
    print(f"\n=== GetTeamRecord groupSc={group} (status={r.status_code}) ===")
    if txt.strip().startswith("{") or txt.strip().startswith("["):
        data = json.loads(txt)
        sys.stdout.buffer.write((json.dumps(data, ensure_ascii=False, indent=2)[:2000] + "\n").encode("utf-8"))
    else:
        sys.stdout.buffer.write(txt[:500].encode("utf-8", errors="replace"))
        print()
