from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image, ImageOps

from crawler import get_next_hanwha_game

ROOT = Path(__file__).parent
TEMPLATE_PATH = ROOT / "index.template.html"
OUTPUT_PATH = ROOT / "index.html"
THUMBNAIL_PATH = ROOT / "thumbnail.jpg"
KBO_IMAGE_BASE = "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle"


def _face_image_url(season_id: str, player_id: str) -> str:
    season = season_id or "2026"
    return f"{KBO_IMAGE_BASE}/{season}/{player_id}.jpg"


def _download_face(url: str) -> Image.Image:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return Image.open(io.BytesIO(response.content)).convert("RGB")


def _build_thumbnail(game_info: dict) -> None:
    canvas = Image.new("RGB", (1200, 630), (20, 20, 20))
    away_box = (80, 70, 560, 560)
    home_box = (640, 70, 1120, 560)

    def paste_face(player_id: str, box: tuple[int, int, int, int]) -> None:
        if not player_id:
            return
        try:
            face = _download_face(_face_image_url(game_info.get("season_id", ""), player_id))
            fitted = ImageOps.fit(face, (box[2] - box[0], box[3] - box[1]), method=Image.Resampling.LANCZOS)
            canvas.paste(fitted, (box[0], box[1]))
        except Exception:
            pass

    paste_face(game_info.get("away_starter_id", ""), away_box)
    paste_face(game_info.get("home_starter_id", ""), home_box)
    canvas.save(THUMBNAIL_PATH, format="JPEG", quality=92)


def build() -> None:
    game_info = get_next_hanwha_game() or {}
    has_game = bool(game_info)

    if has_game:
        og_title = f"{game_info['game_date']} {game_info['matchup']}"
        og_description = f"{game_info['away_team']} : {game_info['away_starter']} / {game_info['home_team']} : {game_info['home_starter']}"
        _build_thumbnail(game_info)
    else:
        og_title = "한화 이글스 다음 경기 정보"
        og_description = "현재 한화 이글스 다음 경기 정보를 찾지 못했습니다."

    html_template = TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = (
        html_template.replace("__OG_TITLE__", og_title)
        .replace("__OG_DESCRIPTION__", og_description)
        .replace(
            "__GAME_JSON__",
            json.dumps(game_info if has_game else None, ensure_ascii=False),
        )
        .replace("__UPDATED_AT_VALUE__", datetime.now().replace(microsecond=0).isoformat())
    )
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    build()
