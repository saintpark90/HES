from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

KBO_GAME_LIST_URL = "https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList"
KBO_TEAM_RECORD_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetTeamRecord"
KBO_LINEUP_ANALYSIS_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetLineUpAnalysis"
KBO_BOX_SCORE_SCROLL_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetBoxScoreScroll"
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
YOUTUBE_PLAYLIST_FEED_URL = "https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
EAGLES_HIGHLIGHT_PLAYLIST_ID = "PLH13Vc2FtHHh-syagRtonzJLl-SkG3B7Q"
EAGLES_OIYU_PLAYLIST_ID = "PLH13Vc2FtHHg4qpO0evfriiB7R7pU_q05"
NAVER_SPORTS_NEWS_API_URL = "https://api-gw.sports.naver.com/news/articles/kbaseball"

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


def _cell_text(cell: Dict[str, Any]) -> str:
    return _clean_html_text(str((cell or {}).get("Text", "") or ""))


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


def _fetch_latest_playlist_video(playlist_id: str) -> Dict[str, str]:
    feed_url = YOUTUBE_PLAYLIST_FEED_URL.format(playlist_id=playlist_id)
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(feed_url, timeout=10, headers=headers)
        response.raise_for_status()
        root = ET.fromstring(response.text)
    except Exception:
        return _fetch_latest_playlist_video_from_page(playlist_id)

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/",
    }
    entry = root.find("atom:entry", ns)
    if entry is None:
        return _fetch_latest_playlist_video_from_page(playlist_id)

    title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
    link_node = entry.find("atom:link", ns)
    video_url = ""
    if link_node is not None:
        video_url = str(link_node.attrib.get("href", "") or "").strip()
    published = (entry.findtext("atom:published", default="", namespaces=ns) or "").strip()
    video_id = (entry.findtext("yt:videoId", default="", namespaces=ns) or "").strip()
    thumbnail = ""
    thumbnail_node = entry.find("media:group/media:thumbnail", ns)
    if thumbnail_node is not None:
        thumbnail = str(thumbnail_node.attrib.get("url", "") or "").strip()
    if not thumbnail and video_id:
        thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    if video_id:
        title = _fetch_youtube_video_title_ko(video_id, title)

    return {
        "title": title,
        "url": video_url,
        "published_at": published,
        "video_id": video_id,
        "thumbnail": thumbnail,
    }


