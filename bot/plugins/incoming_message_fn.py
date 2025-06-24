# incoming_message.py
import datetime
import logging
import os
import time
import asyncio
import json
import shutil
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.localisation import Localisation
from bot import (
    DOWNLOAD_LOCATION,
    AUTH_USERS,
    LOG_CHANNEL,
    USER_SESSION,
    APP_ID,
    API_HASH,
    data,
    app
)
from bot.helper_funcs.ffmpeg import (
    convert_video,
    media_info,
    take_screen_shot
)
from bot.helper_funcs.display_progress import (
    progress_for_pyrogram,
    TimeFormatter,
    humanbytes
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
LOGGER = logging.getLogger(__name__)

# Initialize user client for large uploads
user_client = None
if USER_SESSION:
    try:
        user_client = Client(
            name="user_session",
            session_string=USER_SESSION,
            api_id=APP_ID,
            api_hash=API_HASH,
            in_memory=True
        )
    except Exception as e:
        LOGGER.error(f"Failed to initialize user client: {e}")

# Download default thumbnail
try:
    if not os.path.exists("thumb.jpg"):
        os.system("wget https://telegra.ph/file/0e369e097843b0dc4b771.jpg -O thumb.jpg")
except Exception as e:
    LOGGER.error(f"Failed to download thumbnail: {e}")
    open("thumb.jpg", "wb").write(b"DEFAULT_THUMBNAIL_BYTES")

async def cleanup_files(*files):
    """Clean up multiple files safely"""
    for file in files:
        try:
            if file and os.path.exists(file) and file not in ["thumb.jpg"]:
                if os.path.isdir(file):
                    shutil.rmtree(file)
                else:
                    os.remove(file)
        except Exception as e:
            LOGGER.error(f"Failed to delete {file}: {e}")

async def handle_failure(error_msg, sent_message=None, log_channel=None):
    """Centralized error handling"""
    LOGGER.error(error_msg)
    try:
        if sent_message:
            await sent_message.edit_text(f"❌ Error: {error_msg[:1000]}")
    except Exception as e:
        LOGGER.error(f"Failed to send error message: {e}")
    
    if log_channel:
        try:
            await app.send_message(
                chat_id=log_channel,
                text=f"<blockquote>❌ Error:\n<code>{error_msg[:4000]}</code></blockquote>"
            )
        except Exception as e:
            LOGGER.error(f"Failed to log error: {e}")

async def incoming_start_message_f(bot, update):
    """Handle /start command"""
    try:
        await bot.send_message(
            chat_id=update.chat.id,
            text=Localisation.START_TEXT,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton('👨‍💻 Owner 👨‍💻', url='https://t.me/Krishna99887722')]]
            ),
            reply_to_message_id=update.id,
        )
    except Exception as e:
        LOGGER.error(f"Start command failed: {e}")

