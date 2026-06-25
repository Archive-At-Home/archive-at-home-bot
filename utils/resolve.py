import html
import re
from collections import defaultdict
from datetime import datetime

from config.config import cfg
from utils.http_client import http

tag_map = defaultdict(lambda: {"name": "", "data": {}})

GALLERY_URL_RE = re.compile(r"https://e[-x]hentai\.org/g/(\d+)/([0-9a-f]{10})", re.I)
SAMPLE_URL_RE = re.compile(r"https://e[-x]hentai\.org/s/[0-9a-f]{10}/\d+-\d+", re.I)


async def fetch_tag_map(_):
    db = (
        await http.get(
            "https://github.com/EhTagTranslation/Database/releases/latest/download/db.text.json",
            follow_redirects=True,
        )
    ).json()

    global tag_map
    tag_map = defaultdict(lambda: {"name": "", "data": {}})

    for entry in db["data"][2:]:
        namespace = entry["namespace"]
        tag_map[namespace]["name"] = entry["frontMatters"]["name"]
        tag_map[namespace]["data"].update(
            {key: value["name"] for key, value in entry["data"].items()}
        )


async def resolve_sample_to_gallery(sample_url: str):
    sample_url = sample_url.replace("e-hentai.org", "exhentai.org", 1)
    response = await http.get(sample_url, follow_redirects=True)
    page = response.text

    match = GALLERY_URL_RE.search(page)
    if not match:
        raise ValueError("未在 /s/ 页面中找到画廊链接")
    gid, token = match.group(1), match.group(2)

    thumb = None
    photo_proxy = cfg.get("PHOTO_PROXY_URL")
    if photo_proxy and (thumb_match := re.search(
        r'id="img"[^>]*\ssrc="([^"]+)"', page, re.I
    )):
        thumb = photo_proxy + html.unescape(thumb_match.group(1))

    return f"https://exhentai.org/g/{gid}/{token}/", gid, token, thumb


async def get_gallery_info(gid, token):
    """获取画廊基础信息"""
    response = await http.post(
        "https://e-hentai.org/api.php",
        json={"method": "gdata", "gidlist": [[gid, token]], "namespace": 1},
    )
    gallery_info = response.json().get("gmetadata")[0]

    user_GP_cost = (int(gallery_info["filesize"] / 1e6 * 20) + 1) * (
        3 if datetime.now().timestamp() - int(gallery_info["posted"]) > 31536000 else 1
    )

    new_tags = defaultdict(list)
    for item in gallery_info["tags"]:
        ns, sep, tag = item.partition(":")
        if not sep:
            continue
        if (ns_info := tag_map.get(ns)) and (tag_name := ns_info["data"].get(tag)):
            new_tags[ns_info["name"]].append(f"#{tag_name}")

    tag_text = "\n".join(
        f"{ns_name}：{' '.join(tags_list)}" for ns_name, tags_list in new_tags.items()
    )

    text = (
        f"📌 主标题：{gallery_info['title']}\n"
        + (
            f"⭐ 评分：{gallery_info['rating']}\n"
            if float(gallery_info["posted"]) < datetime.now().timestamp() - 172800
            else ""
        )
        + f"<blockquote expandable>📙 副标题：{gallery_info['title_jpn']}\n"
        f"📂 类型：{gallery_info['category']}\n"
        f"👤 上传者：<a href='https://e-hentai.org/uploader/{gallery_info['uploader']}'>{gallery_info['uploader']}</a>\n"
        f"🕒 上传时间：{datetime.fromtimestamp(float(gallery_info['posted'])):%Y-%m-%d %H:%M}\n"
        f"📄 页数：{gallery_info['filecount']}\n\n"
        f"{tag_text}\n\n"
        f"💰 归档消耗 GP：{user_GP_cost}</blockquote>"
    )

    return (
        text,
        gallery_info["category"] != "Non-H",
        gallery_info["thumb"].replace("s.exhentai", "ehgt"),
    )
