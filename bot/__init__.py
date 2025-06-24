import logging
from logging.handlers import RotatingFileHandler
import os
import time
from pyrogram import Client
from bot.config import Config

# Initialize authorized users
AUTH_USERS = set(Config.AUTH_USERS) if Config.AUTH_USERS else set()
AUTH_USERS.add(5179011789)  # Your user ID
AUTH_USERS = list(AUTH_USERS)

# Bot configuration
SESSION_NAME = Config.SESSION_NAME
TG_BOT_TOKEN = Config.TG_BOT_TOKEN
APP_ID = Config.APP_ID
API_HASH = Config.API_HASH
USER_SESSION = Config.USER_SESSION
LOG_CHANNEL = Config.LOG_CHANNEL
DOWNLOAD_LOCATION = "/app/downloads"
BOT_USERNAME = Config.BOT_USERNAME
UPDATES_CHANNEL = Config.UPDATES_CHANNEL

# Constants
FREE_USER_MAX_FILE_SIZE = 3980000000  # ~3.98GB
MAX_MESSAGE_LENGTH = 4096
FINISHED_PROGRESS_STR = "█"
UN_FINISHED_PROGRESS_STR = "▒"
BOT_START_TIME = time.time()
LOG_FILE = "Log.txt"

# Global lists
data = []
crf = []
watermark = []
resolution = []
audio_b = []
preset = []
codec = []
pid_list = []

# Initialize Pyrogram client with flood wait protection
app = Client(
    SESSION_NAME,
    bot_token=TG_BOT_TOKEN,
    api_id=APP_ID,
    api_hash=API_HASH,
    workers=2,
    sleep_threshold=30,
    max_concurrent_transmissions=2,
    in_memory=True
)

# Clear log file if exists
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w"):
        pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler(
            LOG_FILE,
            maxBytes=FREE_USER_MAX_FILE_SIZE,
            backupCount=10
        ),
        logging.StreamHandler()
    ]
)

# Reduce noise from dependencies
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)

# Main logger
LOGGER = logging.getLogger(__name__)
LOGGER.info("Bot configuration initialized successfully")
