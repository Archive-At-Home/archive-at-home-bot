from telegram import BotCommand

from . import inline_query, resolver, user_action

BOT_COMMANDS = [
    BotCommand("start", "开始使用"),
    BotCommand("login", "登录账号"),
    BotCommand("myinfo", "我的信息"),
    BotCommand("help", "帮助"),
]


def register_all_handlers(app):
    user_action.register(app)
    resolver.register(app)
    inline_query.register(app)
