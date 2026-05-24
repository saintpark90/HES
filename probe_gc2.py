import requests
import re
import json

# Fetch the GameCenter JS file to find actual endpoint names
GID = "20260422HHLG0"

url = f"https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx?leId=1&srId=0&gameId={GID}"
r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
html = r.content.decode("euc-kr", errors="replace")

# Find all JS file references
js_files = re.findall(r'src=["\']([^"\']*\.js[^"\']*)["\']', html)
print("JS files:", js_files[:10])

# Find script blocks with ws/ calls
ws_in_html = re.findall(r"['\"]([^'\"]*(?:ws|asmx)[^'\"]{2,80})['\"]", html)
print("\nWS refs in HTML:")
for w in sorted(set(ws_in_html))[:30]:
    print(" ", w)

# Try fetching one of the JS files that might have GameCenter logic
gc_js_candidates = [
    "https://www.koreabaseball.com/scripts/gamecenter.js",
    "https://www.koreabaseball.com/scripts/gameCenter.js",
    "https://www.koreabaseball.com/scripts/GameCenter.js",
    "https://www.koreabaseball.com/Schedule/GameCenter/Main.js",
]
for js_url in gc_js_candidates:
    r2 = requests.get(js_url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
    if r2.status_code == 200 and len(r2.text) > 200:
        print(f"\n=== Found: {js_url} ===")
        # find asmx calls
        calls = re.findall(r"[A-Za-z]+\.asmx[^'\"\s]{0,80}", r2.text)
        for c in sorted(set(calls)):
            print(" ", c)
