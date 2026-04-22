from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup

KBO_GAME_LIST_URL = "https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList"
KBO_TEAM_RECORD_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetTeamRecord"
KBO_PLAYER_SEARCH_URL = "https://www.koreabaseball.com/ws/Controls.asmx/GetSearchPlayer"
HANWHA_TEAM_ID = "HH"
SERIES_IDS = "0,1,3,4,5,6,7,9"
KBO_IMAGE_BASE = "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle"
KBO_EMBLEM_BASE = "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/emblem/regular"
PITCHER_DETAIL_URL = "https://www.koreabaseball.com/Record/Player/PitcherDetail/Basic.aspx"
KBO_TEAM_RANK_DAILY_URL = "https://www.koreabaseball.com/Record/TeamRank/TeamRankDaily.aspx"
KBO_LIVETEXT_VIEW2_URL = "https://www.koreabaseball.com/Game/LiveTextView2.aspx"
NAVER_SPORTS_API_BASE = "https://api-gw.sports.naver.com"
NAVER_KBO_TEAM_RANK_URL = NAVER_SPORTS_API_BASE + "/statistics/categories/kbo/seasons/{season}/teams"
NAVER_KBO_LAST10_URL = (
    NAVER_SPORTS_API_BASE + "/statistics/categories/kbo/seasons/{season}/teams/last-ten-games"
)

TEAM_NAME_TO_ID = {
    "KT": "KT",
    "LG": "LG",
    "삼성": "SS",
    "SSG": "SK",
    "KIA": "HT",
    "한화": "HH",
    "NC": "NC",
    "두산": "OB",
    "롯데": "LT",
    "키움": "WO",
}


def _fetch_games(target_date: date) -> list[Dict[str, Any]]:
    payload = {
        "leId": "1",
        "srId": SERIES_IDS,
        "date": target_date.strftime("%Y%m%d"),
    }
    response = requests.post(KBO_GAME_LIST_URL, data=payload, timeout=10)
    response.raise_for_status()
    body = json.loads(response.content.decode("utf-8-sig"))
    return body.get("game", [])


def _fetch_game_by_game_id(game_id: str) -> Dict[str, Any]:
    if len(game_id) < 8:
        return {}
    try:
        game_date = datetime.strptime(game_id[:8], "%Y%m%d").date()
    except ValueError:
        return {}

    try:
        games = _fetch_games(game_date)
    except Exception:
        return {}

    for g in games:
        if str(g.get("G_ID", "")) == game_id:
            return g
    return {}


def _is_hanwha_game(game: Dict[str, Any]) -> bool:
    return game.get("AWAY_ID") == HANWHA_TEAM_ID or game.get("HOME_ID") == HANWHA_TEAM_ID


def _extract_hanwha_starter(game: Dict[str, Any]) -> str:
    if game.get("AWAY_ID") == HANWHA_TEAM_ID:
        return (game.get("T_PIT_P_NM") or "").strip()
    return (game.get("B_PIT_P_NM") or "").strip()


def _face_image_url(season_id: str, player_id: str) -> str:
    season = season_id or str(date.today().year)
    return f"{KBO_IMAGE_BASE}/{season}/{player_id}.jpg"


def _is_finished_game(game: Dict[str, Any]) -> bool:
    # SCORE_CK == "1" means final score is available.
    return str(game.get("SCORE_CK", "")) == "1"


def _is_live_game(game: Dict[str, Any]) -> bool:
    # GAME_STATE_SC:
    # 1: 예정, 2: 경기중, 3/4: 종료(데이터 반영 상태에 따라 다름)
    return str(game.get("GAME_STATE_SC", "")) == "2"


def _is_final_game(game: Dict[str, Any]) -> bool:
    return str(game.get("GAME_STATE_SC", "")) in {"3", "4"}


