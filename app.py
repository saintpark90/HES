import base64
import io
import os
from datetime import datetime
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, render_template, request, send_from_directory, url_for
from PIL import Image, ImageEnhance, ImageFilter

from crawler import get_next_hanwha_game

app = Flask(__name__)

REPLICATE_API_BASE = "https://api.replicate.com/v1"
REPLICATE_MODEL_OWNER = os.getenv("REPLICATE_MODEL_OWNER", "nightmareai")
REPLICATE_MODEL_NAME = os.getenv("REPLICATE_MODEL_NAME", "real-esrgan")


def _download_image_bytes(image_url: str) -> bytes:
    parsed = urlparse(image_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("image_url must be a valid http/https URL.")
    response = requests.get(image_url, timeout=20)
    response.raise_for_status()
    return response.content


def _upscale_with_replicate(image_url: str, scale: int) -> str:
    token = os.getenv("REPLICATE_API_TOKEN", "")
    if not token:
        raise RuntimeError("Missing REPLICATE_API_TOKEN")

    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "input": {
            "image": image_url,
            "scale": scale,
            "face_enhance": True,
        }
    }
    create_url = f"{REPLICATE_API_BASE}/models/{REPLICATE_MODEL_OWNER}/{REPLICATE_MODEL_NAME}/predictions"
    created = requests.post(create_url, headers=headers, json=payload, timeout=20)
    created.raise_for_status()
    prediction = created.json()
    poll_url = prediction.get("urls", {}).get("get")
    if not poll_url:
        raise RuntimeError("Replicate response does not include poll URL.")

    for _ in range(25):
        poll = requests.get(poll_url, headers=headers, timeout=20)
        poll.raise_for_status()
        prediction = poll.json()
        status = prediction.get("status")
        if status == "succeeded":
            output = prediction.get("output")
            if isinstance(output, list) and output:
                return output[-1]
            if isinstance(output, str):
                return output
            raise RuntimeError("Replicate output is empty.")
        if status in {"failed", "canceled"}:
            raise RuntimeError(f"Replicate failed: {prediction.get('error', 'unknown error')}")
    raise RuntimeError("Replicate request timed out while polling.")


def _upscale_locally_base64(image_url: str, scale: int, sharpness: float = 1.3) -> str:
    raw = _download_image_bytes(image_url)
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    target_size = (max(1, image.width * scale), max(1, image.height * scale))
    upscaled = image.resize(target_size, Image.Resampling.LANCZOS)
    upscaled = upscaled.filter(ImageFilter.UnsharpMask(radius=1.2, percent=150, threshold=3))
    upscaled = ImageEnhance.Sharpness(upscaled).enhance(sharpness)

    output_buffer = io.BytesIO()
    upscaled.save(output_buffer, format="JPEG", quality=95, optimize=True)
    encoded = base64.b64encode(output_buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _build_og_context(game_info: dict | None) -> dict:
    share_url = request.url_root.rstrip("/") + url_for("share_hanwha_next")
    fixed_thumb_url = request.url_root.rstrip("/") + url_for("thumbnail_png")

    if game_info:
        title = f"한화 다음 경기: {game_info['matchup']}"
        description = (
            f"{game_info['game_date']} {game_info['game_time']} | "
            f"한화 선발: {game_info['hanwha_starter']} | 상대팀: {game_info['opponent']}"
        )
        image_url = fixed_thumb_url
    else:
        title = "한화 다음 경기 정보"
        description = "현재 한화 이글스의 다음 경기 정보를 찾을 수 없습니다."
        image_url = fixed_thumb_url

    return {
        "title": title,
        "description": description,
        "url": share_url,
        "image": image_url,
    }


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


@app.get("/")
def index():
    game_info = get_next_hanwha_game()
    og = _build_og_context(game_info)
    return render_template("index.html", game_info=game_info, og=og, updated_at=_now_iso())


@app.get("/share/hanwha-next")
def share_hanwha_next():
    game_info = get_next_hanwha_game()
    og = _build_og_context(game_info)
    return render_template("index.html", game_info=game_info, og=og, updated_at=_now_iso())


@app.get("/api/game-info")
def game_info_api():
    game_info = get_next_hanwha_game()
    return jsonify({"ok": True, "game_info": game_info, "updated_at": _now_iso()})


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


@app.get("/thumbnail.png")
def thumbnail_png():
    return send_from_directory(app.root_path, "thumbnail.png")


@app.get("/styles.css")
def styles():
    return send_from_directory(app.root_path, "styles.css")


@app.get("/script.js")
def script():
    return send_from_directory(app.root_path, "script.js")


@app.post("/api/upscale-image")
def upscale_image():
    """
    Request JSON:
    {
      "image_url": "<required>",
      "scale": 2 | 3 | 4 (optional, default=2)
    }
    """
    payload = request.get_json(silent=True) or {}
    image_url = str(payload.get("image_url", "")).strip()
    scale = int(payload.get("scale", 2) or 2)
    scale = 2 if scale not in {2, 3, 4} else scale

    if not image_url:
        return jsonify({"ok": False, "error": "image_url is required."}), 400

    # Primary path: Replicate Real-ESRGAN (cloud inference).
    try:
        upscaled_url = _upscale_with_replicate(image_url, scale)
        return jsonify(
            {
                "ok": True,
                "provider": "replicate",
                "scale": scale,
                "input_image_url": image_url,
                "upscaled_image_url": upscaled_url,
            }
        )
    except Exception as cloud_err:
        # Fallback path: local upscale with Pillow to avoid complete failure.
        try:
            data_url = _upscale_locally_base64(image_url, scale=scale)
            return jsonify(
                {
                    "ok": True,
                    "provider": "local-fallback",
                    "scale": scale,
                    "input_image_url": image_url,
                    "upscaled_image_data_url": data_url,
                    "warning": f"Cloud upscale unavailable, fallback used: {cloud_err}",
                }
            )
        except Exception as local_err:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "Failed to upscale image.",
                        "cloud_error": str(cloud_err),
                        "local_error": str(local_err),
                    }
                ),
                500,
            )


if __name__ == "__main__":
    app.run(debug=True)
