from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes

from utils.service_api import get_login_url


def build_login_markup(bot_username: str, bot_id: int) -> InlineKeyboardMarkup:
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


async def reply_need_login(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
) -> None:
    await update.effective_message.reply_text(
        text,
        reply_markup=build_login_markup(
            context.application.bot.username, context.application.bot.id
        ),
    )
