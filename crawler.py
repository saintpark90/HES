from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional
import xml.etree.ElementTree as ET
import time
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

KBO_GAME_LIST_URL = "https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList"
KBO_TEAM_RECORD_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetTeamRecord"
KBO_LINEUP_ANALYSIS_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetLineUpAnalysis"
KBO_BOX_SCORE_SCROLL_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetBoxScoreScroll"
KBO_PITCHER_RECORD_ANALYSIS_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetPitcherRecordAnalysis"
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
YOUTUBE_PLAYLIST_URL = "https://www.youtube.com/playlist?list={playlist_id}"
OPENMETEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPENMETEO_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
KST = ZoneInfo("Asia/Seoul")

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

STADIUM_REGION_COORDS = {
    "잠실": {"region": "서울 잠실", "lat": 37.5121, "lon": 127.0719},
    "고척": {"region": "서울 고척", "lat": 37.4982, "lon": 126.8671},
    "문학": {"region": "인천 문학", "lat": 37.4369, "lon": 126.6931},
    "수원": {"region": "수원", "lat": 37.2998, "lon": 127.0096},
    "대전": {"region": "대전", "lat": 36.3171, "lon": 127.4281},
    "대구": {"region": "대구", "lat": 35.8410, "lon": 128.6811},
    "광주": {"region": "광주", "lat": 35.1680, "lon": 126.8891},
    "사직": {"region": "부산 사직", "lat": 35.1943, "lon": 129.0615},
    "창원": {"region": "창원", "lat": 35.2222, "lon": 128.5822},
    "포항": {"region": "포항", "lat": 36.0147, "lon": 129.3650},
    "울산": {"region": "울산", "lat": 35.5351, "lon": 129.2582},
}

WEATHER_CODE_TEXT = {
    0: "맑음",
    1: "대체로 맑음",
    2: "부분 흐림",
    3: "흐림",
    45: "안개",
    48: "짙은 안개",
    51: "약한 이슬비",
    53: "이슬비",
    55: "강한 이슬비",
    56: "약한 어는비",
    57: "강한 어는비",
    61: "약한 비",
    63: "비",
    65: "강한 비",
    66: "약한 어는비",
    67: "강한 어는비",
    71: "약한 눈",
    73: "눈",
    75: "강한 눈",
    77: "진눈깨비",
    80: "소나기",
    81: "강한 소나기",
    82: "매우 강한 소나기",
    85: "약한 눈소나기",
    86: "강한 눈소나기",
    95: "뇌우",
    96: "약한 우박 뇌우",
    99: "강한 우박 뇌우",
}


def _resolve_stadium_coords(stadium_name: str) -> Optional[Dict[str, Any]]:
    name = str(stadium_name or "").strip()
    if not name:
        return None
    for key, info in STADIUM_REGION_COORDS.items():
        if key in name:
            return {"region": info["region"], "lat": info["lat"], "lon": info["lon"]}
    return None


def _weather_icon_key(code: int) -> str:
    if code in {95, 96, 99}:
        return "storm"
    if code in {45, 48}:
        return "fog"
    if code in {71, 73, 75, 77, 85, 86}:
        return "snow"
    if code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}:
        return "rain"
    if code in {1, 2}:
        return "partly"
    if code == 3:
        return "cloud"
    return "sun"


def _parse_game_datetime_kst(target_date: date, game_time: str) -> Optional[datetime]:
    text = str(game_time or "").strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2))
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return datetime(target_date.year, target_date.month, target_date.day, hour, minute, tzinfo=KST)


