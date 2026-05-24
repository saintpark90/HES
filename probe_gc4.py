import requests
import re
import sys

# The GameCenter page loads sub-pages via AJAX. Let's check S2i.AjaxHtml and S2i.GameList
CDN = "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/KBOHome/resources/min/js"
ver = "version=20260330"

for fname in ["S2i.AjaxHtml-1.0.0.min.js", "S2i.GameList-1.0.0.min.js"]:
    url = f"{CDN}/{fname}?{ver}"
    r = requests.get(url, timeout=10)
    print(f"\n=== {fname} (status={r.status_code}, len={len(r.text)}) ===")
    # Show first 1000 chars
    sys.stdout.buffer.write(r.text[:1000].encode("ascii", errors="replace"))
    print()

# Try fetching the gamecenter subpage for "팀전력비교"
GID = "20260422HHLG0"
sub_urls = [
    f"https://www.koreabaseball.com/Schedule/GameCenter/TeamCompare.aspx?gameId={GID}",
    f"https://www.koreabaseball.com/Schedule/GameCenter/TeamPower.aspx?gameId={GID}",
    f"https://www.koreabaseball.com/Schedule/GameCenter/PowerCompare.aspx?gameId={GID}",
    f"https://www.koreabaseball.com/Schedule/GameCenter/TeamBatting.aspx?gameId={GID}",
]
print("\n=== Probing GameCenter subpages ===")
for u in sub_urls:
    r2 = requests.get(u, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
    txt = r2.content.decode("euc-kr", errors="replace")
    has_table = "<table" in txt
    has_asmx = "asmx" in txt
    print(f"{u.split('/')[-1][:40]:42s} {r2.status_code} table={has_table} asmx={has_asmx} len={len(txt)}")
    if has_asmx:
        calls = re.findall(r"[A-Za-z]+\.asmx/[A-Za-z_]+", txt)
        for c in sorted(set(calls)):
            sys.stdout.buffer.write(("  " + c + "\n").encode("ascii", errors="replace"))
