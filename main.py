from loguru import logger
from telegram.ext import Application

from config.config import cfg
from handlers import BOT_COMMANDS, register_all_handlers
from utils.resolve import fetch_tag_map

logger.add("log.log", encoding="utf-8")


async def post_init(app):
    await app.bot.set_my_commands(BOT_COMMANDS)


telegram_app = (
    Application.builder().token(cfg["BOT_TOKEN"]).post_init(post_init).build()
)

register_all_handlers(telegram_app)
telegram_app.job_queue.run_repeating(fetch_tag_map, interval=86400, first=5)


if __name__ == "__main__":
    telegram_app.run_polling()
