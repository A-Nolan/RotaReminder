import os
import errbot
import requests
from bs4 import BeautifulSoup
import schedule
import time
from datetime import datetime

from rota_exceptions import *

from errbot import BotPlugin, botcmd, CommandError
from dotenv import load_dotenv
load_dotenv()


class RotaReminder(BotPlugin):
    """
    https://zendesk.atlassian.net/wiki/spaces/~332665210/pages/4951083676/RotaReminder+Documentation
    """

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
    # DATABASE HELPER FUNCTIONS
    #################################

    def get_all_rotas(self):
        headers = {
            'Authorization': f'Bearer {os.environ.get("AIRTABLE_API_TOKEN")}',
        }

        try:
            response = requests.get(f'https://api.airtable.com/v0/{os.environ.get("AIRTABLE_BASE_ID")}/Table%201', headers=headers)
            exception_handler(response)
        except Exception as e:
            self.log_info(str(e), error=True)
            return 'An error has occured, my admins have been notified! Sorry!'
    
        return response.json()['records']

    def add_rota(self, conf_id, name, creator, channel):
        headers = {
            'Authorization': f'Bearer {os.environ.get("AIRTABLE_API_TOKEN")}',
            'Content-Type': 'application/json',
        }

        data = (
            f'{{ "fields": {{ "confluence_id": "{conf_id}", "rota_name": "{name}", "creator": "{creator}", "channel": "{channel}" }} }}'
        )

        try:
            response = requests.post(f'https://api.airtable.com/v0/{os.environ.get("AIRTABLE_BASE_ID")}/Table%201', headers=headers, data=data)
            exception_handler(response)
        except Exception as e:
            self.log_info(str(e), error=True)
            return 'An error has occured, my admins have been notified! Sorry!'

        self.log_info(response.json())
        res_dict = response.json()['fields']

        ret_str = (
            f'Thanks {res_dict["creator"]}! I have added {res_dict["rota_name"]} to the list\n'
            f'It will be posted in #{res_dict["channel"]} every Monday at 9am\n'
            f'Please ensure I am added to #{res_dict["channel"]} or I may not be able to post there :('
        )

        return ret_str

    def delete_rota(self, rota_identifier):
        headers = {
            'Authorization': f'Bearer {os.environ.get("AIRTABLE_API_TOKEN")}',
        }

        rotas = self.get_all_rotas()

        for rota in rotas:
            if rota_identifier in rota['fields'].values():
                try:
                    response = requests.delete(f'https://api.airtable.com/v0/{os.environ.get("AIRTABLE_BASE_ID")}/Table%201/{rota["id"]}', headers=headers)
                    exception_handler(response)
                except Exception as e:
                    self.log_info(str(e), error=True)
                    return 'An error has occured, my admins have been notified! Sorry!'
                
                return [rota['fields']['rota_name'], response.json()]

        return False


    #################################
    # ROTA HELPER FUNCTIONS
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

    def post_all_rotas(self, search_date=''):
        """ Used by the scheduler to post all saved rotas
        """
        rotas = self.get_all_rotas()

        for rota in rotas:
            confluence_page_id = rota['fields']['confluence_id']
            
            if not search_date:
                search_date = datetime.today().strftime('%Y-%m-%d')

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
                summary='Use (!help RotaReminder) for documentation',
                to=self.build_identifier('#' + rota['fields']['channel']),
                title=raw_html['title'],
                link=page_url,
                fields=field_list,
                color='red',
            )

    def log_info(self, response, error=False, msg_details=[]):
        if error:
            self.send(
                self.build_identifier('#talk-rota-logs'),
                (
                    "@aaron.nolan and @jasonshawn.dsouza\n"
                    f"{msg_details}\n"
                    f"\`\`\`{response}\`\`\`"
                ),
            )
        else:
            self.send(
                self.build_identifier('#talk-rota-logs'),
                (
                    f"{msg_details}\n"
                    f"\`\`\`{response}\`\`\`"
                ),
            )

    #################################
    # BOT COMMANDS
    #################################

    @botcmd(split_args_with=', ')
    def rota_add(self, msg, args):
        """
        Add rota to saved list - Usage: !rota add <rota_name>, <confluence_page_id>, <slack_channel>
        """

        if not len(args) == 3:
            return "\`\`\`Command should have 3 args, separated by commas\`\`\`"

        self.log_info(msg, msg_details=[msg.frm.fullname, msg.to.channelname])
        rota_name = args[0]
        page_id = args[1]

        # Private channels cannot be mentioned directly
        # This handles this case by stripping the '#'
        if args[2][0] == '#':
            slack_channel = args[2][1:]
        else:
            slack_channel = args[2]

        creator = msg.frm.fullname

        ret_str = self.add_rota(page_id, rota_name, creator, slack_channel)
        return f"\`\`\`{ret_str}\`\`\`"

    @botcmd()
    def rota_remove(self, msg, args):
        """
        Remove a rota from saved list - Usage: !rota remove <confluence_page_id>
        """
        ret_str = ''

        response = self.delete_rota(args)

        if response:
            if isinstance(response, list):
                self.log_info(response, msg_details=[msg.frm.fullname, msg.to.channelname])
                ret_str = f'{response[0]} has successfully been removed from the rota list'
            else:
                ret_str = response
        else:
            ret_str = (
                'That rota has not been found\n'
                'Please ensure you entered the correct name/confluence id\n'
                'You can use "!rota display" to view all saved rotas'
            )

        return f"\`\`\`{ret_str}\`\`\`"

    @botcmd()
    def rota_display(self, msg, args):
        """
        Show all saved rotas - Usage: !rota display
        """
        rotas = self.get_all_rotas()

        if isinstance(rotas, str):
            return rotas

        returned_rotas = []
        self.log_info(msg, msg_details=[msg.frm.fullname, msg.to.channelname])

        for rota in rotas:

            conf_id = rota['fields']['confluence_id']
            name = rota['fields']['rota_name']
            creator = rota['fields']['creator']
            channel = rota['fields']['channel']

            text = (
                f'{name.upper()}\n'
                f'Channel:\t\t #{channel}\n'
                f'Creator:\t\t {creator}\n'
                f'Confluence ID:\t {conf_id}\n'
                f'====================================================='
            )

            returned_rotas.append(text)

        ret_str = '\n'.join(returned_rotas)
        return f"\`\`\`{ret_str}\`\`\`"
        

    #################################
    # ADMIN COMMANDS
    #################################

    @botcmd()
    def admin_clear_all_rotas(self, msg, args):
        """
        Will remove all saved rotas - Usage: !admin clear all rotas
        """
        self['saved_rotas'] = {}

    @botcmd()
    def admin_test_post_rotas(self, msg, args):
        """
        Used to test rota posting, WILL PING PEOPLE - Usage: !admin test post rotas <YYYY-MM-DD>
        """
        self.post_all_rotas(args)

    @botcmd()
    def admin_test(self, msg, args):
        """
        Used to test rota posting, WILL PING PEOPLE - Usage: !admin test post rotas <YYYY-MM-DD>
        """
        return self.delete_rota(args)