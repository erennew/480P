import asyncio
import io
import logging
import os
import shutil
import sys
import time
import traceback
from typing import Optional, Tuple

from bot import (
    BOT_START_TIME,
    LOGGER,
    LOG_FILE_ZZGEVC,
    MAX_MESSAGE_LENGTH,
    AUTH_USERS,
    crf,
    codec,
    resolution,
    audio_b,
    preset,
    watermark,
    data,
    pid_list
)
from bot.commands import Command
from bot.localisation import Localisation
from bot.helper_funcs.display_progress import TimeFormatter, humanbytes

# Constants
ALLOWED_FFMPEG_VARS = {'crf', 'preset', 'audio_b', 'codec', 'resolution', 'watermark'}
MAX_CMD_LENGTH = 1000
CMD_TIMEOUT = 60

async def exec_message_f(client, message) -> None:
    """Execute shell commands securely with proper error handling."""
    if message.from_user.id not in AUTH_USERS:
        return

    try:
        # Safely extract command
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("⚠️ Please provide a command to execute.\nUsage: /exec <command>")
            return

        cmd = parts[1].strip()
        if not cmd:
            await message.reply_text("⚠️ Command cannot be empty.")
            return
        if len(cmd) > MAX_CMD_LENGTH:
            await message.reply_text(f"⚠️ Command too long (max {MAX_CMD_LENGTH} chars).")
            return

        reply_to_id = message.reply_to_message.id if message.reply_to_message else message.id
        status_msg = await message.reply_text("⌛ Executing command...")

        try:
            process = await asyncio.wait_for(
                asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=10
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=CMD_TIMEOUT)
        except asyncio.TimeoutError:
            await status_msg.edit_text("⌛ Command timed out.")
            return

        # Process output
        e = stderr.decode().strip() if stderr else "No Error"
        o = stdout.decode().strip() if stdout else "No Output"
        
        OUTPUT = (
            f"<blockquote>📌 <b>Command</b>:\n<code>{cmd}</code>\n\n"
            f"🆔 <b>PID</b>: <code>{process.pid}</code>\n\n"
            f"❌ <b>Error</b>:\n<code>{e if e else 'None'}</code>\n\n"
            f"📋 <b>Output</b>:\n<code>{o if o else 'None'}</code></blockquote>"
        )

        # Handle large output
        if len(OUTPUT) > MAX_MESSAGE_LENGTH:
            try:
                with open("exec.txt", "w", encoding="utf-8") as f:
                    f.write(OUTPUT)
                await client.send_document(
                    chat_id=message.chat.id,
                    document="exec.txt",
                    caption=cmd[:50],
                    reply_to_message_id=reply_to_id
                )
            finally:
                if os.path.exists("exec.txt"):
                    os.remove("exec.txt")
            await status_msg.delete()
        else:
            await status_msg.edit_text(OUTPUT)

    except Exception as e:
        LOGGER.error(f"exec error: {str(e)}")
        await message.reply_text(f"⚠️ Error: {str(e)}")

async def eval_message_f(client, message) -> None:
    """Safely evaluate Python code with FFmpeg-specific handling."""
    if message.from_user.id not in AUTH_USERS:
        return

    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("⚠️ Usage: /eval <code>")
            return

        cmd = parts[1].strip()
        if not cmd:
            await message.reply_text("⚠️ Empty code!")
            return

        status_msg = await message.reply_text("⏳ Evaluating...")
        reply_to_id = message.reply_to_message.id if message.reply_to_message else message.id

        # FFmpeg config special handling
        if any(cmd.startswith(f"{var}.") for var in ALLOWED_FFMPEG_VARS):
            safe_globals = {
                'crf': crf,
                'preset': preset,
                'audio_b': audio_b,
                'codec': codec,
                'resolution': resolution,
                'watermark': watermark,
                'insert': list.insert,
                'update': dict.update,
                'append': list.append,
                'clear': list.clear
            }
            
            try:
                exec(f"result = {cmd}", {"__builtins__": None}, safe_globals)
                output = "✅ FFmpeg config updated successfully!"
            except Exception as e:
                output = f"❌ FFmpeg config error: {str(e)}"
        else:
            # Regular eval handling
            old_stdout, old_stderr = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = redirected = io.StringIO()
            
            try:
                await aexec(cmd, client, message)
                output = redirected.getvalue() or "✅ Success"
            except Exception as e:
                output = f"❌ Error: {str(e)}\n{traceback.format_exc()}"
            finally:
                sys.stdout, sys.stderr = old_stdout, old_stderr

        final_output = (
            f"<blockquote>🧠 <b>Evaluated</b>:\n<code>{cmd}</code>\n\n"
            f"📤 <b>Result</b>:\n<code>{output.strip()}</code></blockquote>"
        )

        if len(final_output) > MAX_MESSAGE_LENGTH:
            try:
                with open("eval.txt", "w", encoding="utf-8") as f:
                    f.write(final_output)
                await client.send_document(
                    chat_id=message.chat.id,
                    document="eval.txt",
                    caption=cmd[:50],
                    reply_to_message_id=reply_to_id
                )
            finally:
                if os.path.exists("eval.txt"):
                    os.remove("eval.txt")
            await status_msg.delete()
        else:
            await status_msg.edit_text(final_output)

    except Exception as e:
        LOGGER.error(f"Eval error: {str(e)}")
        await message.reply_text(f"⚠️ Critical error: {str(e)}")

async def aexec(code: str, client, message) -> None:
    """Safe async code execution with restrictions."""
    exec_globals = {
        'client': client,
        'message': message,
        'print': lambda *a, **k: None,
        '__builtins__': {
            k: v for k, v in __builtins__.items() 
            if k in ('str', 'int', 'float', 'bool', 'list', 'dict', 'tuple')
        }
    }
    
    exec(
        "async def __aexec(client, message):\n"
        + "\n".join(f"    {line}" for line in code.split("\n")),
        exec_globals
    )
    
    await asyncio.wait_for(exec_globals['__aexec'](client, message), timeout=30)

async def upload_log_file(client, message) -> None:
    """Upload log file with safety checks."""
    if message.from_user.id not in AUTH_USERS:
        return

    try:
        if not os.path.exists(LOG_FILE_ZZGEVC):
            await message.reply_text("⚠️ Log file not found!")
            return

        if os.path.getsize(LOG_FILE_ZZGEVC) > 50 * 1024 * 1024:  # 50MB
            await message.reply_text("⚠️ Log file too large (max 50MB).")
            return

        await message.reply_document(
            document=LOG_FILE_ZZGEVC,
            caption="📜 Bot log file",
            disable_notification=True
        )
    except Exception as e:
        LOGGER.error(f"Log upload error: {str(e)}")
        await message.reply_text(f"⚠️ Failed to upload logs: {str(e)}")
