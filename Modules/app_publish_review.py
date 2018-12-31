'''
Contains the function that triggers whenever an app is published 
to one of the streams that is set as an approval stream in
the QMC with a custom property='True' defined in the config.

Fires an email off to the associated addresses to any stream(s).
'''

import logging
from logging.handlers import RotatingFileHandler
import uuid
import os
import json
import csv
from pathlib import Path
import Modules.qrs_functions as qrs

# configuration file
with open("config.json") as f:
    CONFIG = json.load(f)
    f.close()

# logging
QLIK_SHARE_LOCATION = CONFIG["qlik_share_location"]
LOG_LEVEL = CONFIG["log_level"].lower()

LOG_LOCATION = QLIK_SHARE_LOCATION + \
    "\\qs-event-driven-cross-site-app-promoter\\log\\"
if not os.path.exists(LOG_LOCATION):
    os.makedirs(LOG_LOCATION)

LOG_FILE = LOG_LOCATION + "app_publish_review.log"

LOGGER = logging.getLogger(__name__)
# rolling logs with max 2 MB files with 3 backups
HANDLER = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=2000000, backupCount=3)

if LOG_LEVEL == "info":
    logging.basicConfig(level=logging.INFO)
else:
    logging.basicConfig(level=logging.DEBUG)

LOG_ID = str(uuid.uuid4())
APP_CHANGE_STATUS = "Initializing"
FORMATTER = logging.Formatter("%(asctime)s\t%(msecs)d\t%(name)s\t%(levelname)s\t" +
                              "%(process)d\t%(thread)d\t" + APP_CHANGE_STATUS + "\t%(message)s")
HANDLER.setFormatter(FORMATTER)
LOGGER.addHandler(HANDLER)

# additional config
PROMOTION_EMAIL_ALERTS = CONFIG["promote_on_custom_property_change"]["email_config"][
    "promotion_email_alerts"]
CUSTOM_PROPERTY_NAME_STREAM_ALERT_ON_PUBLISH = CONFIG["promote_on_custom_property_change"][
    "email_config"]["custom_property_name_stream_alert_on_publish"]
LOCAL_SERVER_FQDN = CONFIG[
    'promote_on_custom_property_change']['local_server_FQDN']
PROMOTION_SENDER_EMAIL = CONFIG["promote_on_custom_property_change"]["email_config"][
    "promotion_sender_email"]
PROMOTION_SENDER_PASS = CONFIG["promote_on_custom_property_change"]["email_config"][
    "promotion_sender_pass"]
PROMOTION_SMTP = CONFIG["promote_on_custom_property_change"]["email_config"][
    "promotion_SMTP"]
PROMOTION_SMTP_PORT = CONFIG["promote_on_custom_property_change"][
    "email_config"]["promotion_SMTP_port"]

# email alert config for app promotion
EMAIL_ALERTS = False
if PROMOTION_EMAIL_ALERTS.lower() == "true":
    try:
        import smtplib
        EMAIL_ALERTS = True

    except Exception as error:
        LOGGER.error(
            "%s\tSomething went wrong while trying to setup email alerts: %s", LOG_ID, error)
else:
    EMAIL_ALERTS = False

APP_CHANGE_STATUS = "app_published_gather_info"
FORMATTER = logging.Formatter("%(asctime)s\t%(msecs)d\t%(name)s\t%(levelname)s\t" +
                              "%(process)d\t%(thread)d\t" + APP_CHANGE_STATUS + "\t%(message)s")
HANDLER.setFormatter(FORMATTER)
LOGGER.addHandler(HANDLER)