def _dust_grade(pm10: float) -> str:
    if pm10 <= 30:
        return "좋음"
    if pm10 <= 80:
        return "보통"
    if pm10 <= 150:
        return "나쁨"
    return "매우 나쁨"


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _build_game_weather_info(target_date: date, game_time: str, stadium_name: str) -> Dict[str, Any]:
    coords = _resolve_stadium_coords(stadium_name)
    if not coords:
        return {}

    now_kst = datetime.now(KST)
    game_start = _parse_game_datetime_kst(target_date=target_date, game_time=game_time)
    start_hour_dt = datetime(target_date.year, target_date.month, target_date.day, 0, 0, tzinfo=KST)
    if target_date == now_kst.date():
        start_hour_dt = now_kst.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    end_boundary = datetime(target_date.year, target_date.month, target_date.day, 23, 0, tzinfo=KST)
    end_midnight = datetime(target_date.year, target_date.month, target_date.day, 0, 0, tzinfo=KST) + timedelta(days=1)
    include_midnight = target_date == now_kst.date()
    if start_hour_dt > end_boundary and not include_midnight:
        return {}

    target_hours: list[datetime] = []
    cursor = start_hour_dt
    while cursor <= end_boundary:
        target_hours.append(cursor)
        cursor += timedelta(hours=1)
    if include_midnight and end_midnight not in target_hours:
        target_hours.append(end_midnight)

    if not target_hours:
        return {}

    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "timezone": "Asia/Seoul",
        "hourly": "temperature_2m,weather_code,precipitation_probability",
        "start_date": target_date.isoformat(),
        "end_date": (target_date + timedelta(days=1)).isoformat() if include_midnight else target_date.isoformat(),
    }
    try:
        weather_resp = _http_get_with_retries(OPENMETEO_FORECAST_URL, params=params, timeout=12)
        weather_resp.raise_for_status()
        weather_payload = weather_resp.json()
    except Exception:
        return {}

    hourly = weather_payload.get("hourly") or {}
    times = hourly.get("time") or []
    weather_codes = hourly.get("weather_code") or []
    temperatures = hourly.get("temperature_2m") or []
    rain_probs = hourly.get("precipitation_probability") or []
    by_time: Dict[str, Dict[str, Any]] = {}
    for idx, raw_time in enumerate(times):
        by_time[str(raw_time)] = {
            "code": int(weather_codes[idx]) if idx < len(weather_codes) and weather_codes[idx] is not None else 0,
            "temp": temperatures[idx] if idx < len(temperatures) else None,
            "pop": rain_probs[idx] if idx < len(rain_probs) else None,
        }

    hourly_items: list[Dict[str, Any]] = []
    for hour_dt in target_hours:
        key = hour_dt.strftime("%Y-%m-%dT%H:00")
        entry = by_time.get(key)
        if not entry:
            continue
        code = int(entry.get("code", 0) or 0)
        pop = int(entry.get("pop", 0) or 0)
        is_midnight = hour_dt.hour == 0 and hour_dt.date() > target_date
        label = "24:00" if is_midnight else hour_dt.strftime("%H:00")
        game_start_label = game_start.strftime("%H:%M") if game_start else ""
        is_game_start = bool(game_start_label) and game_start_label.startswith(label[:2] + ":")
        hourly_items.append(
            {
                "time_label": label,
                "weather": WEATHER_CODE_TEXT.get(code, "날씨"),
                "icon": _weather_icon_key(code),
                "rain_probability": pop,
                "temperature": (
                    f"{float(entry['temp']):.1f}"
                    if entry.get("temp") is not None and entry.get("temp") != ""
                    else "-"
                ),
                "is_game_start": is_game_start,
            }
        )

    if not hourly_items:
        return {}

    if game_start:
        game_window_pops = []
        for offset in range(-1, 5):
            slot = (game_start.replace(minute=0, second=0, microsecond=0) + timedelta(hours=offset)).strftime("%H:00")
            if slot == "00:00":
                slot = "24:00"
            for item in hourly_items:
                if item["time_label"] == slot:
                    game_window_pops.append(item["rain_probability"])
        if not game_window_pops:
            game_window_pops = [item["rain_probability"] for item in hourly_items]
    else:
        game_window_pops = [item["rain_probability"] for item in hourly_items]

    avg_pop = sum(game_window_pops) / max(1, len(game_window_pops))
    max_pop = max(game_window_pops) if game_window_pops else 0
    progress_probability = int(round(max(0, min(100, 100 - (avg_pop * 0.6 + max_pop * 0.4)))))

    aq_params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "timezone": "Asia/Seoul",
        "hourly": "pm10,pm2_5",
        "start_date": now_kst.date().isoformat(),
        "end_date": now_kst.date().isoformat(),
    }
    dust = {"pm10": "-", "pm2_5": "-", "grade": "-"}
    try:
        aq_resp = _http_get_with_retries(OPENMETEO_AIR_QUALITY_URL, params=aq_params, timeout=12)
        aq_resp.raise_for_status()
        aq_payload = aq_resp.json()
        aq_hourly = aq_payload.get("hourly") or {}
        aq_times = aq_hourly.get("time") or []
        pm10_values = aq_hourly.get("pm10") or []
        pm25_values = aq_hourly.get("pm2_5") or []
        now_hour_key = now_kst.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00")
        pick_idx = aq_times.index(now_hour_key) if now_hour_key in aq_times else (len(aq_times) - 1)
        if pick_idx >= 0:
            pm10 = _safe_float(pm10_values[pick_idx] if pick_idx < len(pm10_values) else None)
            pm25 = _safe_float(pm25_values[pick_idx] if pick_idx < len(pm25_values) else None)
            if pm10 is not None:
                dust["pm10"] = f"{pm10:.0f}"
                dust["grade"] = _dust_grade(pm10)
            if pm25 is not None:
                dust["pm2_5"] = f"{pm25:.0f}"
    except Exception:
        pass

    return {
        "region": coords["region"],
        "game_start_time": str(game_time or "").strip(),
        "hourly": hourly_items,
        "game_progress_probability": progress_probability,
        "dust": dust,
        "updated_at": now_kst.replace(microsecond=0).isoformat(),
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


def _is_missing_starter_name(name: str) -> bool:
    token = (name or "").strip()
    return token in {"", "-", "미정", "TBD", "예정"}


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
        response = _http_get_with_retries(feed_url, headers=headers, timeout=10)
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
        response = _http_get_with_retries(page_url, headers=headers, timeout=12)
        response.raise_for_status()
        html = response.text
    except Exception:
        return {
            "title": "",
            "url": YOUTUBE_PLAYLIST_URL.format(playlist_id=playlist_id),
            "published_at": "",
            "video_id": "",
            "thumbnail": "",
        }

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
    # 1) oEmbed is lightweight and tends to return channel-native title text.
    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json&hl=ko"
    url = f"https://www.youtube.com/watch?v={video_id}&hl=ko&gl=KR&persist_hl=1&persist_gl=1"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    try:
        oembed_resp = _http_get_with_retries(oembed_url, timeout=8, headers=headers)
        if oembed_resp.ok:
            oembed_payload = oembed_resp.json()
            oembed_title = str(oembed_payload.get("title", "") or "").strip()
            if oembed_title:
                return oembed_title
    except Exception:
        pass

    try:
        response = _http_get_with_retries(url, timeout=10, headers=headers)
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


def _http_get_with_retries(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 10,
    retries: int = 3,
) -> requests.Response:
    last_error: Optional[Exception] = None
    for attempt in range(retries):
        try:
            return requests.get(
                url,
                headers=headers,
                params=params,
                timeout=timeout,
            )
        except Exception as exc:  # requests exceptions
            last_error = exc
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
    if last_error:
        raise last_error
    raise RuntimeError("unreachable retry state")


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


def _fetch_box_score_scroll(game: Dict[str, Any], game_date: date) -> Dict[str, Any]:
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
        return json.loads(response.content.decode("utf-8-sig"))
    except Exception:
        return {}


def _extract_hanwha_boxscore_batters(
    box_data: Dict[str, Any],
    game: Dict[str, Any],
) -> list[Dict[str, str]]:
    if str(box_data.get("code", "")) != "100":
        return []

    arr_hitter = box_data.get("arrHitter", []) or []
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


def _extract_hanwha_boxscore_pitchers(
    box_data: Dict[str, Any],
    game: Dict[str, Any],
) -> list[Dict[str, str]]:
    if str(box_data.get("code", "")) != "100":
        return []

    arr_pitcher = box_data.get("arrPitcher", []) or []
    if len(arr_pitcher) < 2:
        return []

    hanwha_is_away = game.get("AWAY_ID") == HANWHA_TEAM_ID
    target_idx = 0 if hanwha_is_away else 1
    if target_idx >= len(arr_pitcher):
        return []

    try:
        table = json.loads(str(arr_pitcher[target_idx].get("table", "{}") or "{}"))
    except Exception:
        return []

    rows = table.get("rows", []) or []
    if not rows:
        return []

    pitchers: list[Dict[str, str]] = []
    for row in rows:
        cells = (row or {}).get("row", [])
        if len(cells) < 17:
            continue

        name = _cell_text(cells[0])
        if not name or name == "-":
            continue
        pitchers.append(
            {
                "name": name,
                "ip": _cell_text(cells[6]) or "-",
                "hit": _cell_text(cells[10]) or "-",
                "run": _cell_text(cells[14]) or "-",
                "er": _cell_text(cells[15]) or "-",
                "bb": _cell_text(cells[12]) or "-",
                "so": _cell_text(cells[13]) or "-",
                "era": _cell_text(cells[16]) or "-",
            }
        )
    return pitchers


def _fetch_hanwha_game_boxscore_stats(
    game: Dict[str, Any],
    game_date: date,
) -> Dict[str, list[Dict[str, str]]]:
    box_data = _fetch_box_score_scroll(game=game, game_date=game_date)
    return {
        "batters": _extract_hanwha_boxscore_batters(box_data=box_data, game=game),
        "pitchers": _extract_hanwha_boxscore_pitchers(box_data=box_data, game=game),
    }


def _looks_numeric_token(value: str) -> bool:
    token = (value or "").strip()
    return bool(re.match(r"^\d+(\.\d+)?$", token))


def _extract_live_text_hanwha_stats(
    game: Dict[str, Any],
    season_id: str,
    game_id: str,
    sr_id: str,
) -> Dict[str, list[Dict[str, str]]]:
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
        return {"batters": [], "pitchers": []}

    soup = BeautifulSoup(response.text, "html.parser")
    team_name = str(game.get("AWAY_NM") if game.get("AWAY_ID") == HANWHA_TEAM_ID else game.get("HOME_NM") or "")
    lineup_rows: list[list[str]] = []
    batter_rows: list[list[str]] = []
    pitcher_rows: list[list[str]] = []
    pitcher_detail_rows: list[list[str]] = []

    for table in soup.find_all("table"):
        caption_tag = table.find("caption")
        caption = _clean_html_text(caption_tag.get_text(" ", strip=True) if caption_tag else "")
        if not caption or (team_name and team_name not in caption):
            continue

        rows: list[list[str]] = []
        for tr in table.find_all("tr")[1:]:
            cells = [_clean_html_text(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
            if any(cells):
                rows.append(cells)
        if not rows:
            continue

        first = rows[0]
        if "투수" in caption and len(first) >= 5:
            pitcher_rows = rows
            continue
        if len(first) >= 12 and not re.match(r"^\d+$", first[0] or ""):
            ip_token = first[1]
            if _looks_numeric_token(first[2]) and _looks_numeric_token(first[10]) and _looks_numeric_token(first[11]):
                if _looks_numeric_token(ip_token) or "." in ip_token or " " in ip_token:
                    pitcher_detail_rows = rows
                    continue
        if "타" in caption:
            if len(first) >= 5 and re.match(r"^\d+$", first[0] or ""):
                lineup_rows = rows
            elif len(first) >= 4 and not re.match(r"^\d+$", first[0] or ""):
                batter_rows = rows

    batters: list[Dict[str, str]] = []
    detail_by_name: Dict[str, list[str]] = {}
    for row in batter_rows:
        if len(row) >= 4 and _looks_numeric_token(row[1]) and _looks_numeric_token(row[2]) and _looks_numeric_token(row[3]):
            detail_by_name[row[0]] = row

    for row in lineup_rows:
        if len(row) < 5:
            continue
        order = row[0]
        if not re.match(r"^\d+$", order):
            continue
        name = row[1]
        detail = detail_by_name.get(name, row)
        batters.append(
            {
                "order": order,
                "position": "-",
                "name": name,
                "ab": detail[1] if len(detail) > 1 else (row[2] if len(row) > 2 else "-"),
                "hit": detail[2] if len(detail) > 2 else (row[3] if len(row) > 3 else "-"),
                "run": detail[3] if len(detail) > 3 else (row[4] if len(row) > 4 else "-"),
                "avg": "-",
            }
        )

    pitchers: list[Dict[str, str]] = []
    for row in pitcher_rows:
        if len(row) < 5:
            continue
        pitchers.append(
            {
                "name": row[0],
                "ip": row[1],
                "hit": row[2],
                "run": row[3],
                "er": row[4],
                "bb": "-",
                "so": "-",
                "era": "-",
            }
        )
    if len(pitchers) <= 1 and pitcher_detail_rows:
        pitchers = []
        for row in pitcher_detail_rows:
            if len(row) < 12:
                continue
            pitchers.append(
                {
                    "name": row[0],
                    "ip": row[1],
                    "hit": row[5],
                    "run": row[10],
                    "er": row[11],
                    "bb": row[7],
                    "so": row[9],
                    "era": "-",
                }
            )

    batters = [b for b in batters if b.get("name")]
    pitchers = [p for p in pitchers if p.get("name")]
    return {"batters": batters[:9], "pitchers": pitchers}


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
    is_today_target = target_date == date.today()
    can_trust_today_lineup = bool(lineup_data.get("lineup_ck")) or _is_live_game(game) or _is_final_game(game)

    # KBO can return full lineup rows while LINEUP_CK remains false.
    # Prefer actual lineup rows when present to avoid stale fallback display.
    if is_today_target and len(today_lineup) >= 9 and can_trust_today_lineup:
        realtime_stats = _fetch_hanwha_game_boxscore_stats(game=game, game_date=target_date)
        if not realtime_stats.get("batters") or not realtime_stats.get("pitchers"):
            live_stats = _extract_live_text_hanwha_stats(
                game=game,
                season_id=season_id,
                game_id=game_id,
                sr_id=sr_id,
            )
            if not realtime_stats.get("batters"):
                realtime_stats["batters"] = live_stats.get("batters", [])
            if not realtime_stats.get("pitchers"):
                realtime_stats["pitchers"] = live_stats.get("pitchers", [])
        if not realtime_stats.get("batters") or not realtime_stats.get("pitchers"):
            latest_game = _find_latest_finished_hanwha_game(before_date=target_date)
            if latest_game:
                latest_game_date = latest_game.get("_resolved_date") or (target_date - timedelta(days=1))
                fallback_stats = _fetch_hanwha_game_boxscore_stats(game=latest_game, game_date=latest_game_date)
                if not realtime_stats.get("batters"):
                    realtime_stats["batters"] = fallback_stats.get("batters", [])
                if not realtime_stats.get("pitchers"):
                    realtime_stats["pitchers"] = fallback_stats.get("pitchers", [])
        realtime_batters = realtime_stats.get("batters", [])
        realtime_pitchers = realtime_stats.get("pitchers", [])
        by_order = {
            str(item.get("order") or ""): item
            for item in realtime_batters
            if str(item.get("order") or "")
        }
        by_name = {
            str(item.get("name") or ""): item
            for item in realtime_batters
            if str(item.get("name") or "")
        }
        merged_batters = []
        for item in today_lineup[:9]:
            order = str(item.get("order", "-"))
            name = str(item.get("name", "-"))
            stat_src = by_order.get(order) or by_name.get(name) or {}
            merged_batters.append(
                {
                    "order": order,
                    "position": item.get("position", "-"),
                    "name": name,
                    "ab": stat_src.get("ab", "-"),
                    "hit": stat_src.get("hit", "-"),
                    "run": stat_src.get("run", "-"),
                    "avg": stat_src.get("avg", "-"),
                }
            )
        return {
            "is_official": True,
            "notice": "",
            "source_game_date": target_date.isoformat(),
            "batters": merged_batters,
            "pitchers": realtime_pitchers,
        }

    latest_game = _find_latest_finished_hanwha_game(before_date=target_date)
    if not latest_game:
        return {
            "is_official": False,
            "notice": "아직 라인업이 발표되지 않아 전날 라인업을 보여드립니다.",
            "source_game_date": "",
            "batters": [],
            "pitchers": [],
        }

    latest_game_date = latest_game.get("_resolved_date") or (target_date - timedelta(days=1))
    fallback_stats = _fetch_hanwha_game_boxscore_stats(game=latest_game, game_date=latest_game_date)
    probe_date = latest_game_date
    while (
        not fallback_stats.get("batters")
        and not fallback_stats.get("pitchers")
        and probe_date > (target_date - timedelta(days=14))
    ):
        older_game = _find_latest_finished_hanwha_game(before_date=probe_date)
        if not older_game:
            break
        older_date = older_game.get("_resolved_date") or (probe_date - timedelta(days=1))
        fallback_stats = _fetch_hanwha_game_boxscore_stats(game=older_game, game_date=older_date)
        latest_game_date = older_date
        probe_date = older_date
    return {
        "is_official": False,
        "notice": "아직 라인업이 발표되지 않아 전날 라인업을 보여드립니다.",
        "source_game_date": latest_game_date.isoformat(),
        "batters": fallback_stats.get("batters", []),
        "pitchers": fallback_stats.get("pitchers", []),
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
        "war": "-",
        "games": basic.get("G", "-"),
        "avg_innings": basic.get("IP", "-"),
        "qs": advanced.get("QS", "-"),
        "whip": advanced.get("WHIP", "-"),
        "image_url": image_url,
    }


def _fetch_pitcher_record_analysis(
    season_id: str,
    sr_id: str,
    away_team_id: str,
    away_pit_id: str,
    home_team_id: str,
    home_pit_id: str,
) -> Dict[str, Dict[str, str]]:
    payload = {
        "leId": "1",
        "srId": sr_id or "0",
        "seasonId": season_id or str(date.today().year),
        "awayTeamId": away_team_id or "",
        "awayPitId": away_pit_id or "",
        "homeTeamId": home_team_id or "",
        "homePitId": home_pit_id or "",
        "groupSc": "SEASON",
    }
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.koreabaseball.com/"}
    empty = {"away": {}, "home": {}}
    try:
        response = requests.post(
            KBO_PITCHER_RECORD_ANALYSIS_URL,
            data=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        data = json.loads(response.content.decode("utf-8-sig"))
    except Exception:
        return empty

    rows = data.get("rows", []) if isinstance(data, dict) else []
    if not isinstance(rows, list) or len(rows) < 2:
        return empty

    def parse_row(row_obj: Dict[str, Any]) -> Dict[str, str]:
        row_cells = row_obj.get("row", []) if isinstance(row_obj, dict) else []
        if not isinstance(row_cells, list):
            return {}
        parsed = {"war": "-", "games": "-", "avg_innings": "-", "qs": "-", "whip": "-"}
        for cell in row_cells:
            cls = str((cell or {}).get("Class") or "")
            text = _cell_text(cell) or "-"
            if "td_war_" in cls:
                parsed["war"] = text
            elif "td_game_" in cls:
                parsed["games"] = text
            elif "td_startinn_" in cls.lower():
                parsed["avg_innings"] = text
            elif "td_qs_" in cls:
                parsed["qs"] = text
            elif "td_whip_" in cls:
                parsed["whip"] = text
        return parsed

    return {
        "away": parse_row(rows[0]),
        "home": parse_row(rows[1]),
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


def _parse_head_to_head_record(record: str) -> tuple[int, int, int]:
    parts = [p.strip() for p in str(record or "").split("-")]
    if len(parts) != 3:
        return (0, 0, 0)
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        return (0, 0, 0)


def _format_head_to_head_record(wins: int, losses: int, draws: int) -> str:
    return f"{wins}-{losses}-{draws}"


def _apply_final_game_to_head_to_head(
    summary: Dict[str, str],
    final_game: Dict[str, Any],
    away_team: str,
    home_team: str,
) -> Dict[str, str]:
    if not final_game:
        return summary
    if str(final_game.get("AWAY_NM", "") or "") != away_team:
        return summary
    if str(final_game.get("HOME_NM", "") or "") != home_team:
        return summary
    if not _is_final_game(final_game):
        return summary

    try:
        away_score = int(str(final_game.get("T_SCORE_CN", "0") or "0"))
        home_score = int(str(final_game.get("B_SCORE_CN", "0") or "0"))
    except Exception:
        return summary

    away_w, away_l, away_d = _parse_head_to_head_record(summary.get("away_vs_home", "-"))
    home_w, home_l, home_d = _parse_head_to_head_record(summary.get("home_vs_away", "-"))

    if away_score > home_score:
        away_w += 1
        home_l += 1
    elif away_score < home_score:
        away_l += 1
        home_w += 1
    else:
        away_d += 1
        home_d += 1

    return {
        "away_vs_home": _format_head_to_head_record(away_w, away_l, away_d),
        "home_vs_away": _format_head_to_head_record(home_w, home_l, home_d),
    }


def _parse_season_record(record: str) -> tuple[int, int, int]:
    match = re.search(r"(\d+)\s*승\s*(\d+)\s*패\s*(\d+)\s*무", str(record or ""))
    if not match:
        return (0, 0, 0)
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _format_season_record(wins: int, losses: int, draws: int) -> str:
    return f"{wins}승 {losses}패 {draws}무"


def _apply_outcome_to_last5(last5: str, outcome: str) -> str:
    tokens = [ch for ch in str(last5 or "") if ch in {"승", "패", "무"}]
    tokens.append(outcome)
    return "".join(tokens[-5:]) if tokens else outcome


def _apply_final_game_to_team_comparison(
    team_comparison: Dict[str, Any],
    final_game: Dict[str, Any],
    away_team: str,
    home_team: str,
) -> Dict[str, Any]:
    if not isinstance(team_comparison, dict) or not final_game:
        return team_comparison
    if not _is_final_game(final_game):
        return team_comparison

    final_away = str(final_game.get("AWAY_NM", "") or "")
    final_home = str(final_game.get("HOME_NM", "") or "")
    if not final_away or not final_home:
        return team_comparison

    try:
        away_score = int(str(final_game.get("T_SCORE_CN", "0") or "0"))
        home_score = int(str(final_game.get("B_SCORE_CN", "0") or "0"))
    except Exception:
        return team_comparison

    if away_score > home_score:
        final_outcomes = {final_away: "승", final_home: "패"}
    elif away_score < home_score:
        final_outcomes = {final_away: "패", final_home: "승"}
    else:
        final_outcomes = {final_away: "무", final_home: "무"}

    adjusted = dict(team_comparison)
    for side_key, team_name in (("away", away_team), ("home", home_team)):
        side = adjusted.get(side_key)
        if not isinstance(side, dict):
            continue
        outcome = final_outcomes.get(team_name)
        if not outcome:
            continue

        wins, losses, draws = _parse_season_record(str(side.get("season_record", "")))
        if outcome == "승":
            wins += 1
        elif outcome == "패":
            losses += 1
        else:
            draws += 1

        next_side = dict(side)
        next_side["season_record"] = _format_season_record(wins, losses, draws)
        next_side["last5"] = _apply_outcome_to_last5(str(side.get("last5", "")), outcome)
        adjusted[side_key] = next_side

    return adjusted


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
    today_final_hanwha_game: Optional[Dict[str, Any]] = None
    try:
        today_games = _fetch_games(today)
        today_finals = [g for g in today_games if _is_hanwha_game(g) and _is_final_game(g)]
        if today_finals:
            today_finals.sort(
                key=lambda g: (
                    str(g.get("G_TM", "") or ""),
                    str(g.get("G_ID", "") or ""),
                ),
                reverse=True,
            )
            today_final_hanwha_game = today_finals[0]
    except Exception:
        today_final_hanwha_game = None

    for offset in range(max_days_ahead + 1):
        target = today + timedelta(days=offset)
        games = _fetch_games(target)
        for game in games:
            if not _is_hanwha_game(game):
                continue
            # KBO can report SCORE_CK=1 before first pitch, so only skip true final games.
            if offset == 0 and _is_final_game(game):
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

            # Starter-name fallback: LiveText often has names earlier than game list payload.
            is_live_game = _is_live_game(game)
            if game_id and (_is_missing_starter_name(away_starter) or _is_missing_starter_name(home_starter)):
                live_starters = _fetch_live_starter_names(game_id=game_id, season_id=season_id, sr_id=sr_id)
                away_starter = live_starters.get("away_starter", away_starter)
                home_starter = live_starters.get("home_starter", home_starter)

            # Reload by gameId/date when IDs or names are still missing.
            if game_id and (
                not away_starter_id
                or not home_starter_id
                or _is_missing_starter_name(away_starter)
                or _is_missing_starter_name(home_starter)
            ):
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

            away_starter = away_starter.strip() if away_starter else ""
            home_starter = home_starter.strip() if home_starter else ""
            if _is_missing_starter_name(away_starter):
                away_starter = "미정"
            if _is_missing_starter_name(home_starter):
                home_starter = "미정"

            hanwha_starter = away_starter if is_away else home_starter
            if _is_missing_starter_name(hanwha_starter):
                hanwha_starter = _extract_hanwha_starter(game) or "미정"

            away_starter_stats = _fetch_pitcher_stats(away_starter_id)
            home_starter_stats = _fetch_pitcher_stats(home_starter_id)
            away_team_id = str(game.get("AWAY_ID", ""))
            home_team_id = str(game.get("HOME_ID", ""))
            analysis_stats = _fetch_pitcher_record_analysis(
                season_id=season_id,
                sr_id=sr_id,
                away_team_id=away_team_id,
                away_pit_id=away_starter_id,
                home_team_id=home_team_id,
                home_pit_id=home_starter_id,
            )
            away_analysis = analysis_stats.get("away", {})
            home_analysis = analysis_stats.get("home", {})
            if not away_starter_stats:
                away_starter_stats = {}
            if not home_starter_stats:
                home_starter_stats = {}
            away_starter_stats["war"] = away_analysis.get("war") or away_starter_stats.get("war") or "-"
            home_starter_stats["war"] = home_analysis.get("war") or home_starter_stats.get("war") or "-"
            team_comparison = _fetch_team_comparison(game_id, season_id, away_team_id, home_team_id)
            if offset > 0 and today_final_hanwha_game:
                team_comparison = _apply_final_game_to_team_comparison(
                    team_comparison=team_comparison,
                    final_game=today_final_hanwha_game,
                    away_team=str(game.get("AWAY_NM", "") or ""),
                    home_team=str(game.get("HOME_NM", "") or ""),
                )
            head_to_head_summary = _find_head_to_head_record(
                rank_daily.get("head_to_head", []),
                game.get("AWAY_NM", ""),
                game.get("HOME_NM", ""),
            )
            # Rank-daily matrix can lag right after final.
            # For next-game view, reflect today's just-finished result immediately.
            if offset > 0 and today_final_hanwha_game:
                head_to_head_summary = _apply_final_game_to_head_to_head(
                    summary=head_to_head_summary,
                    final_game=today_final_hanwha_game,
                    away_team=str(game.get("AWAY_NM", "") or ""),
                    home_team=str(game.get("HOME_NM", "") or ""),
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
            weather_info = _build_game_weather_info(
                target_date=target,
                game_time=str(game.get("G_TM", "") or ""),
                stadium_name=str(game.get("S_NM", "") or ""),
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
                "weather_info": weather_info,
                "eagles_tv": eagles_tv,
                "latest_news": latest_news,
            }
    return None
