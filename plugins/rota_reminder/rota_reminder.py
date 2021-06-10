import json
import requests
from bs4 import BeautifulSoup
import os

from errbot import BotPlugin, botcmd, CommandError
from dotenv import load_dotenv
load_dotenv()


class RotaReminder(BotPlugin):
    """Errbot plugin to help automate slack reminders"""

    def activate(self):
        super().activate()
        if 'saved_rotas' not in self:
            self['saved_rotas'] = {}

        

    #################################
    # HELPER FUNCTIONS
    #################################

    @staticmethod
    def get_slack_username(confluence_acc_id):
        """Get users slack name from their email on their confluence page
        
        params:
            confluence_acc_id -> str

        returns:
            str
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

    @staticmethod
    def get_page_html(confluence_page_id):
        """Get confluence page table html from confluence page id
        
        params:
            confluence_page_id -> str

        returns:
            dict

        raises:
            CommandError
        """

        headers = {
            "Content-Type": "application/json",
        }

        response = requests.get(
            f"https://zendesk.atlassian.net/wiki/rest/api/content/{confluence_page_id}?expand=body.view",
            headers=headers,
            auth=(os.environ.get("ATLASSIAN_USER"), os.environ.get("ATLASSIAN_TOKEN")),
        ).json()

        if "statusCode" in response and response['statusCode'] == 404:
            raise CommandError(f"Could not find Confluence Page for id {confluence_page_id}")
        else:
            return response

    @staticmethod
    def get_table_html(page_html):
        """Get confluence page table html from html dict
        
        params:
            page_html -> dict

        returns:
            Soup object
        """

        raw_html = page_html["body"]["view"]["value"]
        soup = BeautifulSoup(raw_html, "html.parser")
        table_html = soup.find("table", class_="confluenceTable")
        return table_html

    @staticmethod
    def get_table_headers(table_soup):
        """Get all the headers from the table as a list

        params:
            table_soup -> Soup object : Table html

        returns
            list
        """

        header_row = table_soup.find_next("th").parent
        headers = header_row.find_all("th", attrs={"class": "confluenceTh"})

        header_list = []

        # [1:] to skip the first 'date' header
        for header in headers[1:]:
            header_list.append(header.text)
            
        return header_list

    # TODO Handle two users in one column e.g @Aaron Nolan + @Iulia Birlaneau
    @staticmethod
    def get_users_from_table(table_soup, search_date):
        """Get all the specified users from the dates row as a list

        params:
            search_date -> str : Date formatted as YYYY-MM-DD
            table_soup -> Soup object : Table html

        returns
            list
        """

        row = table_soup.find_next(
            "time", attrs={"datetime": search_date}
        ).parent.parent.parent  # Sorry :(
        cells = row.find_all(
            "td", attrs={"class": "confluenceTd"}
        )

        user_list = []

        # [1:] to skip the first 'date' cell
        for cell in cells[1:]:
            # Check if there is a link in the cell, as it may be empty
            if cell.find('a'):
                user_id = cell.find('a')
                user_list.append(user_id['data-account-id'])
            else:
                user_list.append('None')

        return user_list

    #################################
    # BOT COMMANDS
    #################################

    @botcmd(split_args_with=', ')
    def add_rota(self, msg, args):
        """
        Add rota to saved list - Usage: !add_rota <rota_name>, <confluence_page_id>, <slack_channel>
        """

        rota_name = args[0]
        page_id = args[1]
        slack_channel = args[2]
        creator = msg.frm.fullname.split(' ', 1)

        rota_info = self['saved_rotas']
        rota_info[page_id] = {
            'rota_name': rota_name,
            'slack_channel': '#' + slack_channel,
            'rota_creator': msg.frm.fullname
        }

        self['saved_rotas'] = rota_info
        ret_str = f'Thanks {creator[0]}, I have added {rota_name} to the list!\n'
        return ret_str + f'It will be posted in #{slack_channel} every Monday at 9am'

    @botcmd()
    def display_rotas(self, msg, args):
        rota_info = self['saved_rotas']

        for k, v in rota_info.items():

            name = v['rota_name']
            chan = v['slack_channel']
            creator = v['rota_creator']

            self.send_card(
                title=name,
                fields=(
                    ('Slack Channel', chan),
                    ('Creator', creator),
                    ('Confluence Page ID', k),
                ),
                color='blue',
                to=msg,
            )
    

    #################################
    # BOT TESTING COMMANDS
    #################################

    @botcmd(split_args_with=", ")
    def test_display_rota(self, msg, args):
        """
        Display a single rota - Usage: !test_display_rota <confluence_page_id>, <YYYY-MM-DD>
        """

        confluence_page_id = args[0]
        search_date = args[1]
        
        raw_html = RotaReminder.get_page_html(confluence_page_id)
        table_html = RotaReminder.get_table_html(raw_html)
        headers = RotaReminder.get_table_headers(table_html)
        users = RotaReminder.get_users_from_table(table_html, search_date)
        
        field_list = []
        page_url = f'https://zendesk.atlassian.net/wiki/spaces/TALK/pages/{confluence_page_id}' 

        for i in range(len(headers)):
            if users[i] == 'None':
                field = [headers[i], ' - ']
            else:
                slack_user = '@' + RotaReminder.get_slack_username(users[i])
                field = [headers[i], slack_user]
            field_list.append(field)

        self.send_card(
            title=raw_html['title'],
            link=page_url,
            fields=field_list,
            color='red',
            in_reply_to=msg,
        )

    @botcmd()
    def test_storage_read(self, msg, args):
        return self['saved_rotas']

    #################################
    # ADMIN COMMANDS
    #################################

    @botcmd()
    def clear_saved_rotas(self, msg, args):
        self['saved_rotas'] = {}