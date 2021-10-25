import os
import requests
from bs4 import BeautifulSoup
from errbot import CommandError
import json
from collections import namedtuple

from requests.models import Response

class ConfluenceHelper:

    SAVED_ROTAS_PAGE_ID = '4951083676'

    ## HELPERS FOR RETURNING ROTA DETAILS

    @staticmethod
    def get_page_from_id(conf_page_id):
        headers = {
            "Content-Type": "application/json",
        }

        response = requests.get(
            f"https://zendesk.atlassian.net/wiki/rest/api/content/{conf_page_id}?expand=body.view,body.storage,version",
            headers=headers,
            auth=(os.environ.get("ATLASSIAN_USER"), os.environ.get("ATLASSIAN_TOKEN")),
        )

        if response.status_code != 200:
            raise CommandError(f"Could not find Confluence Page for id {conf_page_id}")
        else:
            return response.json()

    @staticmethod
    def update_confluence_page(version_no, title, updated_storage):
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        payload = json.dumps({
            "version": {
                "number": version_no + 1
            },
            "title": title,
            "type": 'page',
            "body": {
                "storage": {
                    "value": updated_storage,
                    "representation": "storage"
                }
            }
        })

        response = requests.put(
            f'https://zendesk.atlassian.net/wiki/rest/api/content/{ConfluenceHelper.SAVED_ROTAS_PAGE_ID}',
            data=payload,
            headers=headers,
            auth=(os.environ.get("ATLASSIAN_USER"), os.environ.get("ATLASSIAN_TOKEN")),
        )

        return response.json()

    
    @staticmethod
    def get_page_view_soup(page_html):
        raw_view = page_html['body']['view']['value']
        view_soup = BeautifulSoup(raw_view, 'html.parser')
        return view_soup

    
    @staticmethod
    def get_page_storage_soup(page_html):
        raw_storage = page_html['body']['storage']['value']
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

        teams = {
            'Red Pandas': '@red-pandas',
            'Canaries': '@canaries',
            'Mongooses': '@mongooses',
            'Kelpies': '@kelpie',
            'Kelpie': '@kelpie',
            'Zenguins': '@zenguins',
        }

        name_list = []
        cells = table_row.find_all('td')


        # Skip the first cell as it's the date
        for cell in cells[1:]:
            if cell.text in teams:
                name_list.append(teams[cell.text])
            else:
                links = cell.find_all('a', 'user-mention')
                if len(links) == 0 and not cell.text:
                    name_list.append('None')
                elif len(links) == 0 and cell.text:
                    name_list.append(cell.text)
                elif len(links) == 1:
                    name_list.append(ConfluenceHelper.get_slack_names(links[0]['data-account-id']))
                else:
                    engineers = ''
                    for link in links:
                        engineers += ConfluenceHelper.get_slack_names(link['data-account-id']) + '\n'

                    name_list.append(engineers[:-1])

        return name_list


    ## HELPERS FOR MANIUPULATING ROTA LIST

    @staticmethod
    def get_all_rotas():
        
        page_html = ConfluenceHelper.get_page_from_id(ConfluenceHelper.SAVED_ROTAS_PAGE_ID)

        raw_html = page_html['body']['storage']['value']
        soup = BeautifulSoup(raw_html, 'html.parser')
        table = soup.find('table')
        rows = table.find_all('tr')

        rotas = []

        for row in rows[1:]:
            cells = row.find_all('p')
            rota_dict = {}
            rota_dict['rota_name'] = cells[0].text
            rota_dict['conf_id'] = cells[1].text
            
            chan = cells[2].text
            if chan[:2] == '##':
                rota_dict['channel'] = '<' + chan[1:] + '>'
            else:
                rota_dict['channel'] = chan

            rota_dict['creator'] = cells[3].text
                
            rotas.append(rota_dict)

        return rotas

    
    @staticmethod
    def add_rota(rota_name, conf_id, channel, creator):

        # This will add a new rota to the saved list

        page_html = ConfluenceHelper.get_page_from_id(ConfluenceHelper.SAVED_ROTAS_PAGE_ID)

        # These are required to be passed back
        version_no = page_html['version']['number']
        title = page_html['title']
        original_storage = page_html['body']['storage']['value']

        name_cell = f'<td><p>{rota_name}</p></td>'
        id_cell = f'<td><p>{conf_id}</p></td>'
        channel_cell = f'<td><p>{channel}</p></td>'
        creator_cell = f'<td><p>{creator}</p></td>'

        insert_index = original_storage.find('</tbody>')

        new_tag = '<tr>' + name_cell + id_cell + channel_cell + creator_cell + '</tr>'
        updated_storage = original_storage[:insert_index] + new_tag + original_storage[insert_index:]

        res = ConfluenceHelper.update_confluence_page(version_no, title, updated_storage)

        RotaDetails = namedtuple('RotaDetails', 'name channel creator')
        return RotaDetails(rota_name, channel, creator)


    @staticmethod
    def delete_rota(conf_id):

        page_html = ConfluenceHelper.get_page_from_id(ConfluenceHelper.SAVED_ROTAS_PAGE_ID)

        # These are required to be passed back
        version_no = page_html['version']['number']
        title = page_html['title']
        original_storage = page_html['body']['storage']['value']

        soup = BeautifulSoup(original_storage, 'html.parser')

        deleted = soup.find(string=conf_id).parent.parent.parent.extract()

        res = ConfluenceHelper.update_confluence_page(version_no, title, str(soup))

        info = [val.text for val in deleted.find_all('p')]

        RequestResponse = namedtuple('RequestResponse', 'error rota_name')
        return RequestResponse(False, info[0])