def _fetch_latest_playlist_video_from_page(playlist_id: str) -> Dict[str, str]:
    page_url = f"https://www.youtube.com/playlist?list={playlist_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(page_url, timeout=12, headers=headers)
        response.raise_for_status()
        html = response.text
    except Exception:
        return {}

    init_data_match = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S)
    if not init_data_match:
        video_id_match = re.search(r"watch\?v=([A-Za-z0-9_-]{11})", html)
        if not video_id_match:
            return {}
        video_id = video_id_match.group(1)
        return {
            "title": "",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "published_at": "",
            "video_id": video_id,
            "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        }

    try:
        init_data = json.loads(init_data_match.group(1))
    except Exception:
        return {}

    renderer = _find_first_playlist_video_renderer(init_data)
    if not renderer:
        return {}
    video_id = str(renderer.get("videoId", "") or "").strip()
    if not video_id:
        return {}

    title = ""
    title_data = renderer.get("title", {})
    if isinstance(title_data, dict):
        runs = title_data.get("runs", []) or []
        if runs and isinstance(runs[0], dict):
            title = str(runs[0].get("text", "") or "").strip()
        if not title:
            title = str(title_data.get("simpleText", "") or "").strip()

    published = ""
    published_text = renderer.get("publishedTimeText", {})
    if isinstance(published_text, dict):
        published = str(published_text.get("simpleText", "") or "").strip()
    if not published:
        published_data = renderer.get("videoInfo", {})
        if isinstance(published_data, dict):
            runs = published_data.get("runs", []) or []
            if runs and isinstance(runs[0], dict):
                published = str(runs[0].get("text", "") or "").strip()
    title = _fetch_youtube_video_title_ko(video_id, title)

    return {
        "title": title,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "published_at": published,
        "video_id": video_id,
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    }


def _find_first_playlist_video_renderer(node: Any) -> Dict[str, Any]:
    if isinstance(node, dict):
        if "playlistVideoRenderer" in node and isinstance(node["playlistVideoRenderer"], dict):
            return node["playlistVideoRenderer"]
        for value in node.values():
            found = _find_first_playlist_video_renderer(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_first_playlist_video_renderer(item)
            if found:
                return found
    return {}


def _fetch_youtube_video_title_ko(video_id: str, fallback_title: str = "") -> str:
    if not video_id:
        return fallback_title
    url = f"https://www.youtube.com/watch?v={video_id}&hl=ko&gl=KR"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    try:
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        og_title = soup.find("meta", attrs={"property": "og:title"})
        if og_title and og_title.get("content"):
            title = str(og_title.get("content")).strip()
            if title:
                return title
    except Exception:
        return fallback_title
    return fallback_title


def _fetch_eagles_tv_latest() -> Dict[str, Any]:
    return {
        "highlight": _fetch_latest_playlist_video(EAGLES_HIGHLIGHT_PLAYLIST_ID),
        "oiyu": _fetch_latest_playlist_video(EAGLES_OIYU_PLAYLIST_ID),
    }


def _build_naver_article_url(oid: str, aid: str) -> str:
    if not oid or not aid:
        return ""
    return f"https://m.sports.naver.com/kbaseball/article/{oid}/{aid}"


def _fetch_latest_hanwha_news(limit: int = 5) -> list[Dict[str, str]]:
    params = {
        "team": HANWHA_TEAM_ID,
        "page": 1,
        "pageSize": max(1, min(limit, 20)),
        "sort": "MYTEAM",
        "isPhoto": "Y",
        "date_flag": "Y",
        "categoryId": "kbo",
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://m.sports.naver.com/",
    }
    try:
        response = requests.get(
            NAVER_SPORTS_NEWS_API_URL,
            params=params,
            timeout=10,
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    news_list = ((payload.get("result") or {}).get("newsList") or [])[:limit]
    result: list[Dict[str, str]] = []
    for item in news_list:
        oid = str(item.get("oid", "") or "")
        aid = str(item.get("aid", "") or "")
        article_url = _build_naver_article_url(oid, aid)
        if not article_url:
            continue
        result.append(
            {
                "title": str(item.get("title", "") or "").strip(),
                "url": article_url,
                "thumbnail": str(item.get("thumbnail", "") or item.get("image", "") or "").strip(),
                "source_name": str(item.get("sourceName", "") or "").strip(),
                "published_at": str(item.get("dateTime", "") or "").strip(),
            }
        )
    return result


def _parse_lineup_grid_rows(raw_grid_json: str) -> list[Dict[str, str]]:
    if not raw_grid_json:
        return []
    try:
        grid = json.loads(raw_grid_json)
    except Exception:
        return []

    lineup_rows: list[Dict[str, str]] = []
    seen_orders: set[str] = set()
    for row_obj in grid.get("rows", []):
        cells = row_obj.get("row", []) if isinstance(row_obj, dict) else []
        if len(cells) < 3:
            continue
        order = _cell_text(cells[0])
        position = _cell_text(cells[1])
        player_name = _cell_text(cells[2])
        if not order or not player_name:
            continue
        if not re.match(r"^\d+$", order):
            continue
        if order in seen_orders:
            continue
        seen_orders.add(order)
        lineup_rows.append(
            {
                "order": order,
                "position": position,
                "name": player_name,
            }
        )
        if len(lineup_rows) >= 9:
            break
    lineup_rows.sort(key=lambda item: int(item["order"]))
    return lineup_rows


def _fetch_lineup_analysis(game_id: str, season_id: str, sr_id: str) -> Dict[str, Any]:
    if not game_id:
        return {"lineup_ck": False, "away_lineup": [], "home_lineup": []}
    payload = {
        "leId": "1",
        "srId": sr_id or "0",
        "seasonId": season_id or str(date.today().year),
        "gameId": game_id,
    }
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.koreabaseball.com/"}
    try:
        response = requests.post(
            KBO_LINEUP_ANALYSIS_URL,
            data=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        data = json.loads(response.content.decode("utf-8-sig"))
    except Exception:
        return {"lineup_ck": False, "away_lineup": [], "home_lineup": []}

    lineup_ck = False
    away_lineup_raw = ""
    home_lineup_raw = ""
    if isinstance(data, list):
        if len(data) > 0 and isinstance(data[0], list) and data[0]:
            lineup_ck = bool((data[0][0] or {}).get("LINEUP_CK"))
        if len(data) > 4 and isinstance(data[4], list) and data[4]:
            away_lineup_raw = str(data[4][0] or "")
        if len(data) > 3 and isinstance(data[3], list) and data[3]:
            home_lineup_raw = str(data[3][0] or "")
    return {
        "lineup_ck": lineup_ck,
        "away_lineup": _parse_lineup_grid_rows(away_lineup_raw),
        "home_lineup": _parse_lineup_grid_rows(home_lineup_raw),
    }


def _find_latest_finished_hanwha_game(before_date: date, max_days_lookback: int = 14) -> Optional[Dict[str, Any]]:
    for offset in range(1, max_days_lookback + 1):
        target = before_date - timedelta(days=offset)
        try:
            games = _fetch_games(target)
        except Exception:
            continue

        candidates = [g for g in games if _is_hanwha_game(g) and (_is_finished_game(g) or _is_final_game(g))]
        if not candidates:
            continue

        candidates.sort(
            key=lambda g: (
                str(g.get("G_TM", "") or ""),
                str(g.get("G_ID", "") or ""),
            ),
            reverse=True,
        )
        picked = candidates[0]
        picked["_resolved_date"] = target
        return picked
    return None


def _fetch_hanwha_last_game_batters(game: Dict[str, Any], game_date: date) -> list[Dict[str, str]]:
    payload = {
        "leId": "1",
        "srId": str(game.get("SR_ID") or "0"),
        "seasonId": str(game.get("SEASON_ID") or game_date.year),
        "gameId": str(game.get("G_ID") or ""),
    }
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.koreabaseball.com/"}
    try:
        response = requests.post(
            KBO_BOX_SCORE_SCROLL_URL,
            data=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        data = json.loads(response.content.decode("utf-8-sig"))
    except Exception:
        return []

    if str(data.get("code", "")) != "100":
        return []

    arr_hitter = data.get("arrHitter", []) or []
    if len(arr_hitter) < 2:
        return []

    hanwha_is_away = game.get("AWAY_ID") == HANWHA_TEAM_ID
    target_idx = 0 if hanwha_is_away else 1
    if target_idx >= len(arr_hitter):
        return []

    try:
        table_names = json.loads(str(arr_hitter[target_idx].get("table1", "{}") or "{}"))
        table_stats = json.loads(str(arr_hitter[target_idx].get("table3", "{}") or "{}"))
    except Exception:
        return []

    name_rows = table_names.get("rows", []) or []
    stat_rows = table_stats.get("rows", []) or []
    row_count = min(len(name_rows), len(stat_rows))
    if row_count == 0:
        return []

    lineup_map: Dict[str, Dict[str, str]] = {}
    for idx in range(row_count):
        name_cells = (name_rows[idx] or {}).get("row", [])
        stat_cells = (stat_rows[idx] or {}).get("row", [])
        if len(name_cells) < 3 or len(stat_cells) < 5:
            continue

        order = _cell_text(name_cells[0])
        player_name = _cell_text(name_cells[2])
        if not order or not player_name or not re.match(r"^\d+$", order):
            continue
        if order in lineup_map:
            continue

        position = _cell_text(name_cells[1])
        at_bats = _cell_text(stat_cells[0]) or "-"
        hits = _cell_text(stat_cells[1]) or "-"
        runs = _cell_text(stat_cells[3]) or "-"
        avg = _cell_text(stat_cells[4]) or "-"
        lineup_map[order] = {
            "order": order,
            "position": position,
            "name": player_name,
            "ab": at_bats,
            "hit": hits,
            "run": runs,
            "avg": avg,
        }

    batters = [lineup_map[key] for key in sorted(lineup_map.keys(), key=int)]
    return batters[:9]


def _build_lineup_info(
    game: Dict[str, Any],
    target_date: date,
    season_id: str,
    game_id: str,
    sr_id: str,
) -> Dict[str, Any]:
    is_hanwha_away = game.get("AWAY_ID") == HANWHA_TEAM_ID
    lineup_data = _fetch_lineup_analysis(game_id=game_id, season_id=season_id, sr_id=sr_id)
    today_lineup = lineup_data.get("away_lineup", []) if is_hanwha_away else lineup_data.get("home_lineup", [])

    if lineup_data.get("lineup_ck") and today_lineup:
        return {
            "is_official": True,
            "notice": "",
            "source_game_date": target_date.isoformat(),
            "batters": [
                {
                    "order": item.get("order", "-"),
                    "position": item.get("position", "-"),
                    "name": item.get("name", "-"),
                    "ab": "-",
                    "hit": "-",
                    "run": "-",
                    "avg": "-",
                }
                for item in today_lineup[:9]
            ],
        }

    latest_game = _find_latest_finished_hanwha_game(before_date=target_date)
    if not latest_game:
        return {
            "is_official": False,
            "notice": "아직 라인업이 발표되지 않아 전날 라인업을 보여드립니다.",
            "source_game_date": "",
            "batters": [],
        }

    latest_game_date = latest_game.get("_resolved_date") or (target_date - timedelta(days=1))
    fallback_batters = _fetch_hanwha_last_game_batters(game=latest_game, game_date=latest_game_date)
    return {
        "is_official": False,
        "notice": "아직 라인업이 발표되지 않아 전날 라인업을 보여드립니다.",
        "source_game_date": latest_game_date.isoformat(),
        "batters": fallback_batters,
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


def has_hanwha_game_on_date(target_date: date) -> bool:
    try:
        games = _fetch_games(target_date)
    except Exception:
        return False
    return any(_is_hanwha_game(game) for game in games)


def _format_series_date_range(start_date: date, end_date: date) -> str:
    if start_date == end_date:
        return f"{start_date.month}/{start_date.day}"
    if start_date.month == end_date.month:
        return f"{start_date.month}/{start_date.day}~{end_date.day}"
    return f"{start_date.month}/{start_date.day}~{end_date.month}/{end_date.day}"


def _collect_hanwha_games(start_date: date, end_date: date) -> list[Dict[str, Any]]:
    games: list[Dict[str, Any]] = []
    cursor = start_date
    while cursor <= end_date:
        try:
            day_games = _fetch_games(cursor)
        except Exception:
            cursor += timedelta(days=1)
            continue

        for game in day_games:
            if not _is_hanwha_game(game):
                continue
            is_away = game.get("AWAY_ID") == HANWHA_TEAM_ID
            opponent_name = game.get("HOME_NM") if is_away else game.get("AWAY_NM")
            opponent_team_id = game.get("HOME_ID") if is_away else game.get("AWAY_ID")
            season_id = str(game.get("SEASON_ID") or date.today().year)
            games.append(
                {
                    "date": cursor,
                    "opponent": str(opponent_name or "").strip(),
                    "opponent_team_id": str(opponent_team_id or "").strip(),
                    "stadium": str(game.get("S_NM") or "").strip(),
                    "hanwha_home_away": "원정" if is_away else "홈",
                    "season_id": season_id,
                }
            )
        cursor += timedelta(days=1)

    games.sort(key=lambda item: item["date"])
    return games


def _build_hanwha_series(games: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    if not games:
        return []

    series_list: list[Dict[str, Any]] = []
    current = {
        "opponent": games[0]["opponent"],
        "opponent_team_id": games[0]["opponent_team_id"],
        "start_date": games[0]["date"],
        "end_date": games[0]["date"],
        "game_count": 1,
        "stadium": games[0]["stadium"],
        "hanwha_home_away": games[0]["hanwha_home_away"],
        "season_id": games[0]["season_id"],
    }

    for game in games[1:]:
        day_gap = (game["date"] - current["end_date"]).days
        same_opponent = game["opponent"] == current["opponent"]
        if same_opponent and day_gap in {0, 1}:
            current["end_date"] = game["date"]
            current["game_count"] += 1
            continue

        series_list.append(current)
        current = {
            "opponent": game["opponent"],
            "opponent_team_id": game["opponent_team_id"],
            "start_date": game["date"],
            "end_date": game["date"],
            "game_count": 1,
            "stadium": game["stadium"],
            "hanwha_home_away": game["hanwha_home_away"],
            "season_id": game["season_id"],
        }

    series_list.append(current)
    return series_list


def _serialize_series(series: Dict[str, Any]) -> Dict[str, Any]:
    start_date = series["start_date"]
    end_date = series["end_date"]
    season_id = str(series.get("season_id") or date.today().year)
    opponent_team_id = str(series.get("opponent_team_id") or "")
    return {
        "opponent": series["opponent"],
        "opponent_team_id": opponent_team_id,
        "date_range": _format_series_date_range(start_date, end_date),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "game_count": series["game_count"],
        "stadium": series.get("stadium", ""),
        "hanwha_home_away": series.get("hanwha_home_away", ""),
        "hanwha_emblem": f"{KBO_EMBLEM_BASE}/{season_id}/emblem_{HANWHA_TEAM_ID}.png",
        "opponent_emblem": (
            f"{KBO_EMBLEM_BASE}/{season_id}/emblem_{opponent_team_id}.png"
            if opponent_team_id
            else ""
        ),
    }


def _resolve_hanwha_series(target_date: date, target_opponent: str, max_days_ahead: int) -> Dict[str, Any]:
    # Include a short look-back window so an ongoing series can be detected reliably.
    schedule_start = target_date - timedelta(days=7)
    schedule_end = target_date + timedelta(days=max_days_ahead + 10)
    games = _collect_hanwha_games(schedule_start, schedule_end)
    series_list = _build_hanwha_series(games)
    if not series_list:
        return {"current_series": None, "next_series": None}

    current_idx = -1
    for idx, series in enumerate(series_list):
        in_range = series["start_date"] <= target_date <= series["end_date"]
        if not in_range:
            continue
        if target_opponent and series["opponent"] and series["opponent"] != target_opponent:
            continue
        current_idx = idx
        break

    if current_idx < 0:
        for idx, series in enumerate(series_list):
            if series["start_date"] >= target_date:
                current_idx = idx
                break

    if current_idx < 0:
        return {"current_series": None, "next_series": None}

    current_series = _serialize_series(series_list[current_idx])
    next_series = (
        _serialize_series(series_list[current_idx + 1])
        if current_idx + 1 < len(series_list)
        else None
    )
    return {"current_series": current_series, "next_series": next_series}


def get_next_hanwha_game(max_days_ahead: int = 30) -> Optional[Dict[str, Any]]:
    rank_daily = _fetch_team_rank_daily()
    eagles_tv = _fetch_eagles_tv_latest()
    latest_news = _fetch_latest_hanwha_news(limit=5)
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
            series_info = _resolve_hanwha_series(
                target_date=target,
                target_opponent=opponent_name or "",
                max_days_ahead=max_days_ahead,
            )
            lineup_info = _build_lineup_info(
                game=game,
                target_date=target,
                season_id=season_id,
                game_id=game_id,
                sr_id=sr_id,
            )

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
                "current_series": series_info.get("current_series"),
                "next_series": series_info.get("next_series"),
                "lineup_info": lineup_info,
                "eagles_tv": eagles_tv,
                "latest_news": latest_news,
            }
    return None
