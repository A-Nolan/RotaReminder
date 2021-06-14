import logging
import os
from dotenv import load_dotenv
load_dotenv()

# This is a minimal configuration to get you started with the Text mode.
# If you want to connect Errbot to chat services, checkout
# the options in the more complete config-template.py from here:
# https://raw.githubusercontent.com/errbotio/errbot/master/errbot/config-template.py

SLACK_TOKEN = os.environ.get("SLACK_TOKEN")

BACKEND = 'Slack'  # Errbot will start in text mode (console only mode) and will answer commands from there.

BOT_DATA_DIR = r'./data'
BOT_EXTRA_PLUGIN_DIR = r'./plugins'

BOT_LOG_FILE = r'./errbot.log'
BOT_LOG_LEVEL = logging.DEBUG

BOT_IDENTITY = {
    "token": SLACK_TOKEN,
}
BOT_ADMINS = ('@aaron.nolan', )  # !! Don't leave that to "@CHANGE_ME" if you connect your errbot to a chat system !!
BOT_ALT_PREFIXES = ('@ErrBotTest',)
CHATROOM_PRESENCE = ()