import requests
import re
import sys

# Fetch KBO CDN JS files and look for GameCenter-related WS endpoints
CDN = "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/KBOHome/resources/min/js"
ver = "version=20260330"

candidates = [
    f"{CDN}/S2i.Common-1.0.1.min.js?{ver}",
    f"{CDN}/common.min.js?{ver}",
]

# Also check if there's a gamecenter-specific JS
gc_candidates = [
    f"{CDN}/gameCenter.min.js?{ver}",
    f"{CDN}/gamecenter.min.js?{ver}",
    f"{CDN}/GameCenter.min.js?{ver}",
    "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/KBOHome/resources/min/js/S2i.MakeTable-1.0.3.min.js?version=20260330",
]

GID = "20260422HHLG0"
url = f"https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx?leId=1&srId=0&gameId={GID}"
r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
html = r.content.decode("euc-kr", errors="replace")

# Get all unique JS srcs
all_js = re.findall(r'src=["\']([^"\']+\.js[^"\']*)["\']', html)
print("All JS files:")
for j in all_js:
    print(" ", j)

# Fetch each JS and look for asmx/ws patterns
print("\n--- Scanning JS for ws/asmx references ---")
for js_url in all_js:
    if js_url.startswith("//"):
        js_url = "https:" + js_url
    try:
        r2 = requests.get(js_url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if r2.status_code != 200:
            continue
        text = r2.text
        calls = re.findall(r"[A-Za-z]+\.asmx/[A-Za-z_]+", text)
        if calls:
            print(f"\n[{js_url.split('/')[-1].split('?')[0]}]")
            for c in sorted(set(calls)):
                sys.stdout.buffer.write((c + "\n").encode("ascii", errors="replace"))
    except Exception as e:
        pass

# Also try direct HTML embedded ajax calls
print("\n--- Direct WS calls in Main.aspx HTML ---")
asmx_in_html = re.findall(r"[A-Za-z]+\.asmx/[A-Za-z_]+", html)
for c in sorted(set(asmx_in_html)):
    sys.stdout.buffer.write((c + "\n").encode("ascii", errors="replace"))