def _build_live_status(game: Dict[str, Any], away_team: str, home_team: str) -> Dict[str, Any]:
    is_live = _is_live_game(game)
    is_final = _is_final_game(game)
    top_bottom = str(game.get("GAME_TB_SC", "") or "")
    inning_no = str(game.get("GAME_INN_NO", "") or "").strip()
    inning_half = "초" if top_bottom == "T" else "말" if top_bottom == "B" else ""
    inning_text = f"{inning_no}회 {inning_half}".strip() if inning_no else ""

    away_score = str(game.get("T_SCORE_CN", "0") or "0")
    home_score = str(game.get("B_SCORE_CN", "0") or "0")

    away_batter = str(game.get("T_P_NM", "") or "").strip()
    home_batter = str(game.get("B_P_NM", "") or "").strip()
    if top_bottom == "T":
        current_batter = away_batter
        current_batter_team = away_team
        current_pitcher = home_batter
        current_pitcher_team = home_team
    elif top_bottom == "B":
        current_batter = home_batter
        current_batter_team = home_team
        current_pitcher = away_batter
        current_pitcher_team = away_team
    else:
        current_batter = away_batter or home_batter
        current_batter_team = away_team if away_batter else home_team
        current_pitcher = home_batter or away_batter
        current_pitcher_team = home_team if home_batter else away_team

    return {
        "is_live": is_live,
        "is_final": is_final,
        "away_score": away_score,
        "home_score": home_score,
        "inning_text": inning_text,
        "current_pitcher": current_pitcher,
        "current_pitcher_team": current_pitcher_team,
        "current_batter": current_batter,
        "current_batter_team": current_batter_team,
    }


def _clean_html_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    return text.replace("&nbsp;", " ").strip()


def _parse_stat_tables(html: str) -> list[dict[str, str]]:
    """Parse every <table> in html and return list of header→first-row-value dicts."""
    flat = html.replace("\n", " ")
    result = []
    for table_html in re.findall(r"<table[^>]*>.*?</table>", flat, re.S):
        headers = [_clean_html_text(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", table_html, re.S)]
        if not headers:
            continue
        for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.S):
            cells = [_clean_html_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)]
            if cells:
                result.append({headers[i]: cells[i] for i in range(min(len(headers), len(cells)))})
                break  # only first data row per table
    return result


def _parse_team_record_row(row: list) -> Dict[str, str]:
    """row is the list of cell dicts from GetTeamRecord JSON."""
    def text(idx: int) -> str:
        if idx >= len(row):
            return "-"
        return re.sub(r"<[^>]+>", "", row[idx].get("Text", "") or "").strip() or "-"

    def is_win(idx: int) -> bool:
        if idx >= len(row):
            return False
        return (row[idx].get("Class") or "") == "win"

    return {
        "season_record": text(1),
        "last5": text(2),
        "era": text(3),
        "era_win": is_win(3),
        "avg": text(4),
        "avg_win": is_win(4),
        "runs_scored": text(5),
        "runs_scored_win": is_win(5),
        "runs_allowed": text(6),
        "runs_allowed_win": is_win(6),
    }


