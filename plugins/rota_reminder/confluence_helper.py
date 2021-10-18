import os
import requests
from bs4 import BeautifulSoup
from errbot import CommandError

class ConfluenceHelper:
    @staticmethod
    def get_page_html(conf_page_id):
        headers = {
            "Content-Type": "application/json",
        }

        response = requests.get(
            f"https://zendesk.atlassian.net/wiki/rest/api/content/{conf_page_id}?expand=body.view",
            headers=headers,
            auth=(os.environ.get("ATLASSIAN_USER"), os.environ.get("ATLASSIAN_TOKEN")),
        ).json()

        if "statusCode" in response and response['statusCode'] == 404:
            raise CommandError(f"Could not find Confluence Page for id {conf_page_id}")
        else:
            return response

    
    @staticmethod
    def get_page_storage_soup(page_html):
        raw_storage = page_html['body']['view']['value']
        storage_soup = BeautifulSoup(raw_storage, 'html.parser')
        return storage_soup


    @staticmethod
    def get_table_soup(storage_soup):
        table_soup = storage_soup.find('table')
        return table_soup


    @staticmethod
    def get_rota_table_headers(table_soup):
        header_row = table_soup.find('tr')
        headers = header_row.find_all('p')
        return [header.text for header in headers[1:]]


    @staticmethod
    def get_row_from_date(table_soup, search_date):
        row = table_soup.find('time', attrs={'datetime': search_date}).parent.parent.parent
        return row


    @staticmethod
    def get_slack_names(userid):
        headers = {
            "Accept": "application/json",
        }

        response = requests.get(
            f"https://zendesk.atlassian.net/wiki/rest/api/user?accountId={userid}",
            headers=headers,
            auth=(os.environ.get("ATLASSIAN_USER"), os.environ.get("ATLASSIAN_TOKEN")),
        ).json()['email']
        # Only grab the start of the email, this is their slack handle
        return '@' + response.split("@")[0]


    @staticmethod
    def get_slack_names_from_row(table_row):
        cells = table_row.find_all('a')
        return [ConfluenceHelper.get_slack_names(cell['data-account-id']) for cell in cells]

    @staticmethod
    def get_all_rotas():
        headers = {
            "Content-Type": "application/json",
        }

        response = requests.get(
            "https://zendesk.atlassian.net/wiki/rest/api/content/5169875015?expand=body.storage",
            headers=headers,
            auth=(os.environ.get("ATLASSIAN_USER"), os.environ.get("ATLASSIAN_TOKEN")),
        ).json()

        raw_html = response['body']['storage']['value']
        soup = BeautifulSoup(raw_html, 'html.parser')
        table = soup.find('table')
        rows = table.find_all('tr')

        rotas = []

        for row in rows[1:]:
            cells = row.find_all('p')
            rota_dict = {}
            rota_dict['rota_name'] = cells[0].text
            rota_dict['conf_id'] = cells[1].text
            rota_dict['channel'] = cells[2].text
            rota_dict['creator'] = cells[3].text
                
            rotas.append(rota_dict)

        return rotas

    