import re

from loguru import logger
from telegram import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters

from config.config import cfg
from utils.login_prompt import reply_need_login
from utils.resolve import get_gallery_info
from utils.service_api import (
    ServiceAPIError,
    get_user_api_key,
    parse_gallery,
)


async def reply_gallery_info(
    update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, gid: str, token: str
):
    msg = await update.effective_message.reply_text("🔍 正在解析画廊信息...")
    logger.info(f"解析画廊 {url}")

    try:
        text, has_spoiler, thumb = await get_gallery_info(gid, token)
    except Exception as e:
        await msg.edit_text("❌ 画廊解析失败，请检查链接或稍后再试")
        logger.error(f"画廊 {url} 解析失败：{e}")
        return

    keyboard = [
        [InlineKeyboardButton("🌐 跳转画廊", url=url)],
    ]
    if update.effective_chat.type == "private":
        has_spoiler = False
        keyboard[0].append(
            InlineKeyboardButton(
                "📦 归档下载",
                callback_data=f"download|{gid}|{token}",
            )
        )
        if cfg["AD"]["text"] and cfg["AD"]["url"]:
            keyboard.append(
                [InlineKeyboardButton(cfg["AD"]["text"], url=cfg["AD"]["url"])]
            )
    else:
        keyboard[0].append(
            InlineKeyboardButton(
                "🤖 在 Bot 中打开",
                url=f"https://t.me/{context.application.bot.username}?start={gid}_{token}",
            )
        )

    await msg.delete()
    await update.effective_message.reply_photo(
        photo=thumb,
        caption=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        has_spoiler=has_spoiler,
        parse_mode="HTML",
    )


async def resolve_gallery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text
    url, gid, token = re.search(
        r"https://e[-x]hentai\.org/g/(\d+)/([0-9a-f]{10})", text
    ).group(0, 1, 2)
    await reply_gallery_info(update, context, url, gid, token)


async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    api_key = get_user_api_key(user_id)
    if not api_key:
        await reply_need_login(update, context, "⚠️ 请先登录后再获取下载链接")
        return

    _, gid, token = query.data.split("|")

    caption = re.sub(
        r"\n\n❌ 下载链接获取失败.*$",
        "",
        update.effective_message.caption,
    )

    await update.effective_message.edit_caption(
        caption=f"{caption}\n\n⏳ 正在获取下载链接，请稍等...",
        reply_markup=update.effective_message.reply_markup,
        parse_mode="HTML",
    )
    logger.info(f"获取 https://e-hentai.org/g/{gid}/{token}/ 下载链接")

    error_text = "服务端未返回下载链接"
    try:
        result = await parse_gallery(api_key, gid, token)
        d_url = result.get("archive_url")
        if not d_url:
            error_text = result.get("error", error_text)
    except ServiceAPIError as e:
        d_url = None
        error_text = e.message
    except Exception as e:
        d_url = None
        error_text = str(e)

    if d_url:
        status_text = "✅ 下载链接获取成功"
        if result.get("cached"):
            status_text += "（缓存）"

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🌐 跳转画廊", url=f"https://e-hentai.org/g/{gid}/{token}/"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔗 复制下载链接", copy_text=CopyTextButton(d_url)
                    ),
                    InlineKeyboardButton("📥 跳转下载", url=d_url),
                ],
            ]
        )

        await update.effective_message.edit_caption(
            caption=f"{caption}\n\n{status_text}",
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    else:
        await update.effective_message.edit_caption(
            caption=f"{caption}\n\n❌ 下载链接获取失败：{error_text}",
            reply_markup=update.effective_message.reply_markup,
            parse_mode="HTML",
        )
        logger.error(f"https://e-hentai.org/g/{gid}/{token}/ 下载链接获取失败")


def register(app):
    app.add_handler(
        MessageHandler(
            filters.Regex(r"https://e[-x]hentai\.org/g/\d+/[0-9a-f]{10}"),
            resolve_gallery,
        )
    )
    app.add_handler(CallbackQueryHandler(download, pattern=r"^download"))
