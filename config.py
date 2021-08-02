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

# CORE_PLUGINS = ("ACLs", "Help", "Health", "Utils", "TextCmds", "Webserver", "RotaReminder")
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

# Access Control for admin commands
ADMIN_RESTRICTED_ACL = dict(allowusers=BOT_ADMINS, allowmuc=True)
ALL_RESTRICTED_ACL = dict(allowusers=(None,), allowmuc=False) 
ALL_ALLOWED_ACL = dict(allowmuc=True) 

ACCESS_CONTROLS = {
    # Remove Errbot defined commands
    "ChatRoom:*": ALL_RESTRICTED_ACL,
    "Flows:*": ALL_RESTRICTED_ACL,
    "Health:*": ALL_RESTRICTED_ACL,
    "Plugins:*": ALL_RESTRICTED_ACL,
    "Utils:*": ALL_RESTRICTED_ACL,

    # Remove Talkbot Admin commands
    "RotaReminder:admin*": ADMIN_RESTRICTED_ACL,
}

HIDE_RESTRICTED_COMMANDS = True
HIDE_RESTRICTED_ACCESS = True

DIVERT_TO_THREAD = ('help', 'rota_display', 'rota_add', 'rota_remove')