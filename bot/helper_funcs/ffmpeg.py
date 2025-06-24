async def convert_video(video_file, output_directory, total_time, bot, message, chan_msg):
    """Handle video conversion with comprehensive error handling"""
    progress_file = os.path.join(output_directory, "progress.txt")
    status_file = os.path.join(output_directory, "status.json")
    out_put_file_name = None

    try:
        # Create safe filenames
        original_video_file = video_file
        video_file = await safe_path(video_file)
        
        # Rename if needed
        if original_video_file != video_file:
            try:
                os.rename(original_video_file, video_file)
                LOGGER.info(f"Renamed file from {original_video_file} to {video_file}")
            except Exception as e:
                LOGGER.error(f"Failed to rename file: {e}")
                video_file = original_video_file

        # Validate input file
        if not os.path.exists(video_file):
            raise FileNotFoundError(f"Input file not found: {video_file}")
        
        # Verify file is not empty
        if os.path.getsize(video_file) == 0:
            raise Exception("Input file is empty (0 bytes)")

        # Setup default encoding parameters
        if not crf: crf.append("28")
        if not codec: codec.append("libx265")
        if not resolution: resolution.append("1280x720")
        if not preset: preset.append("veryfast")
        if not audio_b: audio_b.append("48k")
        if not watermark:
            watermark.append('-vf "drawtext=fontfile=font.ttf:fontsize=25:fontcolor=white:bordercolor=black@0.50:x=w-tw-10:y=10:box=1:boxcolor=black@0.5:boxborderw=6:text=〄"')

        # Prepare output filename
        base_name = await safe_path(os.path.basename(video_file))
        file_name, file_ext = os.path.splitext(base_name)
        out_put_file_name = os.path.join(
            output_directory,
            f"{file_name}[Encoded].mkv"
        )

        # Clean any existing temp files
        for f in [progress_file, status_file, out_put_file_name]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception as e:
                LOGGER.warning(f"Couldn't remove existing file {f}: {e}")

        # First try: Standard conversion
        ffmpeg_command = [
            'ffmpeg',
            '-hide_banner',
            '-loglevel', 'error',
            '-progress', progress_file,
            '-i', video_file,
            '-c:v', codec[0],
            '-map', '0',
            '-crf', crf[0],
            '-c:s', 'copy',
            '-pix_fmt', 'yuv420p10le',
            '-s', resolution[0],
            '-b:v', '1500k',
            '-c:a', 'libopus',
            '-b:a', audio_b[0],
            '-preset', preset[0],
            '-y',
            out_put_file_name
        ]

        # Second try: Fallback command without complex filters
        fallback_command = [
            'ffmpeg',
            '-hide_banner',
            '-loglevel', 'error',
            '-progress', progress_file,
            '-i', video_file,
            '-c:v', codec[0],
            '-map', '0',
            '-crf', crf[0],
            '-c:s', 'copy',
            '-pix_fmt', 'yuv420p10le',
            '-s', resolution[0],
            '-c:a', 'libopus',
            '-b:a', audio_b[0],
            '-preset', preset[0],
            '-y',
            out_put_file_name
        ]

        # Third try: Minimal conversion
        minimal_command = [
            'ffmpeg',
            '-hide_banner',
            '-loglevel', 'error',
            '-progress', progress_file,
            '-i', video_file,
            '-c:v', 'copy',
            '-c:a', 'copy',
            '-y',
            out_put_file_name
        ]

        commands_to_try = [
            (ffmpeg_command, "Standard command"),
            (fallback_command, "Fallback command"),
            (minimal_command, "Minimal command")
        ]

        last_error = None
        COMPRESSION_START_TIME = time.time()

        for cmd, cmd_name in commands_to_try:
            try:
                LOGGER.info(f"Trying {cmd_name}: {' '.join(cmd)}")
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                pid_list.insert(0, process.pid)
                with open(status_file, 'w') as f:
                    json.dump({
                        'pid': process.pid,
                        'message': message.id,
                        'running': True
                    }, f, indent=2)

                # Progress tracking loop
                while True:
                    await asyncio.sleep(3)
                    if process.returncode is not None:
                        break

                    try:
                        with open(progress_file, 'r') as file:
                            text = file.read()
                            frame = re.findall(r"frame=(\d+)", text)
                            time_in_us = re.findall(r"out_time_ms=(\d+)", text)
                            progress = re.findall(r"progress=(\w+)", text)
                            speed = re.findall(r"speed=(\d+\.?\d*)", text)

                            frame = int(frame[-1]) if frame else 0
                            speed = float(speed[-1]) if speed else 1.0
                            time_in_us = int(time_in_us[-1]) if time_in_us else 0

                            if progress and progress[-1] == "end":
                                LOGGER.info("Encoding completed")
                                break

                            elapsed_time = time_in_us / 1000000
                            remaining_time = math.floor((total_time - elapsed_time) / speed)
                            percentage = math.floor(elapsed_time * 100 / total_time)

                            progress_str = (
                                "📈 <b>Progress:</b> {0}%\n[{1}{2}]".format(
                                    round(percentage, 2),
                                    ''.join([FINISHED_PROGRESS_STR for _ in range(math.floor(percentage / 10))]),
                                    ''.join([UN_FINISHED_PROGRESS_STR for _ in range(10 - math.floor(percentage / 10))])
                                )
                            )

                            stats = (
                                f'<blockquote>🗳 <b>Encoding in Progress</b>\n\n'
                                f'⌚ <b>Time Left:</b> {TimeFormatter(remaining_time * 1000) if remaining_time > 0 else "-"}\n\n'
                                f'{progress_str}\n</blockquote>'
                            )

                            try:
                                await message.edit_text(
                                    text=stats,
                                    reply_markup=InlineKeyboardMarkup([
                                        [InlineKeyboardButton('❌ Cancel ❌', callback_data='fuckingdo')]
                                    ])
                                )
                            except Exception as e:
                                if "MESSAGE_NOT_MODIFIED" not in str(e):
                                    LOGGER.warning(f"Progress update failed: {e}")
                    except Exception as e:
                        LOGGER.error(f"Progress tracking error: {e}")
                        continue

                stdout, stderr = await process.communicate()
                LOGGER.debug(f"FFmpeg stdout: {stdout.decode().strip()}")
                LOGGER.debug(f"FFmpeg stderr: {stderr.decode().strip()}")

                if process.pid in pid_list:
                    pid_list.remove(process.pid)

                # Verify output
                if os.path.exists(out_put_file_name):
                    if os.path.getsize(out_put_file_name) > 0:
                        LOGGER.info(f"Encoding successful with {cmd_name}")
                        return out_put_file_name
                    else:
                        os.remove(out_put_file_name)
                        last_error = f"{cmd_name} produced empty output file"
                        LOGGER.warning(last_error)
                else:
                    last_error = f"{cmd_name} failed to create output file\nFFmpeg error:\n{stderr.decode().strip()}"
                    LOGGER.warning(last_error)

            except Exception as e:
                last_error = str(e)
                LOGGER.warning(f"Command {cmd_name} failed: {e}")
                continue

        raise Exception(f"All conversion attempts failed. Last error: {last_error}")

    except Exception as e:
        LOGGER.error(f"Conversion failed: {str(e)}", exc_info=True)
        try:
            if out_put_file_name and os.path.exists(out_put_file_name):
                os.remove(out_put_file_name)
        except Exception as e:
            LOGGER.error(f"Failed to remove output file: {e}")
        raise
    finally:
        for f in [progress_file, status_file]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception as e:
                LOGGER.error(f"Failed to remove temp file {f}: {e}")

