import asyncio
from pyrogram import Client, idle
from plugins.cb_data import init_user_client
from config import *
import pyromod  # keep if your plugins use pyromod
import pyrogram.utils

# Optional: widen ID ranges if your bot uses very small IDs
pyrogram.utils.MIN_CHAT_ID = -999999999999
pyrogram.utils.MIN_CHANNEL_ID = -100999999999999

bot = Client(
    "Renamer",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH,
    plugins=dict(root="plugins")
)


async def main():
    # Start main bot
    await bot.start()
    print("Main bot started.")

    # Start userbot if STRING_SESSION is provided
    userbot = None
    if STRING_SESSION:
        userbot = init_user_client()
        if userbot is not None:
            await userbot.start()
            print("Userbot started with STRING_SESSION.")

    print("Bot running. Waiting for events...")
    await idle()

    # Graceful shutdown
    if STRING_SESSION and userbot is not None:
        await userbot.stop()
        print("Userbot stopped.")

    await bot.stop()
    print("Main bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