def _fetch_team_comparison(game_id: str, season_id: str, away_id: str, home_id: str) -> Dict[str, Any]:
    """Fetch team season stats from KBO GetTeamRecord endpoint."""
    if not game_id:
        return {}

    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.koreabaseball.com/"}
    payload = {
        "leId": "1",
        "srId": "0",
        "seasonId": season_id or str(date.today().year),
        "gameId": game_id,
        "groupSc": "SEASON",
    }

    try:
        resp = requests.post(KBO_TEAM_RECORD_URL, data=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = json.loads(resp.content.decode("utf-8-sig"))
    except Exception:
        return {}

    rows = data.get("rows", [])
    if len(rows) < 2:
        return {}

    away_row = rows[0].get("row", [])
    home_row = rows[1].get("row", [])

    emblem_year = season_id or str(date.today().year)
    return {
        "away": _parse_team_record_row(away_row),
        "home": _parse_team_record_row(home_row),
        "away_emblem": f"{KBO_EMBLEM_BASE}/{emblem_year}/emblem_{away_id}.png",
        "home_emblem": f"{KBO_EMBLEM_BASE}/{emblem_year}/emblem_{home_id}.png",
    }


def _fetch_pitcher_stats(player_id: str) -> Dict[str, str]:
    if not player_id:
        return {}

    try:
        response = requests.get(PITCHER_DETAIL_URL, params={"playerId": player_id}, timeout=10)
        response.raise_for_status()
        html = response.text
    except Exception:
        return {}

    tables = _parse_stat_tables(html)

    basic: Dict[str, str] = {}
    advanced: Dict[str, str] = {}
    for t in tables:
        if "ERA" in t and not basic:
            basic = t
        if "WHIP" in t and not advanced:
            advanced = t

    image_url = ""
    try:
        soup = BeautifulSoup(html, "html.parser")
        # KBO player detail uses id like:
        # cphContents_cphContents_cphContents_playerProfile_imgProgile
        profile_img = soup.find(id=re.compile(r"imgProgile$", re.I))
        if profile_img:
            image_url = (profile_img.get("src") or "").strip()
        if not image_url:
            fallback_img = soup.select_one("img[src*='/KBO_IMAGE/person/middle/']")
            if fallback_img:
                image_url = (fallback_img.get("src") or "").strip()
    except Exception:
        image_url = ""

    if image_url.startswith("//"):
        image_url = "https:" + image_url
    elif image_url.startswith("/"):
        image_url = "https://www.koreabaseball.com" + image_url

    return {
        "era": basic.get("ERA", "-"),
        "wins": basic.get("W", "-"),
        "losses": basic.get("L", "-"),
        "war": "-",  # KBO 투수 상세 페이지에서 WAR를 제공하지 않음
        "games": basic.get("G", "-"),
        "avg_innings": basic.get("IP", "-"),
        "qs": advanced.get("QS", "-"),
        "whip": advanced.get("WHIP", "-"),
        "image_url": image_url,
    }


def _fetch_live_starter_names(game_id: str, season_id: str, sr_id: str) -> Dict[str, str]:
    """
    Parse LiveTextView2 boxscore and read first pitcher row for each team.
    This is used when live games don't expose starter in GetKboGameList payload.
    """
    payload = {
        "leagueId": "1",
        "seriesId": sr_id or "0",
        "gameId": game_id,
        "gyear": season_id or str(date.today().year),
    }
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.koreabaseball.com/"}

    try:
        response = requests.post(KBO_LIVETEXT_VIEW2_URL, data=payload, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception:
        return {}

    soup = BeautifulSoup(response.text, "html.parser")
    pitchers: list[str] = []
    for table in soup.find_all("table"):
        caption = table.find("caption")
        caption_text = caption.get_text(" ", strip=True) if caption else ""
        if "투수" not in caption_text:
            continue
        for row in table.find_all("tr")[1:]:
            tds = row.find_all("td")
            if not tds:
                continue
            name = tds[0].get_text(" ", strip=True)
            if name and name != "-":
                pitchers.append(name)
                break
        if len(pitchers) >= 2:
            break

    if len(pitchers) >= 2:
        return {"away_starter": pitchers[0], "home_starter": pitchers[1]}
    return {}


def _resolve_pitcher_id_from_search(player_name: str, team_id: str) -> str:
    """
    Resolve playerId from KBO player search endpoint.
    Prefer active roster and team match.
    """
    player_name = (player_name or "").strip()
    if not player_name or player_name == "미정":
        return ""

    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.koreabaseball.com/"}
    try:
        response = requests.post(
            KBO_PLAYER_SEARCH_URL,
            data={"name": player_name},
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        payload = json.loads(response.content.decode("utf-8-sig"))
    except Exception:
        return ""

    candidates = payload.get("now", []) or []
    if not candidates:
        candidates = payload.get("retire", []) or []

    if not candidates:
        return ""

    filtered = [p for p in candidates if str(p.get("T_ID", "")) == str(team_id)]
    target = filtered[0] if filtered else candidates[0]
    player_id = str(target.get("P_ID", "")).strip()
    if player_id:
        return player_id

    link = str(target.get("P_LINK", "") or "")
    m = re.search(r"playerId=(\d+)", link)
    return m.group(1) if m else ""


def _fetch_team_rank_daily() -> Dict[str, Any]:
    """Fetch team rankings from Naver Sports API and head-to-head from KBO page."""
    season = str(date.today().year)
    naver_headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://m.sports.naver.com/",
    }

    rankings: list[dict[str, str]] = []
    rank_date = datetime.now().strftime("%Y.%m.%d")
    try:
        ranking_resp = requests.get(
            NAVER_KBO_TEAM_RANK_URL.format(season=season),
            timeout=10,
            headers=naver_headers,
        )
        ranking_resp.raise_for_status()
        ranking_payload = ranking_resp.json()
        season_team_stats = (
            (ranking_payload.get("result") or {}).get("seasonTeamStats") or []
        )

        last10_resp = requests.get(
            NAVER_KBO_LAST10_URL.format(season=season),
            timeout=10,
            headers=naver_headers,
        )
        last10_resp.raise_for_status()
        last10_payload = last10_resp.json()
        last10_stats = (
            (last10_payload.get("result") or {}).get("seasonTeamLastTenGameStats") or []
        )
        def _safe_text(value: Any) -> str:
            return "-" if value is None or value == "" else str(value)

        last10_by_team: Dict[str, str] = {}
        for item in last10_stats:
            team_id = str(item.get("teamId", "") or "")
            win = item.get("lastTenGameWinGameCount")
            draw = item.get("lastTenGameDrawnGameCount")
            lose = item.get("lastTenGameLoseGameCount")
            if win is not None and draw is not None and lose is not None:
                last10_by_team[team_id] = f"{win}승 {draw}무 {lose}패"
            else:
                last10_by_team[team_id] = _safe_text(item.get("lastTenGameResult"))

        for item in season_team_stats:
            team_id = str(item.get("teamId", "") or "")
            win_rate = item.get("wra")
            emblem_team_id = team_id or TEAM_NAME_TO_ID.get(_safe_text(item.get("teamName")), "")
            emblem_url = (
                f"{KBO_EMBLEM_BASE}/{season}/emblem_{emblem_team_id}.png" if emblem_team_id else ""
            )
            rankings.append(
                {
                    "rank": _safe_text(item.get("ranking")),
                    "team_name": _safe_text(item.get("teamName")),
                    "team_id": team_id,
                    "games": _safe_text(item.get("gameCount")),
                    "wins": _safe_text(item.get("winGameCount")),
                    "losses": _safe_text(item.get("loseGameCount")),
                    "draws": _safe_text(item.get("drawnGameCount")),
                    "win_rate": f"{float(win_rate):.3f}" if win_rate is not None else "-",
                    "games_behind": _safe_text(item.get("gameBehind")),
                    "last10": last10_by_team.get(team_id, "-"),
                    "streak": _safe_text(item.get("continuousGameResult")),
                    "emblem": emblem_url,
                }
            )
    except Exception:
        rankings = []

    # Keep using KBO matrix for head-to-head summary in team comparison card.
    try:
        response = requests.get(
            KBO_TEAM_RANK_DAILY_URL,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception:
        return {"rankings": [], "head_to_head": [], "rank_date": ""}

    tables = soup.find_all("table")
    if len(tables) < 2:
        return {"rankings": rankings, "head_to_head": [], "rank_date": rank_date}

    head_to_head: list[dict[str, str]] = []
    h2h_table = tables[1]
    headers = [th.get_text(" ", strip=True) for th in h2h_table.find_all("th")]
    for tr in h2h_table.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        row = [td.get_text(" ", strip=True) for td in tds]
        if len(row) < 2:
            continue
        team_name = row[0]
        record_map: Dict[str, str] = {}
        for idx, value in enumerate(row[1:], start=1):
            if idx >= len(headers):
                break
            col_team = re.sub(r"\s*\(.*\)$", "", headers[idx]).strip()
            if col_team and col_team != "합계":
                record_map[col_team] = value
        head_to_head.append({"team_name": team_name, "records": record_map})

    return {"rankings": rankings, "head_to_head": head_to_head, "rank_date": rank_date}


def _find_head_to_head_record(
    head_to_head_rows: list[dict[str, Any]], away_team: str, home_team: str
) -> Dict[str, str]:
    away_vs_home = "-"
    home_vs_away = "-"
    for row in head_to_head_rows:
        team = row.get("team_name", "")
        records = row.get("records", {})
        if team == away_team:
            away_vs_home = records.get(home_team, "-")
        if team == home_team:
            home_vs_away = records.get(away_team, "-")
    return {"away_vs_home": away_vs_home, "home_vs_away": home_vs_away}


def get_next_hanwha_game(max_days_ahead: int = 30) -> Optional[Dict[str, Any]]:
    rank_daily = _fetch_team_rank_daily()
    today = date.today()
    for offset in range(max_days_ahead + 1):
        target = today + timedelta(days=offset)
        games = _fetch_games(target)
        for game in games:
            if not _is_hanwha_game(game):
                continue
            # Live games can also have SCORE_CK=1, so don't skip those.
            if offset == 0 and _is_finished_game(game) and not _is_live_game(game):
                continue

            is_away = game.get("AWAY_ID") == HANWHA_TEAM_ID
            opponent_name = game.get("HOME_NM") if is_away else game.get("AWAY_NM")
            away_starter = (game.get("T_PIT_P_NM") or "").strip() or "미정"
            home_starter = (game.get("B_PIT_P_NM") or "").strip() or "미정"
            away_starter_id = str(game.get("T_PIT_P_ID") or "")
            home_starter_id = str(game.get("B_PIT_P_ID") or "")
            season_id = str(game.get("SEASON_ID", ""))
            game_id = str(game.get("G_ID", ""))
            sr_id = str(game.get("SR_ID", "0"))

            # Live-game fallback: read starter names from LiveText when game list values are missing.
            is_live_game = _is_live_game(game)
            if is_live_game and ("미정" in {away_starter, home_starter}):
                live_starters = _fetch_live_starter_names(game_id=game_id, season_id=season_id, sr_id=sr_id)
                away_starter = live_starters.get("away_starter", away_starter)
                home_starter = live_starters.get("home_starter", home_starter)

            # Live-game fallback: if starter IDs are missing, try reloading by gameId/date.
            if (not away_starter_id or not home_starter_id) and game_id:
                latest_game = _fetch_game_by_game_id(game_id)
                if latest_game:
                    away_starter_id = str(latest_game.get("T_PIT_P_ID") or away_starter_id)
                    home_starter_id = str(latest_game.get("B_PIT_P_ID") or home_starter_id)
                    away_starter = (latest_game.get("T_PIT_P_NM") or "").strip() or away_starter
                    home_starter = (latest_game.get("B_PIT_P_NM") or "").strip() or home_starter

            # Final fallback: resolve starter IDs by name via player search endpoint.
            if not away_starter_id:
                away_starter_id = _resolve_pitcher_id_from_search(away_starter, str(game.get("AWAY_ID", "")))
            if not home_starter_id:
                home_starter_id = _resolve_pitcher_id_from_search(home_starter, str(game.get("HOME_ID", "")))

            hanwha_starter = away_starter if is_away else home_starter
            if not hanwha_starter:
                hanwha_starter = _extract_hanwha_starter(game) or "미정"

            away_starter_stats = _fetch_pitcher_stats(away_starter_id)
            home_starter_stats = _fetch_pitcher_stats(home_starter_id)
            away_team_id = str(game.get("AWAY_ID", ""))
            home_team_id = str(game.get("HOME_ID", ""))
            team_comparison = _fetch_team_comparison(game_id, season_id, away_team_id, home_team_id)
            head_to_head_summary = _find_head_to_head_record(
                rank_daily.get("head_to_head", []),
                game.get("AWAY_NM", ""),
                game.get("HOME_NM", ""),
            )
            live_status = _build_live_status(game, game.get("AWAY_NM", ""), game.get("HOME_NM", ""))

            return {
                "season_id": season_id,
                "game_id": game_id,
                "game_date": game.get("G_DT_TXT", ""),
                "game_date_ymd": target.strftime("%Y-%m-%d"),
                "game_time": game.get("G_TM", ""),
                "stadium": game.get("S_NM", ""),
                "home_team": game.get("HOME_NM", ""),
                "away_team": game.get("AWAY_NM", ""),
                "matchup": f"{game.get('AWAY_NM', '')} vs {game.get('HOME_NM', '')}",
                "hanwha_home_away": "원정" if is_away else "홈",
                "opponent": opponent_name or "",
                "hanwha_starter": hanwha_starter,
                "away_starter": away_starter,
                "home_starter": home_starter,
                "away_starter_id": away_starter_id,
                "home_starter_id": home_starter_id,
                "away_starter_image": (
                    away_starter_stats.get("image_url")
                    or (_face_image_url(season_id, away_starter_id) if away_starter_id else "")
                ),
                "home_starter_image": (
                    home_starter_stats.get("image_url")
                    or (_face_image_url(season_id, home_starter_id) if home_starter_id else "")
                ),
                "away_starter_stats": away_starter_stats,
                "home_starter_stats": home_starter_stats,
                "team_comparison": team_comparison,
                "head_to_head_summary": head_to_head_summary,
                "team_rankings": rank_daily.get("rankings", []),
                "team_rank_date": rank_daily.get("rank_date", ""),
                "live_status": live_status,
            }
    return None
