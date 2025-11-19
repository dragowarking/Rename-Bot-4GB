import asyncio
from pyrogram import Client, idle
from plugins.cb_data import app as Client2
from config import *
import pyromod
import pyrogram.utils

pyrogram.utils.MIN_CHAT_ID = -999999999999
pyrogram.utils.MIN_CHANNEL_ID = -100999999999999


bot = Client(
    "Renamer",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH,
    plugins=dict(root='plugins')
)


async def main():
    if STRING_SESSION:
        apps = [Client2, bot]
        for app in apps:
            await app.start()
        await idle()
        for app in apps:
            await app.stop()

    else:
        await bot.start()
        await idle()
        await bot.stop()


asyncio.run(main())
