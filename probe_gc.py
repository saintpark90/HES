import requests
import re
import json

GID = "20260422HHLG0"

# 1. Try GameCenter page - look for ws endpoints
url = f"https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx?leId=1&srId=0&gameId={GID}"
r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
# try various encodings
for enc in ["utf-8", "euc-kr", "utf-8-sig"]:
    try:
        safe = r.content.decode(enc, errors="replace")
        break
    except Exception:
        pass

ws_calls = re.findall(r"[A-Za-z_]+\.asmx[^\s\"'<>]{0,80}", safe)
print("=== ASMX refs ===")
for w in sorted(set(ws_calls))[:30]:
    print(w)

# 2. Try direct JSON endpoints seen on KBO sites
print("\n=== Probing JSON endpoints ===")
candidates = [
    ("https://www.koreabaseball.com/ws/GameCenter.asmx/GetTeamCompareInfo", {"gameId": GID}),
    ("https://www.koreabaseball.com/ws/GameCenter.asmx/GetTeamCompareStat", {"gameId": GID}),
    ("https://www.koreabaseball.com/ws/GameCenter.asmx/GetTeamPowerCompare", {"gameId": GID}),
    ("https://www.koreabaseball.com/ws/Main.asmx/GetTeamStat", {"gameId": GID}),
    ("https://www.koreabaseball.com/ws/Schedule.asmx/GetTeamCompare", {"gameId": GID}),
    ("https://www.koreabaseball.com/ws/GameCenter.asmx/GetLineUp", {"gameId": GID}),
    ("https://www.koreabaseball.com/ws/GameCenter.asmx/GetBoxScore", {"gameId": GID}),
    ("https://www.koreabaseball.com/ws/GameCenter.asmx/GetPitchLog", {"gameId": GID}),
]
for url2, payload in candidates:
    try:
        r2 = requests.post(url2, data=payload, timeout=5)
        txt = r2.content.decode("utf-8-sig", errors="replace")
        is_json = txt.strip().startswith("{") or txt.strip().startswith("[")
        is_xml = txt.strip().startswith("<") and "<?xml" in txt[:50]
        print(f"{url2.split('/')[-1]:40s} {r2.status_code} json={is_json} xml={is_xml} len={len(txt)}")
        if is_json or is_xml:
            print("  PREVIEW:", txt[:300])
    except Exception as e:
        print(f"  ERR: {e}")