def email_on_publish_to_review(app_id):
    '''
    Fires emails off to the addresses associated
    with the streams designated as approval streams
    once an app is published to one of them
    '''
    if EMAIL_ALERTS:
        log_id = str(uuid.uuid4())

        s, base_url = qrs.establish_requests_session("local")
        LOGGER.info("%s\tRequesting app/full info on '%s'", log_id, app_id)
        app_full_status, app_full_response = qrs.app_full(s, base_url, app_id)
        qrs.close_requests_session(s)
        if app_full_status != 200:
            LOGGER.error(
                "%s\tSomething went wrong while trying to get app/full: %s", log_id, app_full_status)
        else:
            LOGGER.debug("%s\tGot app/full data: %s", log_id, app_full_status)

        app_name = app_full_response["name"]
        LOGGER.info("%s\tApp Name: '%s'", log_id, app_name)

        app_owner = app_full_response["owner"]["userId"]
        app_owner_user_directory = app_full_response["owner"]["userDirectory"]
        app_owner = "{}\\{}".format(app_owner_user_directory, app_owner)
        LOGGER.info("%s\tApp Owner: '%s'", log_id, app_owner)
        modified_by_user = app_full_response["modifiedByUserName"]
        LOGGER.info("%s\tApp published by: '%s'", log_id, modified_by_user)

        stream_name = app_full_response["stream"]["name"]
        stream_id = app_full_response["stream"]["id"]
        LOGGER.info("%s\tPublished to stream Name: '%s'", log_id, stream_name)
        LOGGER.info("%s\tPublished to stream ID: '%s'", log_id, stream_id)

        LOGGER.info("%s\tChecking to see if the stream '%s' has the custom property '%s'",
                    log_id, stream_id, CUSTOM_PROPERTY_NAME_STREAM_ALERT_ON_PUBLISH)

        s, base_url = qrs.establish_requests_session("local")
        LOGGER.info("%s\tRequesting stream/full info on '%s'",
                    log_id, stream_id)
        stream_full_status, stream_full_response = qrs.stream_full(
            s, base_url, stream_id)
        qrs.close_requests_session(s)
        if stream_full_status != 200:
            LOGGER.error("%s\tSomething went wrong while trying to get stream/full: %s",
                         log_id, stream_full_status)
        else:
            LOGGER.debug("%s\tGot stream/full data: %s",
                         log_id, stream_full_status)

        stream_custom_properties = stream_full_response["customProperties"]
        LOGGER.debug("%s\tStream custom properties: %s",
                     log_id, stream_custom_properties)

        stream_marked_for_approval = False
        for stream_prop in stream_custom_properties:
            if stream_prop["definition"]["name"] == CUSTOM_PROPERTY_NAME_STREAM_ALERT_ON_PUBLISH:
                stream_marked_for_approval = True
                break

        if stream_marked_for_approval:
            app_change_status = "app_published_to_approval_stream"
            formatter = logging.Formatter("%(asctime)s\t%(msecs)d\t%(name)s\t%(levelname)s\t" +
                                          "%(process)d\t%(thread)d\t" + app_change_status + "\t%(message)s")
            HANDLER.setFormatter(formatter)
            LOGGER.addHandler(HANDLER)
            LOGGER.info(
                "%s\tApp published to approval stream: '%s', configuring email", log_id, stream_name)

            try:
                EMAIL_MAP_FILE_DIRECTORY = str(
                    Path(__file__).parent.parent).replace("\\", "/")
                EMAIL_MAP_FILE = EMAIL_MAP_FILE_DIRECTORY + \
                    '/ApprovalStreamsToEmailAddressMap.csv'
                EMAIL_MAP_STREAM_LIST = []
                EMAIL_MAP_ADDRESS_LIST = []

                with open(EMAIL_MAP_FILE) as email_map:
                    reader = csv.reader(email_map, delimiter=',')
                    next(reader, None)  # skip the header
                    for row in reader:
                        EMAIL_MAP_STREAM_LIST.append(row[0])
                        EMAIL_MAP_ADDRESS_LIST.append([row[0], row[1]])

                recipient_list = []
                for stream_to_email in EMAIL_MAP_ADDRESS_LIST:
                    if stream_id == stream_to_email[0]:
                        recipient_list.append(stream_to_email[1].strip())

                recipient_list = list(set(recipient_list))
                LOGGER.info("%s\tRecipient list: '%s'", log_id, recipient_list)

                subject = "'{}' published to: '{}'".format(
                    app_name, stream_name)
                body = """Application: '{}'\nOwned by: '{}'\nPublished by: '{}'\nPublished to: '{}'
                       \n\nView the app here: https://{}/sense/app/{}""".format(
                    app_name, app_owner, modified_by_user, stream_name, LOCAL_SERVER_FQDN, app_id)
                message = """From: %s\nTo: %s\nSubject: %s\n\n%s""" % (PROMOTION_SENDER_EMAIL, ", ".join(
                    recipient_list), subject, body)

                try:
                    server = smtplib.SMTP(PROMOTION_SMTP, PROMOTION_SMTP_PORT)
                    server.ehlo()
                    server.starttls()
                    server.login(PROMOTION_SENDER_EMAIL, PROMOTION_SENDER_PASS)
                    server.sendmail(PROMOTION_SENDER_EMAIL,
                                    recipient_list, message)
                    server.close()
                    LOGGER.info("%s\tSuccessfully sent the email to %s",
                                log_id,  recipient_list)
                except Exception as error:
                    LOGGER.error(
                        "%s\tThere was an error trying to send the email %s", log_id, error)

            except Exception as error:
                LOGGER.error(
                    "%s\tSomething went wrong with the email alerts: %s", log_id, error)
                LOGGER.error(
                    "%s\tEnsure you have filled out 'ApprovalStreamsToEmailAddressMap.csv' properly", log_id)
        else:
            LOGGER.info("%s\tStream '%s' with id '%s' does not contain the custom property '%s'. Exiting.",
                        log_id, stream_name, stream_id, CUSTOM_PROPERTY_NAME_STREAM_ALERT_ON_PUBLISH)

    return "Finished"