# ... [keep the existing media_info and take_screen_shot functions] ...

async def media_info(saved_file_path):
    """Get media duration and bitrate with robust error handling"""
    try:
        if not os.path.exists(saved_file_path):
            LOGGER.error(f"Media file not found: {saved_file_path}")
            return None, None

        cmd = [
            'ffmpeg',
            '-hide_banner',
            '-i', saved_file_path
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        _, stderr = process.communicate()

        duration = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", stderr)
        bitrate = re.search(r"bitrate:\s*(\d+)\s*kb/s", stderr)

        total_seconds = None
        if duration:
            hours, minutes, seconds = map(float, duration.groups())
            total_seconds = hours * 3600 + minutes * 60 + seconds

        bitrate_value = bitrate.group(1) if bitrate else None
        
        return total_seconds, bitrate_value

    except Exception as e:
        LOGGER.error(f"Media info error: {str(e)}", exc_info=True)
        return None, None


async def take_screen_shot(video_file, output_directory, ttl):
    """Capture screenshot from video with multiple fallbacks"""
    try:
        if not os.path.exists(video_file):
            LOGGER.error(f"Video file not found: {video_file}")
            return None

        # Create output directory if it doesn't exist
        os.makedirs(output_directory, exist_ok=True)

        out_put_file_name = os.path.join(
            output_directory,
            f"{os.path.basename(video_file)}_{int(time.time())}.jpg"
        )

        # Try multiple methods to get screenshot
        methods = [
            # Method 1: Standard screenshot
            [
                'ffmpeg',
                '-hide_banner',
                '-loglevel', 'error',
                '-ss', str(ttl),
                '-i', video_file,
                '-vframes', '1',
                '-q:v', '2',
                '-f', 'image2',
                '-y', out_put_file_name
            ],
            # Method 2: Alternative approach
            [
                'ffmpeg',
                '-hide_banner',
                '-loglevel', 'error',
                '-ss', str(ttl),
                '-i', video_file,
                '-vframes', '1',
                '-vf', 'scale=640:-1',
                '-f', 'image2',
                '-y', out_put_file_name
            ]
        ]

        for method in methods:
            try:
                proc = await asyncio.create_subprocess_exec(*method)
                await proc.wait()
                
                if os.path.exists(out_put_file_name) and os.path.getsize(out_put_file_name) > 0:
                    return out_put_file_name
                
                # Remove failed attempt
                if os.path.exists(out_put_file_name):
                    os.remove(out_put_file_name)
                    
            except Exception as e:
                LOGGER.warning(f"Screenshot method failed: {e}")

        LOGGER.error("All screenshot methods failed")
        return None

    except Exception as e:
        LOGGER.error(f"Screenshot error: {str(e)}", exc_info=True)
        return None
