from helper.progress import progress_for_pyrogram, humanbytes
from pyrogram import Client, filters
from pyrogram.types import ForceReply
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from helper.database import *
import os, random, time
from PIL import Image
from datetime import timedelta
from helper.ffmpeg import take_screen_shot, fix_thumb, add_metadata
from helper.set import escape_invalid_curly_brackets
from config import *

# -------------------------------------------------
#  USERBOT (STRING_SESSION) – lazy initialization
# -------------------------------------------------
app = None  # userbot client


def init_user_client():
    """
    Create and return the userbot client AFTER the event loop exists.
    Only used when STRING_SESSION is set.
    """
    global app
    if app is None and STRING_SESSION:
        app = Client(
            "JishuBotz",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=STRING_SESSION
        )
    return app


# -------------------------------------------------
#  COMMON HELPERS
# -------------------------------------------------
def _ensure_dirs():
    if not os.path.isdir("downloads"):
        os.makedirs("downloads", exist_ok=True)
    if not os.path.isdir("Metadata"):
        os.makedirs("Metadata", exist_ok=True)


# -------------------------------------------------
#  CALLBACK HANDLERS (FOR MAIN BOT)
#  These are attached to *bot* instances created in bot.py
# -------------------------------------------------

@Client.on_callback_query(filters.regex("cancel"))
async def cancel(bot, update):
    """
    Cancel button: delete inline message and, if exists, the replied message.
    """
    try:
        if update.message.reply_to_message:
            await update.message.reply_to_message.delete()
        await update.message.delete()
    except Exception:
        # Ignore if already deleted / insufficient permissions
        pass


@Client.on_callback_query(filters.regex("rename"))
async def rename(bot, update):
    """
    Ask user for new filename using ForceReply.
    """
    date_fa = str(update.message.date)
    pattern = "%Y-%m-%d %H:%M:%S"
    date = int(time.mktime(time.strptime(date_fa, pattern)))
    chat_id = update.message.chat.id
    msg_id = update.message.reply_to_message_id

    await update.message.delete()
    await update.message.reply_text(
        "__Please Enter The New Filename...__\n\n**Note :** Extension Not Required",
        reply_to_message_id=msg_id,
        reply_markup=ForceReply(True)
    )
    dateupdate(chat_id, date)


@Client.on_callback_query(filters.regex("doc"))
async def doc(bot, update):
    """
    Handle document rename & upload via userbot to LOG_CHANNEL, then copy to user.
    """
    _ensure_dirs()
    userbot = init_user_client()

    new_name = update.message.text
    if ":-" not in new_name:
        return await update.message.edit("❌ Invalid format.\nUse: `OldName:-NewName`")

    new_filename = new_name.split(":-", 1)[1].strip()
    file_path = f"downloads/{new_filename}"

    message = update.message.reply_to_message
    file = message.document or message.video or message.audio
    if not file:
        return await update.message.edit("❌ No file found to rename.")

    ms = await update.message.edit("🚀 Try To Download... ⚡")

    used_ = find_one(update.from_user.id)
    used = used_["used_limit"]

    # optimistic usage update
    used_limit(update.from_user.id, used + file.file_size)
    c_time = time.time()

    try:
        path = await bot.download_media(
            message=file,
            progress=progress_for_pyrogram,
            progress_args=("🚀 Try To Downloading... ⚡", ms, c_time)
        )
    except Exception as e:
        used_limit(update.from_user.id, used)
        return await ms.edit(str(e))

    # metadata settings
    chat_conf = find(int(message.chat.id))
    _bool_metadata = chat_conf[2] if chat_conf and len(chat_conf) > 2 else False

    metadata_path = None
    if _bool_metadata:
        metadata = chat_conf[3]
        metadata_path = f"Metadata/{new_filename}"
        await add_metadata(path, metadata_path, metadata, ms)
    else:
        await ms.edit("🚀 Mode Changing... ⚡")

    # rename file
    os.replace(path, file_path)

    data = find(int(update.message.chat.id))
    c_caption = data[1] if data and len(data) > 1 else None
    thumb = data[0] if data else None

    if c_caption:
        doc_list = ["filename", "filesize"]
        new_tex = escape_invalid_curly_brackets(c_caption, doc_list)
        caption = new_tex.format(
            filename=new_filename,
            filesize=humanbytes(file.file_size)
        )
    else:
        caption = f"**{new_filename}**"

    ph_path = None
    if thumb:
        ph_path = await bot.download_media(thumb)
        img = Image.open(ph_path).convert("RGB")
        img = img.resize((320, 320))
        img.save(ph_path, "JPEG")
        c_time = time.time()

    await ms.edit("🚀 Try To Upload... ⚡")

    try:
        if userbot:
            # upload via userbot to LOG_CHANNEL
            upl = await userbot.send_document(
                LOG_CHANNEL,
                document=metadata_path or file_path,
                thumb=ph_path,
                caption=caption,
                progress=progress_for_pyrogram,
                progress_args=("🚀 Try To Uploading... ⚡", ms, c_time)
            )
            await bot.copy_message(
                chat_id=update.from_user.id,
                from_chat_id=upl.chat.id,
                message_id=upl.id
            )
            await ms.delete()
        else:
            # fallback: send directly from bot
            await bot.send_document(
                update.from_user.id,
                document=metadata_path or file_path,
                thumb=ph_path,
                caption=caption,
                progress=progress_for_pyrogram,
                progress_args=("🚀 Try To Uploading... ⚡", ms, c_time)
            )
            await ms.delete()
    except Exception as e:
        used_limit(update.from_user.id, used)
        await ms.edit(str(e))
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        if ph_path and os.path.exists(ph_path):
            os.remove(ph_path)


