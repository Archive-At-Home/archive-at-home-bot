import uuid

from loguru import logger
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InlineQueryResultPhoto,
    InlineQueryResultsButton,
    InputMediaPhoto,
    InputTextMessageContent,
    Update,
)
from telegram.ext import ChosenInlineResultHandler, ContextTypes, InlineQueryHandler

from utils.resolve import (
    GALLERY_URL_RE,
    SAMPLE_URL_RE,
    get_gallery_info,
    resolve_sample_to_gallery,
)


async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query.strip()

    button = InlineQueryResultsButton(text="到Bot查看更多信息", start_parameter="start")

    # 没输入时提示
    if not query:
        results = [
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="请输入 eh/ex 链接以获取预览",
                input_message_content=InputTextMessageContent("请输入链接"),
            ),
        ]

        await update.inline_query.answer(results, button=button)
        return

    gallery_match = GALLERY_URL_RE.fullmatch(query.rstrip("/"))
    sample_match = SAMPLE_URL_RE.fullmatch(query.rstrip("/"))
    if not gallery_match and not sample_match:
        results = [
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="链接格式错误",
                input_message_content=InputTextMessageContent(
                    "请输入合法的 g/s 页面链接"
                ),
            )
        ]
        await update.inline_query.answer(results)
        return

    sample_thumb = None
    if gallery_match:
        gid, token = gallery_match.group(1), gallery_match.group(2)
        gallery_url = query
    else:
        try:
            gallery_url, gid, token, sample_thumb = await resolve_sample_to_gallery(
                query
            )
        except Exception as e:
            logger.warning(f"Inline 模式解析样本页失败: {query}，错误: {e}")
            results = [
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="获取画廊信息失败",
                    input_message_content=InputTextMessageContent(
                        "请检查链接或稍后再试"
                    ),
                )
            ]
            await update.inline_query.answer(results, cache_time=0)
            return

    logger.info(f"解析画廊 {gallery_url}")
    try:
        text, is_h, api_thumb = await get_gallery_info(gid, token)
    except Exception as e:
        logger.warning(f"Inline 模式解析画廊失败: {gallery_url}，错误: {e}")
        results = [
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="获取画廊信息失败",
                input_message_content=InputTextMessageContent("请检查链接或稍后再试"),
            )
        ]
        await update.inline_query.answer(results, cache_time=0)
        return

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🌐 跳转画廊", url=gallery_url),
                InlineKeyboardButton(
                    "🤖 在 Bot 中打开",
                    url=f"https://t.me/{context.application.bot.username}?start={gid}_{token}",
                ),
            ],
        ]
    )

    photo_url = sample_thumb or api_thumb
    result_id = str(uuid.uuid4())

    if is_h:
        context.bot_data.setdefault("__inline_spoiler", {})[result_id] = {
            "photo_url": photo_url,
            "caption": text,
            "reply_markup": keyboard,
        }

    results = [
        InlineQueryResultPhoto(
            id=result_id,
            photo_url=photo_url,
            thumbnail_url=photo_url,
            title="画廊预览",
            caption=text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    ]

    await update.inline_query.answer(results, cache_time=0)


async def on_chosen_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chosen = update.chosen_inline_result
    stored = context.bot_data.get("__inline_spoiler", {})
    data = stored.pop(chosen.result_id, None)
    if not data:
        return

    await context.bot.edit_message_media(
        inline_message_id=chosen.inline_message_id,
        media=InputMediaPhoto(
            media=data["photo_url"],
            caption=data["caption"],
            parse_mode="HTML",
            has_spoiler=True,
        ),
        reply_markup=data["reply_markup"],
    )


def register(app):
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(ChosenInlineResultHandler(on_chosen_result))
