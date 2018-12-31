"""
    This Configures the notifications within the QRS API
    which trigger actions on app change events and
    apps being published to approval streams
"""
import os
import logging
from logging.handlers import RotatingFileHandler
import json
import time
import csv
import urllib3
import requests
import Modules.qrs_functions as qrs

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
with open("CONFIG.json") as f:
    CONFIG = json.load(f)
    f.close()

# logging
LOG_LEVEL = CONFIG["log_level"]
PORT = CONFIG["port"]
USER_DIRECTORY = CONFIG["promote_on_custom_property_change"]["user_directory"]
USER_ID = CONFIG["promote_on_custom_property_change"]["user_id"]
QLIK_SHARE_LOCATION = CONFIG["qlik_share_location"]
LOCAL_SERVER = CONFIG["internal_central_node_IP"]

BASE_URL = "https://" + LOCAL_SERVER + ":4242"

LOG_LOCATION = QLIK_SHARE_LOCATION + "\\qs-event-driven-cross-site-app-promoter\\log\\"
if not os.path.exists(LOG_LOCATION):
    os.makedirs(LOG_LOCATION)

LOG_FILE = LOG_LOCATION + "notification_creator.log"
LOGGER = logging.getLogger(__name__)
# rolling logs with max 2 MB files with 3 backups
HANDLER = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=2000000, backupCount=3)

if LOG_LEVEL == "INFO":
    logging.basicConfig(level=logging.INFO)
    HANDLER.setLevel(logging.INFO)
else:
    logging.basicConfig(level=logging.DEBUG)
    HANDLER.setLevel(logging.DEBUG)
FORMATTER = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
HANDLER.setFormatter(FORMATTER)
LOGGER.addHandler(HANDLER)

# set headers
HEADERS = {
    "X-Qlik-Xrfkey":
    "abcdefg123456789",
    "X-Qlik-User":
    "UserDirectory=" + USER_DIRECTORY + ";UserId=" + USER_ID,
    "Content-Type":
    "application/json",
    "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36"
}

NOTIFICATIONS = dict({
    "notifications":
    [{
        "name": "AppUpdatePromote",
        "post_url": "/qrs/notification?name=app&changeType=update&xrfkey=abcdefg123456789",
        "listener_url": "http://{}:{}/app/update/promote".format(LOCAL_SERVER, PORT)
    },
     {
         "name":
         "AppPublishedToReviewStream",
         "post_url":
         "/qrs/notification?name=app&changeType=update&propertyName=publishTime&xrfkey=abcdefg123456789",
         "listener_url":
         "http://{}:{}/app/publish/review".format(LOCAL_SERVER, PORT)
     }]
})

while True:
    try:
        s, base_url = qrs.establish_requests_session("local")

        for notification in NOTIFICATIONS["notifications"]:
            # create the notification
            data = notification["listener_url"]
            LOGGER.info("Data: %s", data)
            post_url = notification["post_url"]
            full_url = BASE_URL + post_url
            LOGGER.info("Post URL: %s", full_url)

            r = s.post(full_url, json=data)

            LOGGER.info("Created    Status code: %s    Post URL: %s Response: %s",
                        r.status_code, full_url, r.json())

        qrs.close_requests_session(s)
    except requests.exceptions.RequestException as error:
        LOGGER.info(
            "The notifications cannot be created. "
            "The repository service is likely not fully operational: %s", error)
    except ValueError as error:
        LOGGER.info(
            "Value Error received: %s. "
            "The repository service is likely in the boot process.", error)

    time.sleep(60)
