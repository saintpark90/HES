from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from crawler import get_next_hanwha_game

ROOT = Path(__file__).parent
TEMPLATE_PATH = ROOT / "index.template.html"
OUTPUT_PATH = ROOT / "index.html"
DATA_OUTPUT_PATH = ROOT / "game-data.json"
KST = ZoneInfo("Asia/Seoul")


def build() -> None:
    game_info = get_next_hanwha_game() or {}
    has_game = bool(game_info)
    updated_at = datetime.now(KST).replace(microsecond=0).isoformat()

    if has_game:
        og_title = f"{game_info['game_date']} {game_info['matchup']}"
        og_description = f"{game_info['away_team']} : {game_info['away_starter']} / {game_info['home_team']} : {game_info['home_starter']}"
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
        .replace(
            "__UPDATED_AT_VALUE__",
            updated_at,
        )
    )
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    DATA_OUTPUT_PATH.write_text(
        json.dumps(
            {"ok": True, "game_info": game_info if has_game else None, "updated_at": updated_at},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    build()