@Client.on_callback_query(filters.regex("vid"))
async def vid(bot, update):
    """
    Handle video rename & upload (similar to doc).
    """
    _ensure_dirs()
    userbot = init_user_client()

    new_name = update.message.text
    if ":-" not in new_name:
        return await update.message.edit("❌ Invalid format.\nUse: `OldName:-NewName`")

    new_filename = new_name.split(":-", 1)[1].strip()
    file_path = f"downloads/{new_filename}"

    message = update.message.reply_to_message
    file = message.video or message.document or message.audio
    if not file:
        return await update.message.edit("❌ No file found to rename.")

    ms = await update.message.edit("🚀 Try To Download... ⚡")
    used_ = find_one(update.from_user.id)
    used = used_["used_limit"]

    used_limit(update.from_user.id, used + file.file_size)
    c_time = time.time()

    try:
        path = await bot.download_media(
            message=file,
            progress=progress_for_pyrogram,
            progress_args=("🚀 Try To Downloading... ⚡", ms, c_time)
        )
    except Exception as e:
        used_limit(update.from_user.id, used)
        return await ms.edit(str(e))

    chat_conf = find(int(message.chat.id))
    _bool_metadata = chat_conf[2] if chat_conf and len(chat_conf) > 2 else False

    metadata_path = None
    if _bool_metadata:
        metadata = chat_conf[3]
        metadata_path = f"Metadata/{new_filename}"
        await add_metadata(path, metadata_path, metadata, ms)
    else:
        await ms.edit("🚀 Mode Changing... ⚡")

    os.replace(path, file_path)

    metadata_obj = extractMetadata(createParser(file_path))
    duration = metadata_obj.get("duration").seconds if metadata_obj and metadata_obj.has("duration") else 0

    data = find(int(update.message.chat.id))
    c_caption = data[1] if data and len(data) > 1 else None
    thumb = data[0] if data else None

    if c_caption:
        vid_list = ["filename", "filesize", "duration"]
        new_tex = escape_invalid_curly_brackets(c_caption, vid_list)
        caption = new_tex.format(
            filename=new_filename,
            filesize=humanbytes(file.file_size),
            duration=timedelta(seconds=duration)
        )
    else:
        caption = f"**{new_filename}**"

    ph_path = None
    if thumb:
        ph_path = await bot.download_media(thumb)
        img = Image.open(ph_path).convert("RGB")
        img = img.resize((320, 320))
        img.save(ph_path, "JPEG")
    else:
        try:
            ph_path_tmp = await take_screen_shot(
                file_path,
                os.path.dirname(os.path.abspath(file_path)),
                random.randint(0, max(0, duration - 1)) if duration > 0 else 0
            )
            _, _, ph_path = await fix_thumb(ph_path_tmp)
        except Exception:
            ph_path = None

    await ms.edit("🚀 Try To Upload... ⚡")

    try:
        if userbot:
            upl = await userbot.send_video(
                LOG_CHANNEL,
                video=metadata_path or file_path,
                thumb=ph_path,
                duration=duration,
                caption=caption,
                progress=progress_for_pyrogram,
                progress_args=("🚀 Try To Uploading... ⚡", ms, c_time)
            )
            await bot.copy_message(
                chat_id=update.from_user.id,
                from_chat_id=upl.chat.id,
                message_id=upl.id
            )
            await ms.delete()
        else:
            await bot.send_video(
                update.from_user.id,
                video=metadata_path or file_path,
                thumb=ph_path,
                duration=duration,
                caption=caption,
                progress=progress_for_pyrogram,
                progress_args=("🚀 Try To Uploading... ⚡", ms, c_time)
            )
            await ms.delete()
    except Exception as e:
        used_limit(update.from_user.id, used)
        await ms.edit(str(e))
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        if ph_path and os.path.exists(ph_path):
            os.remove(ph_path)


