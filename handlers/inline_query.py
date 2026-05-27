import re
import uuid

from loguru import logger
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InlineQueryResultPhoto,
    InlineQueryResultsButton,
    InputTextMessageContent,
    Update,
)
from telegram.ext import CallbackQueryHandler, ContextTypes, InlineQueryHandler

from utils.resolve import get_gallery_info
from utils.service_api import (
    ServiceAPIError,
    get_user_api_key,
    user_checkin,
)


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip()

    button = InlineQueryResultsButton(text="到Bot查看更多信息", start_parameter="start")

    # 没输入时提示
    if not query:
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "签到", callback_data=f"checkin|{update.effective_user.id}"
                    )
                ]
            ]
        )
        results = [
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="请输入 eh/ex 链接以获取预览",
                input_message_content=InputTextMessageContent("请输入链接"),
            ),
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="我的信息（签到）",
                input_message_content=InputTextMessageContent("点击按钮进行签到"),
                description="签到并查看自己的信息",
                reply_markup=keyboard,
            ),
        ]

        await update.inline_query.answer(results, button=button, cache_time=0)
        return

    # 正则匹配合法链接（严格格式）
    pattern = r"^https://e[-x]hentai\.org/g/(\d+)/([0-9a-f]{10})/?$"
    match = re.match(pattern, query)
    if not match:
        results = [
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="链接格式错误",
                input_message_content=InputTextMessageContent("请输入合法链接"),
            )
        ]
        await update.inline_query.answer(results)
        return

    gid, token = match.groups()

    logger.info(f"解析画廊 {query}")
    try:
        text, _, thumb = await get_gallery_info(gid, token)
    except Exception as e:
        logger.warning(f"Inline 模式解析画廊失败: {query}，错误: {e}")
        results = [
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="获取画廊信息失败",
                input_message_content=InputTextMessageContent("请检查链接或稍后再试"),
            )
        ]
        await update.inline_query.answer(results, cache_time=0)
        return

    # 按钮
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🌐 跳转画廊", url=query),
                InlineKeyboardButton(
                    "🤖 在 Bot 中打开",
                    url=f"https://t.me/{context.application.bot.username}?start={gid}_{token}",
                ),
            ],
        ]
    )

    results = [
        InlineQueryResultPhoto(
            id=str(uuid.uuid4()),
            photo_url=thumb,
            thumbnail_url=thumb,
            title="画廊预览",
            caption=text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    ]

    await update.inline_query.answer(results)


async def handle_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    user_id = update.effective_user.id
    if user_id != int(query.data.split("|")[1]):
        await query.answer("是你的东西吗？你就点！")
        return
    await query.answer()

    api_key = get_user_api_key(user_id)
    if not api_key:
        await query.edit_message_text("请先私聊 Bot 登录后再签到")
        return

    try:
        data = await user_checkin(api_key)
    except ServiceAPIError as e:
        await query.edit_message_text(f"签到失败：{e.message}")
        return

    if data.get("success"):
        text = (
            f"✅ {data.get('message', '签到成功')}\n"
            f"💰 当前余额：{data.get('balance', 0)} GP"
        )
    else:
        text = f"📌 {data.get('message', '你今天已经签过到了~')}"
    await query.edit_message_text(text)


def register(app):
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(CallbackQueryHandler(handle_checkin, pattern=r"^checkin"))
