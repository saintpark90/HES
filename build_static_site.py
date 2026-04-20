from __future__ import annotations

import json
from pathlib import Path

from crawler import get_next_hanwha_game

ROOT = Path(__file__).parent
TEMPLATE_PATH = ROOT / "index.template.html"
OUTPUT_PATH = ROOT / "index.html"


def build() -> None:
    game_info = get_next_hanwha_game() or {}
    has_game = bool(game_info)

    if has_game:
        og_title = f"한화 다음 경기: {game_info['matchup']}"
        og_description = (
            f"{game_info['game_date']} {game_info['game_time']} | "
            f"한화 선발: {game_info['hanwha_starter']} | 상대팀: {game_info['opponent']}"
        )
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
    )
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    build()
