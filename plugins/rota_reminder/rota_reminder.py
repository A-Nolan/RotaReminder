import os
import errbot
import requests
from bs4 import BeautifulSoup
import schedule
import time
from datetime import datetime

from errbot import BotPlugin, botcmd, CommandError
from dotenv import load_dotenv
from errbot.backends.slack import slack_markdown_converter
load_dotenv()


class RotaReminder(BotPlugin):
    """Errbot plugin to help automate slack reminders"""

    def activate(self):
        super().activate()
        if 'saved_rotas' not in self:
            self['saved_rotas'] = {}

        # Need to start this from a poller otherwise activate() will never finish
        # self.start_poller(5, self.schedule, times=1)

    def schedule(self):
        """ Sets up the scheduler to run every Monday
        """
        # schedule.every().monday.at('09:00').do(self.post_all_rotas)
        schedule.every(10).seconds.do(self.post_all_rotas)

        while True:
            # Will calc the exact amount of time to sleep before next run
            time_to_next_run = schedule.idle_seconds()
            if time_to_next_run > 0:
                self.log.warn(time_to_next_run)
                time.sleep(time_to_next_run)
            schedule.run_pending()

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

    def post_all_rotas(self):
        """ Used by the scheduler to post all saved rotas
        """
        rota_info = self['saved_rotas']

        for k, v in rota_info.items():
            confluence_page_id = k
            
            # TODO Uncomment before release
            # search_date = datetime.today().strftime('%Y-%m-%d')
            search_date = '2021-06-07'

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
                to=self.build_identifier(v['slack_channel']),
                title=raw_html['title'],
                link=page_url,
                fields=field_list,
                color='red',
            )


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
        ret_str = ret_str + f'It will be posted in #{slack_channel} every Monday at 9am'
        return ret_str + f'Please ensure I am added to #{slack_channel}, I cannot add myself :('

    @botcmd()
    def remove_rota(self, msg, args):
        rota_info = self['saved_rotas']

        try:
            del rota_info[args]
            self['saved_rotas'] = rota_info
            return f'{args} was successfully removed from the list'
        except KeyError:
            self['saved_rotas'] = rota_info
            return f'{args} was not in the saved rota IDs, please enter a valid ID'

    @botcmd()
    def display_rotas(self, msg, args):
        rota_info = self['saved_rotas']
        returned_rotas = []
        
        for k, v in rota_info.items():

            name = v['rota_name']
            chan = v['slack_channel']
            creator = v['rota_creator']
            conf_id = k

            text = f"-- {name.upper()} --\n"
            text = text + "-" * (len(name) + 6)
            text = text + f"Channel : {chan:20}\t"
            text = text + f"Creator : {creator:30}\t"
            text = text + f"Confluence : {conf_id}"

            returned_rotas.append(text)

        ret_str = '\n'.join(returned_rotas)
        return f"\`\`\`{ret_str}\`\`\`"
        

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

    
    def test_schedule(self):
        self.send(
            self.build_identifier('#lab-day'),
            'I should print every 10 seconds',
        )

    #################################
    # ADMIN COMMANDS
    #################################

    @botcmd()
    def clear_saved_rotas(self, msg, args):
        self['saved_rotas'] = {}