from flask import Flask, render_template, request, url_for

from crawler import get_next_hanwha_game

app = Flask(__name__)


def _build_og_context(game_info: dict | None) -> dict:
    share_url = request.url_root.rstrip("/") + url_for("share_hanwha_next")

    if game_info:
        title = f"한화 다음 경기: {game_info['matchup']}"
        description = (
            f"{game_info['game_date']} {game_info['game_time']} | "
            f"한화 선발: {game_info['hanwha_starter']} | 상대팀: {game_info['opponent']}"
        )
        thumb_text = f"한화 다음 경기 | {game_info['matchup']} | 선발 {game_info['hanwha_starter']}"
        image_url = request.url_root.rstrip("/") + url_for("thumbnail_image", text=thumb_text)
    else:
        title = "한화 다음 경기 정보"
        description = "현재 한화 이글스의 다음 경기 정보를 찾을 수 없습니다."
        image_url = request.url_root.rstrip("/") + url_for("thumbnail_image", text=title)

    return {
        "title": title,
        "description": description,
        "url": share_url,
        "image": image_url,
    }


@app.get("/")
def index():
    game_info = get_next_hanwha_game()
    og = _build_og_context(game_info)
    return render_template("index.html", game_info=game_info, og=og)


@app.get("/share/hanwha-next")
def share_hanwha_next():
    game_info = get_next_hanwha_game()
    og = _build_og_context(game_info)
    return render_template("index.html", game_info=game_info, og=og)


@app.get("/thumbnail.svg")
def thumbnail_image():
    text = request.args.get("text", "한화 이글스 다음 경기 정보")
    safe_text = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#151515"/>
    <stop offset="100%" stop-color="#2a2a2a"/>
  </linearGradient>
</defs>
<rect width="1200" height="630" fill="url(#bg)"/>
<rect x="40" y="40" width="1120" height="550" rx="28" fill="#1f1f1f" stroke="#ff6600" stroke-width="4"/>
<text x="80" y="170" fill="#ff6600" font-size="52" font-family="Arial, sans-serif" font-weight="700">HANWHA EAGLES</text>
<text x="80" y="280" fill="#f4f4f4" font-size="44" font-family="Arial, sans-serif">{safe_text}</text>
<text x="80" y="550" fill="#9b9b9b" font-size="30" font-family="Arial, sans-serif">koreabaseball.com data</text>
</svg>"""
    return app.response_class(svg, mimetype="image/svg+xml")


if __name__ == "__main__":
    app.run(debug=True)
