import requests
import re
import sys

GID = "20260422HHLG0"
BASE = "https://www.koreabaseball.com/Schedule"

# Fetch all preview subpages
pages = {
    "Team": f"{BASE}/GameCenter/Preview/Team.aspx?gameId={GID}",
    "StartPitcher": f"{BASE}/GameCenter/Preview/StartPitcher.aspx?gameId={GID}",
    "LineUp": f"{BASE}/GameCenter/Preview/LineUp.aspx?gameId={GID}",
}

for name, url in pages.items():
    r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    html = r.content.decode("euc-kr", errors="replace")
    print(f"\n=== {name}: status={r.status_code}, len={len(html)} ===")
    
    # Find asmx refs
    asmx = re.findall(r"[A-Za-z]+\.asmx/[A-Za-z_]+", html)
    if asmx:
        print("ASMX:", sorted(set(asmx)))
    
    # Find tables
    tables = re.findall(r"<table[^>]*>(.*?)</table>", html.replace("\n", " "), re.S)
    print(f"Tables: {len(tables)}")
    
    # Find JS inline data
    json_like = re.findall(r"var\s+\w+\s*=\s*(\[.*?\]|\{.*?\})", html.replace("\n", " "), re.S)
    if json_like:
        print("JSON vars found:", len(json_like))
        for j in json_like[:3]:
            sys.stdout.buffer.write((j[:200] + "\n").encode("ascii", errors="replace"))
    
    # Save each page
    with open(f"gc_{name}.html", "w", encoding="utf-8", errors="replace") as f:
        f.write(html)
    print(f"Saved gc_{name}.html")
