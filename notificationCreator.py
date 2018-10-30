import requests
import json
import urllib3
import time
import logging
from logging.handlers import RotatingFileHandler

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# configuration
with open('config.json') as f:
    config = json.load(f)

# logging
logLevel = config['logLevel']
logger = logging.getLogger(__name__)
# rolling logs with max 2 MB files with 3 backups
handler = logging.handlers.RotatingFileHandler(
    'Log/notification_creator.log', maxBytes=2000000, backupCount=3)
if logLevel == 'INFO':
    logging.basicConfig(level=logging.INFO)
    handler.setLevel(logging.INFO)
else:
    logging.basicConfig(level=logging.DEBUG)
    handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.info('Log level set to: ' + logLevel)

localServer = config['promoteOnCustomPropertyChange']['localServer']
userDirectory = config['promoteOnCustomPropertyChange']['userDirectory']
userId = config['promoteOnCustomPropertyChange']['userId']
f.close()

logger.info('User Directory: ' + userDirectory)
logger.info('User: ' + userId)

# build URL
baseUrl = 'https://' + localServer + ':4242'
logger.info('Base URL: ' + baseUrl)

# set headers
headers = {
    "X-Qlik-Xrfkey":
    "abcdefg123456789",
    "X-Qlik-User":
    "UserDirectory=" + userDirectory + ";UserId=" + userId,
    "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36"
}

while True:
    try:
        # Setup Session
        s = requests.Session()

        # add certs to headers
        s.headers.update(headers)
        s.cert = ("Certificates/LocalServerCerts/client.pem",
                  "Certificates/LocalServerCerts/client_key.pem")
        s.verify = False

        # create the notification that picks up app update's
        data = 'http://127.0.0.1:5000/app/update'
        logger.info('Data: ' + str(data))

        r = s.post(
            baseUrl + "/qrs/notification?name=app&changeType=update&xrfkey=abcdefg123456789",
            json=data,
            headers={"Content-Type": "application/json"})

        s.close()
        logger.info('Created	' + 'Status code: ' + str(r.status_code) + '	Data Payload: ' + data +
                    '	Response: ' + str(r.json()))
    except requests.exceptions.RequestException as e:
        logger.info(
            'The notifications cannot be created. The repository service is likely not fully operational.'
        )
    except ValueError as e:
        logger.info('Value Error received: ' + str(e) +
                    '. The repository service is likely in the boot process.')

    time.sleep(60)