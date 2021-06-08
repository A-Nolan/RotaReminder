import json
import requests
import bs4 as BeautifulSoup
import os

from errbot import BotPlugin, botcmd, CommandError
from dotenv import load_dotenv
load_dotenv()


class RotaReminder(BotPlugin):
    """Errbot plugin to help automate slack reminders"""

    #################################
    # HELPER FUNCTIONS
    #################################

    def get_slack_username(confluence_acc_id):
        """Get users slack name from their email on their confluence page
        
        params:
         - confluence_acc_id -> str

        returns:
         - str
        """

        headers = {
            "Accept": "application/json",
        }

        response = requests.get(
            f"https://zendesk.atlassian.net/wiki/rest/api/user?accountId={confluence_acc_id}",
            headers=headers,
            auth=(os.environ.get("ATLASSIAN_USER"), os.environ.get("ATLASSIAN_TOKEN")),
        ).json()["email"]
        # Only grab the start of the email, this is their slack handle
        return response.split("@")[0]

    def get_page_html(confluence_page_id):
        """Get confluence page html from confluence page id
        
        params:
         - confluence_page_id -> str    : Obtained from the confluence pages URL

        returns:
         - list -> [str]   : Format of [[user_name, account_id, slack_username]]
        """

        headers = {
            "Content-Type": "application/json",
        }

        response = requests.get(
            f"https://zendesk.atlassian.net/wiki/rest/api/content/{confluence_page_id}?expand=body.view",
            headers=headers,
            auth=(os.environ.get("ATLASSIAN_USER"), os.environ.get("ATLASSIAN_TOKEN")),
        ).json()

        if response['statusCode'] == 404:
            raise CommandError(f"Could not find Confluence Page for id {confluence_page_id}")
        else:
            return response['statusCode']

    #################################
    # BOT COMMANDS
    #################################

    @botcmd
    def test(self, msg, args):
        print(RotaReminder.get_page_html(args))
        print('Will this display?')