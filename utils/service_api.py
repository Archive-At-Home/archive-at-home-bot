import json
import os
from pathlib import Path
from urllib.parse import urlencode

import httpx
from loguru import logger

from config.config import cfg


class ServiceAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = Path(
    os.path.join(BASE_DIR, "..", "data", "user_service_tokens.json")
).resolve()
API_BASE = (
    cfg.get("NEW_SERVICE", {}).get("base_url", "http://127.0.0.1:8080").rstrip("/")
)


def _load_tokens() -> dict[str, str]:
    if TOKEN_FILE.exists():
        try:
            return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"读取 token 文件失败，将使用空数据: {e}")
            return {}
    return {}


def _save_tokens(data: dict[str, str]) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_user_api_key(user_id: int) -> str | None:
    return _load_tokens().get(str(user_id))


def set_user_api_key(user_id: int, api_key: str) -> None:
    db = _load_tokens()
    db[str(user_id)] = api_key
    _save_tokens(db)


def get_login_url(bot_username: str, bot_id: int | None = None) -> str:
    params_dict = {
        "redirect_url": f"https://t.me/{bot_username}",
    }
    if bot_id is not None:
        params_dict["botId"] = bot_id
    params = urlencode(params_dict)
    return f"{API_BASE}/auth/telegram/login?{params}"


def _extract_error(response: httpx.Response) -> str:
    try:
        body = response.json()
        if isinstance(body, dict):
            return body.get("error") or body.get("message") or response.text
    except Exception:
        pass
    return response.text


async def _call_api(
    method: str, path: str, api_key: str, body: dict | None = None
) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Client": cfg.get("NEW_SERVICE", {}).get("client"),
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(
        base_url=API_BASE,
        timeout=45,
        proxy=cfg.get("proxy") or None,
    ) as client:
        response = await client.request(method, path, headers=headers, json=body)
        if response.status_code >= 400:
            raise ServiceAPIError(response.status_code, _extract_error(response))
        return response.json()


async def parse_gallery(api_key: str, gid: str, token: str) -> dict:
    return await _call_api(
        "POST",
        "/api/v1/parse",
        api_key,
        {"gallery_id": gid, "gallery_key": token},
    )


async def get_me(api_key: str) -> dict:
    return await _call_api("GET", "/api/v1/me", api_key)


async def user_checkin(api_key: str) -> dict:
    return await _call_api("POST", "/api/v1/me/checkin", api_key)


async def reset_api_key(api_key: str) -> dict:
    return await _call_api("POST", "/api/v1/me/reset-key", api_key)
