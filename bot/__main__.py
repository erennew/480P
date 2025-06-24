import os
import asyncio
import time
from datetime import datetime as dt
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton , Message
from pyrogram.errors import FloodWait, RPCError
from bot import (
    APP_ID,
    API_HASH,
    TG_BOT_TOKEN,
    USER_SESSION,
    DOWNLOAD_LOCATION,
    BOT_USERNAME,
    LOGGER,
    data,
    app,
    crf,
    resolution,
    audio_b,
    preset,
    codec,
    watermark,
    AUTH_USERS
)
from bot.commands import Command
from bot.helper_funcs.utils import add_task, sysinfo, TimeFormatter
import pyrogram.utils

pyrogram.utils.MIN_CHAT_ID = -999999999999
pyrogram.utils.MIN_CHANNEL_ID = -100999999999999

# Default settings
crf.append("23")                # Balanced CRF for 480p and medium preset
codec.append("libx265")         # Efficient and modern codec
resolution.append("854x480")    # Standard 480p resolution (16:9)
preset.append("fast")         # Medium = balanced speed vs quality
audio_b.append("64k")           # Lower audio bitrate to save size


uptime = dt.now()
user_client = None
MAX_WORKERS = 2  # Number of parallel tasks

def safe_extract_args(text: str) -> str:
    try:
        return text.split(" ", maxsplit=1)[1]
    except IndexError:
        return ""

