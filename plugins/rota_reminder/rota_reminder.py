import os
import errbot
import requests
from bs4 import BeautifulSoup
import schedule
import time
from datetime import datetime
from collections import namedtuple

from rota_exceptions import *
from confluence_helper import ConfluenceHelper

from errbot import BotPlugin, botcmd, CommandError
from errbot.backends.slack import SlackBackend, SlackRoom
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
    # ROTA HELPER FUNCTIONS
    #################################

    def post_all_rotas(self, search_date=''):
        """ Used by the scheduler to post all saved rotas
        """
        rotas = ConfluenceHelper.get_all_rotas()

        for rota in rotas:
            conf_page_id = rota['conf_id']
            
            if not search_date:
                search_date = datetime.today().strftime('%Y-%m-%d')

            page_html = ConfluenceHelper.get_page_html(conf_page_id)
            storage_soup = ConfluenceHelper.get_page_view_soup(page_html)
            table_soup = ConfluenceHelper.get_table_soup(storage_soup)
            table_headers = ConfluenceHelper.get_rota_table_headers(table_soup)
            search_row = ConfluenceHelper.get_row_from_date(table_soup, search_date)
            slack_names = ConfluenceHelper.get_slack_names_from_row(search_row)
            
            field_list = []
            page_url = f'https://zendesk.atlassian.net/wiki/spaces/TALK/pages/{conf_page_id}' 

            for pair in zip(table_headers, slack_names):
                field = [pair[0], pair[1]]
                field_list.append(field)

            # for i in range(len(headers)):
            #     if users[i] == 'None':
            #         field = [headers[i], ' - ']
            #     else:
            #         slack_user = '@' + RotaReminder.get_slack_username(users[i])
            #         field = [headers[i], slack_user]
            #     field_list.append(field)

            self.log.warn(rota['channel'])

            self.send_card(
                summary='Use (!help RotaReminder) for documentation',
                to=self.build_identifier(rota['channel']),
                title=rota['rota_name'],
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

        rota_name = args[0]
        page_id = args[1]

        if args[2][0] == "<":
            slack_channel = "#" + args[2][1:-2]
        else:
            slack_channel = "#" + args[2]

        creator = msg.frm.fullname

        # ret_str = self.add_rota(page_id, rota_name, creator, slack_channel)
        # return f"\`\`\`{ret_str}\`\`\`"

        rota_details = ConfluenceHelper.add_rota(rota_name, page_id, slack_channel, creator)
        return (
            f'\`\`\`Thanks {creator}! I have added {rota_name} to the list\n'
            f'It will be posted in {slack_channel} every Monday at 9am\n'
            f'Please ensure I am added to {slack_channel} or I may not be able to post there :(\`\`\`'
        )

    @botcmd()
    def rota_remove(self, msg, args):
        """
        Remove a rota from saved list - Usage: !rota remove <confluence_page_id>
        """
        # ret_str = ''

        # response = self.delete_rota(args)

        # if response:
        #     if isinstance(response, list):
        #         self.log_info(response, msg_details=[msg.frm.fullname, msg.to.channelname])
        #         ret_str = f'{response[0]} has successfully been removed from the rota list'
        #     else:
        #         ret_str = response
        # else:
        #     ret_str = (
        #         'That rota has not been found\n'
        #         'Please ensure you entered the correct name/confluence id\n'
        #         'You can use "!rota display" to view all saved rotas'
        #     )

        # return f"\`\`\`{ret_str}\`\`\`"

        res_tuple = ConfluenceHelper.delete_rota(args)
        ret_str = f'{res_tuple.rota_name} has successfully been removed from the rota list'
        return f"\`\`\`{ret_str}\`\`\`"

    @botcmd()
    def rota_display(self, msg, args):
        """
        Show all saved rotas - Usage: !rota display
        """
        rotas = ConfluenceHelper.get_all_rotas()

        if isinstance(rotas, str):
            return rotas

        returned_rotas = []

        for rota in rotas:

            conf_id = rota['conf_id']
            name = rota['rota_name']
            creator = rota['creator']
            if rota['channel'][:2] == '##':
                channel = rota['channel'][1:]
            else:
                channel = rota['channel']

            text = (
                f'{name.upper()}\n'
                f'Channel:\t\t {channel}\n'
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

    #################################
    # ADMIN COMMANDS
    #################################

    @botcmd()
    def rota_test(self, msg, args):
        pass

    @staticmethod
    def post_rotas_from_conf():
        headers = {
            "Content-Type": "application/json",
        }

        response = requests.get(
            f"https://zendesk.atlassian.net/wiki/rest/api/content/4951083676?expand=body.view",
            headers=headers,
            auth=(os.environ.get("ATLASSIAN_USER"), os.environ.get("ATLASSIAN_TOKEN")),
        ).json()
    