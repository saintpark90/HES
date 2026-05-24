import requests
import re
import sys

# S2i.AjaxHtml loads sub-pages. The GameCenter main page iframes/ajaxes subpages.
# Let's look at what URLs are referenced in the main page HTML more carefully.
GID = "20260422HHLG0"
url = f"https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx?leId=1&srId=0&gameId={GID}"
r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
html = r.content.decode("euc-kr", errors="replace")

# Look for AjaxHtml url params, iframe srcs, and any aspx page refs
aspx_refs = re.findall(r"[A-Za-z/]+\.aspx[^'\"<>\s]{0,80}", html)
print("=== ASPX refs in main page ===")
for a in sorted(set(aspx_refs))[:30]:
    sys.stdout.buffer.write((a + "\n").encode("ascii", errors="replace"))

# Look for any URL-like strings with GameCenter
gc_refs = re.findall(r"GameCenter[^'\"<>\s]{0,80}", html)
print("\n=== GameCenter refs ===")
for g in sorted(set(gc_refs))[:20]:
    sys.stdout.buffer.write((g + "\n").encode("ascii", errors="replace"))

# Look for tab/menu items that might indicate subpages
tab_refs = re.findall(r"(?:href|url|URL)[^'\"<>]{0,5}['\"]([^'\"]{0,100})['\"]", html)
print("\n=== href/url refs ===")
for t in sorted(set(tab_refs))[:30]:
    sys.stdout.buffer.write((t + "\n").encode("ascii", errors="replace"))

# Save full HTML for manual inspection
with open("gc_main.html", "w", encoding="utf-8", errors="replace") as f:
    f.write(html)
print("\nSaved gc_main.html for inspection")
print("Total length:", len(html))