def ts(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = (
        ((str(days) + "d, ") if days else "") +
        ((str(hours) + "h, ") if hours else "") +
        ((str(minutes) + "m, ") if minutes else "") +
        ((str(seconds) + "s, ") if seconds else "") +
        ((str(milliseconds) + "ms, ") if milliseconds else "")
    )
    return tmp[:-2]

async def is_admin(message):
    if message.from_user.id in AUTH_USERS:
        return True
    await message.reply("🚫 You are not authorized to use this command.")
    return False
if __name__ == "__main__" :
    # create download directory, if not exist
    if not os.path.isdir(DOWNLOAD_LOCATION):
        os.makedirs(DOWNLOAD_LOCATION)
        
# ===================== COMMAND HANDLERS =====================

    @app.on_message(filters.command([Command.START, f"{Command.START}@{BOT_USERNAME}"]))
    async def start_command(_, message):
        try:
            await message.reply_text(
                f"🤖 **Welcome to {BOT_USERNAME}**\n\n"
                "I can compress videos and handle file conversions.\n\n"
                f"Use /{Command.HELP} to see available commands."
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await start_command(_, message)
        except Exception as e:
            LOGGER.error(f"Start error: {e}")

    @app.on_message(filters.command([Command.HELP, f"{Command.HELP}@{BOT_USERNAME}"]))
    async def help_command(_, message):
        help_text = (
            "📝 **Available Commands:**\n\n"
            f"/{Command.START} - Start the bot\n"
            f"/{Command.HELP} - Show this help\n"
            f"/{Command.COMPRESS} - Compress replied video\n"
            f"/{Command.CANCEL} - Cancel current operation\n"
            f"/{Command.STATUS} - Show current status\n"
            f"/{Command.EXEC} - Execute shell command (admin)\n"
            f"/{Command.UPLOAD_LOG_FILE} - Get log file\n\n"
            "**Settings Commands:**\n"
            "/crf [value] - Set CRF value\n"
            "/resolution [value] - Set resolution\n"
            "/preset [value] - Set preset\n"
            "/codec [value] - Set codec\n"
            "/audio [value] - Set audio bitrate\n"
            "/watermark [text] - Set watermark\n"
            "/settings - Show current settings"
        )
        try:
            await message.reply_text(help_text)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await help_command(_, message)

    @app.on_message(filters.command(["crf", f"crf@{BOT_USERNAME}"]))
    async def change_crf(_, message):
        try:
            val = safe_extract_args(message.text)
            if not val:
                return await message.reply_text("Please provide CRF value.\nExample: /crf 23")
            crf[0] = val
            await message.reply_text(f"✅ CRF set to: {val}")
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await change_crf(_, message)

    @app.on_message(filters.command(["resolution", f"resolution@{BOT_USERNAME}"]))
    async def change_resolution(_, message):
        try:
            val = safe_extract_args(message.text)
            if not val:
                return await message.reply_text("Provide resolution. Ex: /resolution 1920x1080")
            resolution[0] = val
            await message.reply_text(f"✅ Resolution set to: {val}")
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await change_resolution(_, message)

    @app.on_message(filters.command(["preset", f"preset@{BOT_USERNAME}"]))
    async def change_preset(_, message):
        try:
            val = safe_extract_args(message.text)
            if not val:
                return await message.reply_text("Provide preset. Ex: /preset fast")
            preset[0] = val
            await message.reply_text(f"✅ Preset set to: {val}")
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await change_preset(_, message)

    @app.on_message(filters.command(["codec", f"codec@{BOT_USERNAME}"]))
    async def change_codec(_, message):
        try:
            val = safe_extract_args(message.text)
            if not val:
                return await message.reply_text("Provide codec. Ex: /codec libx265")
            codec[0] = val
            await message.reply_text(f"✅ Codec set to: {val}")
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await change_codec(_, message)

    @app.on_message(filters.command(["audio", f"audio@{BOT_USERNAME}"]))
    async def change_audio(_, message):
        try:
            val = safe_extract_args(message.text)
            if not val:
                return await message.reply_text("Provide audio bitrate. Ex: /audio 128k")
            audio_b[0] = val
            await message.reply_text(f"✅ Audio bitrate set to: {val}")
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await change_audio(_, message)

    @app.on_message(filters.command(["watermark", f"watermark@{BOT_USERNAME}"]))
    async def change_watermark(_, message):
        try:
            val = safe_extract_args(message.text)
            if not val:
                return await message.reply_text("Ex: /watermark Encoded by MyBot")
            wm = (
                f"-vf drawtext=fontfile=font.ttf:fontsize=25:fontcolor=white:bordercolor=black@0.50:"
                f"x=w-tw-10:y=10:box=1:boxcolor=black@0.5:boxborderw=6:text='{val}'"
            )
            watermark[0] = wm
            await message.reply_text(f"✅ Watermark set to: {val}")
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await change_watermark(_, message)

    @app.on_message(filters.command(["settings", f"settings@{BOT_USERNAME}"]))
    async def current_settings(_, message):
        try:
            wm_text = watermark[0].split("text=")[-1].strip("'") if watermark else "None"
            await message.reply_text(
                f"⚙️ <b>Current Settings:</b>\n\n"
                f"<code>Codec: {codec[0]}\n"
                f"CRF: {crf[0]}\n"
                f"Resolution: {resolution[0]}\n"
                f"Preset: {preset[0]}\n"
                f"Audio Bitrate: {audio_b[0]}\n"
                f"Watermark: {wm_text}</code>"
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await current_settings(_, message)


    @app.on_message(filters.command(["compress", f"compress@{BOT_USERNAME}"]) & filters.reply)
    async def compress_command(_, message: Message):
        try:
            # Only accept replies to video or document
            reply = message.reply_to_message
            if not reply or not (reply.video or reply.document):
                return await message.reply_text("❌ Please reply to a video or document to compress.")

            await message.reply_text("⏳ Added to compression queue...")
            data.append(reply)

            # If it's the only item in queue, start processing
            if len(data) == 1:
                await add_task(reply)

        except FloodWait as e:
            await asyncio.sleep(e.value)
            await compress_command(_, message)

    @app.on_message(filters.command([Command.CANCEL, f"{Command.CANCEL}@{BOT_USERNAME}"]))
    async def cancel_command(_, message):
        try:
            if not data:
                return await message.reply_text("No active tasks to cancel.")
            data.clear()
            await message.reply_text("✅ Cancelled all pending tasks.")
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await cancel_command(_, message)

    @app.on_message(filters.command([Command.STATUS, f"{Command.STATUS}@{BOT_USERNAME}"]))
    async def status_command(_, message):
        try:
            await message.reply_text(
                f"📊 <b>Current Status:</b>\n\n"
                f"<code>Queue size: {len(data)}\n"
                f"Active workers: {len(data) if len(data) < MAX_WORKERS else MAX_WORKERS}/{MAX_WORKERS}</code>"
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await status_command(_, message)

    @app.on_message(filters.command([Command.EXEC, f"{Command.EXEC}@{BOT_USERNAME}"]))
    async def exec_command(_, message):
        if not await is_admin(message):
            return
        
        cmd = safe_extract_args(message.text)
        if not cmd:
            return await message.reply_text("Please provide a command to execute.")
        
        try:
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            output = f"<b>Output:</b>\n<code>{stdout.decode().strip()}</code>"
            if stderr:
                output += f"\n\n<b>Error:</b>\n<code>{stderr.decode().strip()}</code>"
            await message.reply_text(output)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await exec_command(_, message)
        except Exception as e:
            await message.reply_text(f"Error: {str(e)}")

    @app.on_message(filters.command([Command.UPLOAD_LOG_FILE, f"{Command.UPLOAD_LOG_FILE}@{BOT_USERNAME}"]))
    async def log_command(_, message):
        try:
            if not os.path.exists("log.txt"):
                return await message.reply_text("No log file found.")
            await message.reply_document("log.txt", caption="📄 Bot log file")
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await log_command(_, message)

    # ===================== CLIENT MANAGEMENT =====================

    async def initialize_user_client():
        global user_client
        if USER_SESSION:
            user_client = Client(
                name="user_session",
                session_string=USER_SESSION,
                api_id=APP_ID,
                api_hash=API_HASH,
                in_memory=True,
                sleep_threshold=30,
                max_concurrent_transmissions=1
            )
            await user_client.start()
            LOGGER.info("User Client started successfully")

    async def main():
        # Create download location if not exists
        os.makedirs(DOWNLOAD_LOCATION, exist_ok=True)
        
        # Initialize user client if available
        if USER_SESSION:
            await initialize_user_client()
        
        # Start the bot with optimized settings
        await app.start()
        me = await app.get_me()
        LOGGER.info(f"Bot started as @{me.username}")
        
        # Keep the bot running
        while True:
            await asyncio.sleep(3600)

    app.run()
