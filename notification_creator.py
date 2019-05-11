"""
    This Configures the notifications within the QRS API
    which trigger actions on app change events and
    apps being published to approval streams
"""
import os
import logging
from logging.handlers import RotatingFileHandler
import json
import uuid
import time
import csv
from pathlib import Path
import urllib3
import requests
import Modules.qrs_functions as qrs
import base64

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
with open("static/config.json") as f:
    CONFIG = json.load(f)
    f.close()

# logging
LOG_LEVEL = CONFIG["logging"]["log_level"]
PORT = CONFIG["port"]
USER_DIRECTORY = CONFIG["promote_on_custom_property_change"]["user_directory"]
USER_ID = CONFIG["promote_on_custom_property_change"]["user_id"]
PROMOTE_ON_RELOAD = CONFIG["promote_on_reload"]["enabled"]

if PROMOTE_ON_RELOAD == "true":
    PROMOTE_ON_RELOAD = True
else:
    PROMOTE_ON_RELOAD = False

if CONFIG["installed_on_sense_server"] == "true":
    LOCAL_SERVER = "localhost"
else:
    LOCAL_SERVER = CONFIG["local_server"]

BASE_URL = "https://" + LOCAL_SERVER + ":4242"


LOG_LOCATION = str(Path(__file__).parent.parent).replace("\\", "/") + "/Log/"

# LOG_LOCATION = (
#     os.path.expandvars("%ProgramData%\\Qlik\\Sense\\Log")
#     + "\\qs-event-driven-cross-site-app-promoter\\"
# )

if not os.path.exists(LOG_LOCATION):
    os.makedirs(LOG_LOCATION)

LOG_FILE = LOG_LOCATION + "notification_creator.log"
LOG_BYTES = int(CONFIG["logging"]["notification_log_bytes"])
LOG_ROLLING_BACKUP = int(CONFIG["logging"]["notification_log_rolling_backup_num"])

LOGGER = logging.getLogger(__name__)
HANDLER = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=LOG_BYTES, backupCount=LOG_ROLLING_BACKUP
)

if LOG_LEVEL == "INFO":
    logging.basicConfig(level=logging.INFO)
    HANDLER.setLevel(logging.INFO)
else:
    logging.basicConfig(level=logging.DEBUG)
    HANDLER.setLevel(logging.DEBUG)

LOG_ID = str(uuid.uuid4())
STATUS = "Notifications"
FORMATTER = logging.Formatter(
    "%(asctime)s\t%(name)s\t%(levelname)s\t"
    + "%(process)d\t%(thread)d\t"
    + STATUS
    + "\t%(message)s"
)
HANDLER.setFormatter(FORMATTER)
LOGGER.addHandler(HANDLER)

NOTIFICATIONS = dict(
    {
        "notifications": [
            {
                "name": "AppUpdatePromote",
                "post_url": "/qrs/notification?name=app&changeType=update&xrfkey=abcdefg123456789",
                "listener_url": "http://{}:{}/app/update/promote".format(
                    LOCAL_SERVER, PORT
                ),
            },
            {
                "name": "AppPromoteOnReload",
                "post_url": "/qrs/notification?name=app&changeType=update&propertyName=lastReloadTime&xrfkey=abcdefg123456789",
                "listener_url": "http://{}:{}/app/update/reloaded".format(
                    LOCAL_SERVER, PORT
                ),
            },
            {
                "name": "AppPublishedToReviewStream",
                "post_url": "/qrs/notification?name=app&changeType=update&propertyName=publishTime&xrfkey=abcdefg123456789",
                "listener_url": "http://{}:{}/app/publish/review".format(
                    LOCAL_SERVER, PORT
                ),
            },
        ]
    }
)

while True:
    log_id = str(uuid.uuid4())
    try:
        s, base_url = qrs.establish_requests_session("local")

        for notification in NOTIFICATIONS["notifications"]:
            # create the notification
            data = notification["listener_url"]
            LOGGER.info("%s\tData: %s", log_id, data)
            post_url = notification["post_url"]
            full_url = BASE_URL + post_url
            LOGGER.info("%s\tPost URL: %s", log_id, full_url)

            r = s.post(full_url, json=data)

            LOGGER.info(
                "%s\tCreated\tStatus code: %s\tPost URL: %s\tResponse: %s",
                log_id,
                r.status_code,
                full_url,
                r.json(),
            )

        qrs.close_requests_session(s)
    except requests.exceptions.RequestException as error:
        LOGGER.error(
            "%s\tThe notifications cannot be created. "
            "The repository service is likely not fully operational: %s",
            log_id,
            error,
        )
    except ValueError as error:
        LOGGER.error(
            "%s\tValue Error received: %s. "
            "The repository service is likely in the boot process.",
            log_id,
            error,
        )

    time.sleep(60)
