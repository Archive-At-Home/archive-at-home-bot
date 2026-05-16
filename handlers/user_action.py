from loguru import logger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from handlers.resolver import reply_gallery_info
from utils.service_api import (
    ServiceAPIError,
    get_login_url,
    get_me,
    get_user_api_key,
    reset_api_key,
    set_user_api_key,
    user_checkin,
)


def _login_keyboard(bot_username: str, bot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔑 Mini App 登录（推荐）",
                    web_app=WebAppInfo(url=get_login_url(bot_username, bot_id)),
                )
            ],
            [
                InlineKeyboardButton(
                    "🔗 网页登录",
                    url=get_login_url(bot_username),
                ),
            ],
        ]
    )


async def _reply_need_login(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
) -> None:
    await update.effective_message.reply_text(
        text,
        reply_markup=_login_keyboard(
            context.application.bot.username, context.application.bot.id
        ),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /start 登录绑定及跳转解析命令"""
    if update.effective_chat.type in [
        "group",
        "supergroup",
    ] and not update.effective_message.text.startswith(
        f"/start@{context.application.bot.username}"
    ):
        return

    tg_user = update.effective_message.from_user

    if context.args:
        payload = context.args[0]
        if payload.startswith("sk-"):
            set_user_api_key(tg_user.id, payload)
            await update.effective_message.reply_text(
                "✅ 登录成功，账号已绑定到当前 Telegram 会话。"
            )
            logger.info(f"{tg_user.full_name}（{tg_user.id}）完成登录绑定")
            return

        if "_" in payload:
            gid, token = payload.split("_", 1)
            await reply_gallery_info(
                update, context, f"https://e-hentai.org/g/{gid}/{token}/", gid, token
            )
            return

    if update.effective_chat.type == "private" and not get_user_api_key(tg_user.id):
        await _reply_need_login(
            update,
            context,
            "请先点击下方按钮完成登录授权，随后即可按原方式发送画廊链接获取下载。",
        )
        return

    await update.effective_message.reply_text("✅ 已就绪，发送画廊链接即可解析。")


async def login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply_need_login(update, context, "点击下方按钮完成 Telegram 授权登录：")


async def handle_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理每日签到命令"""
    user_id = update.effective_message.from_user.id
    api_key = get_user_api_key(user_id)
    if not api_key:
        await _reply_need_login(update, context, "请先登录后再签到。")
        return

    try:
        data = await user_checkin(api_key)
    except ServiceAPIError as e:
        if e.status_code == 401:
            await update.effective_message.reply_text(
                "登录已失效，请重新使用 /login 授权。"
            )
            return
        await update.effective_message.reply_text(f"❌ 签到失败：{e.message}")
        return

    if data.get("success"):
        await update.effective_message.reply_text(
            f"✅ {data.get('message', '签到成功')}\n"
            f"💰 获得：{data.get('reward', 0)} GP\n"
            f"📊 当前余额：{data.get('balance', 0)} GP"
        )
    else:
        await update.effective_message.reply_text(
            f"📌 {data.get('message', '你今天已经签过到了~')}"
        )


async def myinfo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """查看我的账户信息"""
    user_id = update.effective_message.from_user.id
    api_key = get_user_api_key(user_id)
    if not api_key:
        await _reply_need_login(update, context, "请先登录后再查看账户信息。")
        return

    try:
        data = await get_me(api_key)
        profile = data.get("user", {})
    except ServiceAPIError as e:
        if e.status_code == 401:
            await update.effective_message.reply_text(
                "登录已失效，请重新使用 /login 授权。"
            )
            return
        await update.effective_message.reply_text(f"❌ 获取账户信息失败：{e.message}")
        return

    text = (
        f"🆔 用户 ID：{profile.get('id', '—')}\n"
        f"👤 昵称：{profile.get('nickname', '—')}\n"
        f"📮 邮箱：{profile.get('email') or '—'}\n"
        f"🔐 登录方式：{profile.get('provider', '—')}\n"
        f"📦 账号状态：{profile.get('status', '—')}\n"
        f"💰 剩余 GP：{data.get('balance', 0)}"
    )

    if update.effective_chat.type == "private":
        text += f"\nAPI Key：<code>{api_key}</code>"
        keyboard = [
            [InlineKeyboardButton("重新登录", callback_data="open_login")],
            [InlineKeyboardButton("重置 API Key", callback_data="reset_apikey")],
        ]
        await update.effective_message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
    else:
        await update.effective_message.reply_text(text)


async def reset_apikey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    current_key = get_user_api_key(user_id)
    if not current_key:
        await query.edit_message_text("请先使用 /login 授权后再重置 API Key")
        return

    try:
        data = await reset_api_key(current_key)
        new_key = data.get("api_key") or data.get("user", {}).get("api_key")
    except ServiceAPIError as e:
        await query.edit_message_text(f"重置失败：{e.message}")
        return

    if not new_key:
        await query.edit_message_text("重置失败：服务端未返回新 API Key")
        return

    set_user_api_key(user_id, new_key)

    await query.edit_message_text(
        f"重置成功\nAPI Key：<code>{new_key}</code>", parse_mode="HTML"
    )


async def open_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "点击下方按钮完成登录：",
        reply_markup=_login_keyboard(
            context.application.bot.username, context.application.bot.id
        ),
    )


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("点击这里查看帮助内容：\nhttps://t.me/EH_ArBot/64")


def register(app):
    """注册命令处理器"""
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("checkin", handle_checkin))
    app.add_handler(CommandHandler("myinfo", myinfo))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CallbackQueryHandler(reset_apikey, pattern=r"^reset_apikey$"))
    app.add_handler(CallbackQueryHandler(open_login, pattern=r"^open_login$"))
