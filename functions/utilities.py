import string
from decouple import config
from motor import motor_asyncio

punc = string.punctuation
punc = punc.replace('_', '').replace('[', '').replace(']', '')

host = config("DATABASE_HOST")
username = config("DATABASE_USERNAME")
password = config("DATABASE_PASSWORD")
database = config("DATABASE_NAME")

async def connect(database = database):
    client = motor_asyncio.AsyncIOMotorClient(
        host=host,
        username=username,
        password=password
    )
    return client[database]

def number_to_option(history, option):
    if option in history:
        for choice in history.split('\n')[::-1]:
            if option in choice:
                return choice
    else:    
        return 'invalid character input'
    
def process_name(name, underscore = 0):
    if underscore:
        if len(name.split(' ')) >= 2:
            name = name.replace(' ', '_')

    name = name.translate(str.maketrans('', '', punc)).strip()
    name = ' '.join(name.split())

    return name
