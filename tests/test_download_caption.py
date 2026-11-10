import html
import sys
import unittest
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, patch

from telegram import (
    CallbackQuery,
    Chat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    MessageEntity,
    Update,
    User,
)

# No production configuration, credentials, or network calls are needed.
config = ModuleType("config.config")
config.cfg = {"EH_COOKIE": ""}
with patch.dict(sys.modules, {"config.config": config}):
    from handlers import resolver


def utf16_length(text):
    return len(text.encode("utf-16-le")) // 2


class DownloadCaptionTests(unittest.IsolatedAsyncioTestCase):
    def make_update(self, status="", force=False):
        title = "📌 主标题：Example < > & title\n"
        details = "📙 副标题：A & B\n👤 上传者：Uploader"
        caption = title + details
        entities = [
            MessageEntity(
                MessageEntity.EXPANDABLE_BLOCKQUOTE,
                utf16_length(title),
                utf16_length(details),
            ),
            MessageEntity(
                MessageEntity.TEXT_LINK,
                utf16_length(caption.removesuffix("Uploader")),
                utf16_length("Uploader"),
                url="https://example.com/uploader",
            ),
        ]
        self.bot = SimpleNamespace(
            answer_callback_query=AsyncMock(return_value=True),
            edit_message_caption=AsyncMock(return_value=True),
        )
        user = User(123, "Test", False)
        message = Message(
            message_id=1,
            date=datetime.now(timezone.utc),
            chat=Chat(123, "private"),
            caption=caption + ("\n\n" + status if status else ""),
            caption_entities=entities,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Download", callback_data="download|123|abcdef1234")]]
            ),
        )
        message.set_bot(self.bot)
        query = CallbackQuery(
            "query", user, "chat", message=message,
            data="download|123|abcdef1234" + ("|force" if force else ""),
        )
        query.set_bot(self.bot)
        self.base_html = message.caption_html
        if status:
            self.base_html = self.base_html.removesuffix("\n\n" + html.escape(status))
        return Update(1, callback_query=query)

    async def run_download(self, update, result=None, error=None):
        api = AsyncMock(return_value=result, side_effect=error)
        with (
            patch.object(resolver, "get_user_api_key", return_value="test-api-key"),
            patch.object(resolver, "parse_gallery", api),
        ):
            await resolver.download(update, None)
        self.bot.answer_callback_query.assert_awaited_once()
        self.assertEqual(self.bot.edit_message_caption.await_count, 2)
        edits = [call.kwargs for call in self.bot.edit_message_caption.await_args_list]
        for edit in edits:
            self.assertEqual(edit["parse_mode"], "HTML")
        self.assertEqual(
            edits[0]["caption"],
            self.base_html + "\n\n⏳ 正在获取下载链接，请稍等...",
        )
        return edits[-1], api

    async def test_preserves_escaped_title_links_and_expandable_quote(self):
        update = self.make_update()
        final, api = await self.run_download(
            update, result={"archive_url": "https://example.com/archive.zip"}
        )
        self.assertIn("&lt; &gt; &amp;", final["caption"])
        self.assertIn("<blockquote expandable>", final["caption"])
        self.assertIn('<a href="https://example.com/uploader">', final["caption"])
        self.assertEqual(final["caption"], self.base_html + "\n\n✅ 下载链接获取成功")
        api.assert_awaited_once_with("test-api-key", "123", "abcdef1234", False)

    async def test_force_retry_replaces_previous_status(self):
        for status in (
            "✅ 下载链接获取成功",
            "✅ 下载链接获取成功（缓存）",
            "❌ 下载链接获取失败：upstream <html> & error\nsecond line",
            "⏳ 正在获取下载链接，请稍等...",
        ):
            with self.subTest(status=status):
                update = self.make_update(status, force=True)
                final, api = await self.run_download(
                    update,
                    result={"archive_url": "https://example.com/archive.zip", "cached": True},
                )
                self.assertEqual(
                    final["caption"], self.base_html + "\n\n✅ 下载链接获取成功（缓存）"
                )
                api.assert_awaited_once_with("test-api-key", "123", "abcdef1234", True)

    async def test_service_errors_are_escaped(self):
        error_text = 'upstream <html> & "error"\nretry later'
        for error in (resolver.ServiceAPIError(502, error_text), RuntimeError(error_text)):
            with self.subTest(error=type(error).__name__):
                final, _ = await self.run_download(self.make_update(), error=error)
                self.assertEqual(
                    final["caption"],
                    self.base_html + "\n\n❌ 下载链接获取失败：" + html.escape(error_text),
                )

    async def test_error_in_service_response_is_escaped(self):
        final, _ = await self.run_download(
            self.make_update(), result={"error": "upstream <bad> & response"}
        )
        self.assertEqual(
            final["caption"],
            self.base_html + "\n\n❌ 下载链接获取失败：upstream &lt;bad&gt; &amp; response",
        )

    async def test_missing_archive_url_shows_default_error(self):
        final, _ = await self.run_download(self.make_update(), result={})
        self.assertEqual(
            final["caption"], self.base_html + "\n\n❌ 下载链接获取失败：服务端未返回下载链接"
        )


if __name__ == "__main__":
    unittest.main()