async def incoming_compress_message_f(update):
    """Handle complete compression workflow"""
    d_start = time.time()
    status_file = os.path.join(DOWNLOAD_LOCATION, "status.json")
    video_file = compressed_file = thumb_file = None
    
    try:
        # Initialize status and send start message
        sent_message = await app.send_message(
            chat_id=update.chat.id,
            text=Localisation.DOWNLOAD_START,
            reply_to_message_id=update.id
        )

        with open(status_file, 'w') as f:
            json.dump({'running': True, 'message': sent_message.id}, f)

        # Create download directory if it doesn't exist
        os.makedirs(DOWNLOAD_LOCATION, exist_ok=True)

        # Download the video file
        try:
            video_file = await app.download_media(
                message=update,
                progress=progress_for_pyrogram,
                progress_args=(app, Localisation.DOWNLOAD_START, sent_message, d_start)
            )
            
            if not video_file or not os.path.exists(video_file):
                await handle_failure("Download failed - file not saved", sent_message, LOG_CHANNEL)
                return
                
            LOGGER.info(f"Downloaded file to: {video_file}")
        except Exception as e:
            await handle_failure(f"Download failed: {str(e)}", sent_message, LOG_CHANNEL)
            return

        # Get media info
        try:
            duration, bitrate = await media_info(video_file)
            if not duration:
                await handle_failure("Could not get video duration", sent_message, LOG_CHANNEL)
                return
                
            LOGGER.info(f"Media info - Duration: {duration}, Bitrate: {bitrate}")
        except Exception as e:
            await handle_failure(f"Media info error: {str(e)}", sent_message, LOG_CHANNEL)
            return

        # Create thumbnail
        try:
            thumb_file = await take_screen_shot(
                video_file,
                os.path.dirname(video_file),
                duration / 2
            )
            if not thumb_file or not os.path.exists(thumb_file):
                thumb_file = "thumb.jpg"
                LOGGER.warning("Using default thumbnail")
            else:
                LOGGER.info(f"Created thumbnail: {thumb_file}")
        except Exception as e:
            LOGGER.error(f"Thumbnail error: {e}")
            thumb_file = "thumb.jpg"

        # Compress video
        try:
            compressed_file = await convert_video(
                video_file,
                DOWNLOAD_LOCATION,
                duration,
                app,
                sent_message,
                None
            )
            
            if not compressed_file or not os.path.exists(compressed_file):
                await handle_failure("Compression failed - no output file", sent_message, LOG_CHANNEL)
                return
                
            if os.path.getsize(compressed_file) == 0:
                await handle_failure("Compression failed - empty output file", sent_message, LOG_CHANNEL)
                return
                
            LOGGER.info(f"Successfully compressed file: {compressed_file}")
        except Exception as e:
            await handle_failure(f"Compression error: {str(e)}", sent_message, LOG_CHANNEL)
            return

        # Upload the file
        try:
            file_size = os.path.getsize(compressed_file)
            use_user_client = file_size > 2 * 1024 * 1024 * 1024  # 2GB threshold
            upload_client = user_client if (use_user_client and user_client) else app

            await sent_message.edit_text(Localisation.UPLOAD_START)
            u_start = time.time()

            caption = Localisation.COMPRESS_SUCCESS.replace(
                '{}', TimeFormatter((time.time() - d_start)*1000), 1
            ).replace(
                '{}', TimeFormatter((time.time() - time.time())*1000), 1
            )

            # Start the user client if needed
            if upload_client == user_client and not user_client.is_connected:
                await user_client.start()
                LOGGER.info("Started user client for large upload")

            upload = await upload_client.send_document(
                chat_id=update.chat.id,
                document=compressed_file,
                caption=caption,
                force_document=True,
                thumb=thumb_file,
                reply_to_message_id=update.id,
                progress=progress_for_pyrogram,
                progress_args=(upload_client, Localisation.UPLOAD_START, sent_message, u_start)
            )

            if not upload:
                await handle_failure("Upload failed - no response", sent_message, LOG_CHANNEL)
                return

            # Final success message
            uploaded_time = TimeFormatter((time.time() - u_start)*1000)
            try:
                await upload.edit_caption(
                    caption=upload.caption.replace('{}', uploaded_time)
                )
            except Exception as e:
                if "MESSAGE_NOT_MODIFIED" not in str(e):
                    LOGGER.error(f"Failed to update caption: {e}")

            await sent_message.delete()
            await app.send_message(
                LOG_CHANNEL,
                f"<blockquote>✅ Task completed successfully!\n"
                f"Size: {humanbytes(file_size)}\n"
                f"Time: {TimeFormatter((time.time() - d_start)*1000)}</blockquote>"
            )

        except Exception as e:
            await handle_failure(f"Upload error: {str(e)}", sent_message, LOG_CHANNEL)
            return

    except Exception as e:
        await handle_failure(f"Unexpected error: {str(e)}", None, LOG_CHANNEL)
    finally:
        await cleanup_files(video_file, compressed_file)
        try:
            if thumb_file and thumb_file != "thumb.jpg":
                await cleanup_files(thumb_file)
            if os.path.exists(status_file):
                os.remove(status_file)
        except Exception as e:
            LOGGER.error(f"Cleanup error: {e}")
        finally:
            if user_client and user_client.is_connected:
                await user_client.stop()

async def incoming_cancel_message_f(bot, update):
    """Handle /cancel command"""
    if update.from_user.id not in AUTH_USERS:
        try:
            await update.message.delete()
        except Exception as e:
            LOGGER.error(f"Failed to delete message: {e}")
        return

    status_file = os.path.join(DOWNLOAD_LOCATION, "status.json")
    if os.path.exists(status_file):
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("Yes 🚫", callback_data="fuckingdo"),
            InlineKeyboardButton("No 🤗", callback_data="fuckoff")
        ]])
        await update.reply_text(
            "Are you sure? This will stop the compression!",
            reply_markup=reply_markup,
            quote=True
        )
    else:
        await bot.send_message(
            chat_id=update.chat.id,
            text="No active compression exists",
            reply_to_message_id=update.id
        )