@Client.on_callback_query(filters.regex("aud"))
async def aud(bot, update):
    """
    Handle audio rename & upload directly from bot to user.
    """
    _ensure_dirs()

    new_name = update.message.text
    if ":-" not in new_name:
        return await update.message.edit("❌ Invalid format.\nUse: `OldName:-NewName`")

    new_filename = new_name.split(":-", 1)[1].strip()
    file_path = f"downloads/{new_filename}"

    message = update.message.reply_to_message
    file = message.audio or message.document or message.video
    if not file:
        return await update.message.edit("❌ No file found to rename.")

    ms = await update.message.edit("🚀 Try To Download... ⚡")
    used_ = find_one(update.from_user.id)
    used = used_["used_limit"]

    used_limit(update.from_user.id, used + file.file_size)
    c_time = time.time()

    try:
        path = await bot.download_media(
            message=file,
            progress=progress_for_pyrogram,
            progress_args=("🚀 Try To Downloading... ⚡", ms, c_time)
        )
    except Exception as e:
        used_limit(update.from_user.id, used)
        return await ms.edit(str(e))

    metadata_obj = extractMetadata(createParser(path))
    duration = metadata_obj.get("duration").seconds if metadata_obj and metadata_obj.has("duration") else 0

    os.replace(path, file_path)

    data = find(int(update.message.chat.id))
    c_caption = data[1] if data and len(data) > 1 else None
    thumb = data[0] if data else None

    if c_caption:
        aud_list = ["filename", "filesize", "duration"]
        new_tex = escape_invalid_curly_brackets(c_caption, aud_list)
        caption = new_tex.format(
            filename=new_filename,
            filesize=humanbytes(file.file_size),
            duration=timedelta(seconds=duration)
        )
    else:
        caption = f"**{new_filename}**"

    ph_path = None
    if thumb:
        ph_path = await bot.download_media(thumb)
        img = Image.open(ph_path).convert("RGB")
        img = img.resize((320, 320))
        img.save(ph_path, "JPEG")

    await ms.edit("🚀 Try To Upload... ⚡")

    try:
        await bot.send_audio(
            update.from_user.id,
            audio=file_path,
            caption=caption,
            thumb=ph_path,
            duration=duration,
            progress=progress_for_pyrogram,
            progress_args=("🚀 Try To Uploading... ⚡", ms, c_time)
        )
        await ms.delete()
    except Exception as e:
        used_limit(update.from_user.id, used)
        await ms.edit(str(e))
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        if ph_path and os.path.exists(ph_path):
            os.remove(ph_path)
