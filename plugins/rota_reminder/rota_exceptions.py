class AirtableAuthError(Exception):
    pass

class AirtableBaseError(Exception):
    pass

def exception_handler(res):
    if res.status_code == 401:
        raise AirtableAuthError(
            'RotaReminder Error: Airtable authentication has failed'
            '\nPlease check that the api token is correct and is passing correctly'
            f'\nStatus code returned was: {res.status_code}'
        )
    elif res.status_code == 404:
        raise AirtableBaseError(
            'RotaReminder Error: Airtable base lookup has failed'
            '\nPlease check that the base id is correct and is pasing correctly'
            f'\nStatus code returned was: {res.status_code}'
        )
    elif res.status_code != 200:
        raise Exception(
            'RotaReminder Error: An unknown error has occured'
            f'\nStatus code returned was: {res.status_code}'
            f'\nResponse data was: {res.json()}'
        )