import logging
from logging.handlers import RotatingFileHandler
import uuid
import os
import json
import smtplib
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

LOG_FILE = LOG_LOCATION + "approval_status_emailer.log"

LOGGER = logging.getLogger(__name__)
# rolling logs with max 2 MB files with 3 backups
HANDLER = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=2000000, backupCount=3)

if LOG_LEVEL == "info":
    logging.basicConfig(level=logging.INFO)
else:
    logging.basicConfig(level=logging.DEBUG)

LOG_ID = str(uuid.uuid4())
APP_CHANGE_STATUS = "app_published_gather_info"
FORMATTER = logging.Formatter("%(asctime)s\t%(msecs)d\t%(name)s\t%(levelname)s\t" +
                              "%(process)d\t%(thread)d\t" + APP_CHANGE_STATUS + "\t%(message)s")
HANDLER.setFormatter(FORMATTER)
LOGGER.addHandler(HANDLER)

PROMOTION_SENDER_EMAIL = CONFIG["promote_on_custom_property_change"]["email_config"][
    "promotion_sender_email"]
PROMOTION_SENDER_PASS = CONFIG["promote_on_custom_property_change"]["email_config"][
    "promotion_sender_pass"]
PROMOTION_SMTP = CONFIG["promote_on_custom_property_change"]["email_config"][
    "promotion_SMTP"]
PROMOTION_SMTP_PORT = CONFIG["promote_on_custom_property_change"]["email_config"][
    "promotion_SMTP_port"]


def email_approval_status(app_name, user_id, modified_by_user, approved=True):
    '''
    Fires an email off whenever the custom property is changed on
    an app that is responsible for approving or denying an app's promotion
    '''
    log_id = str(uuid.uuid4())

    s, base_url = qrs.establish_requests_session("local")
    LOGGER.info("%s\tRequesting user info on '%s' who owns '%s'",
                log_id, user_id, app_name)
    user_full_Status, user_full_response = qrs.user_full(s, base_url, user_id)
    qrs.close_requests_session(s)

    owner_name = user_full_response["name"]

    if user_full_Status != 200:
        LOGGER.error(
            "%s\tSomething went wrong while trying to get user/full: %s", log_id, user_full_Status)
    else:
        LOGGER.debug("%s\tGot user/full data: %s", log_id, user_full_Status)

    user_email_found = False
    for attribute in user_full_response["attributes"]:
        if attribute["attributeType"].lower() == "email":
            user_email = attribute["attributeValue"]
            recipient_list = [user_email]
            LOGGER.info("%s\tUser email found: '%s'", log_id, user_email)
            user_email_found = True
            break

    if user_email_found:
        if approved:
            subject = "'{}' promotion approved by: '{}'".format(
                app_name, modified_by_user)
            body = "Application: '{}' owned by: '{}' approved by: '{}'".format(
                app_name, owner_name, modified_by_user)
            message = """From: %s\nTo: %s\nSubject: %s\n\n%s""" % (PROMOTION_SENDER_EMAIL, ", ".join(
                recipient_list), subject, body)
        else:
            subject = "'{}' promotion denied by: '{}'".format(
                app_name, modified_by_user)
            body = "Application: '{}' owned by: '{}' denied by: '{}'".format(
                app_name, owner_name, modified_by_user)
            message = """From: %s\nTo: %s\nSubject: %s\n\n%s""" % (PROMOTION_SENDER_EMAIL, ", ".join(
                recipient_list), subject, body)
        try:
            server = smtplib.SMTP(PROMOTION_SMTP, PROMOTION_SMTP_PORT)
            server.ehlo()
            server.starttls()
            server.login(PROMOTION_SENDER_EMAIL, PROMOTION_SENDER_PASS)
            server.sendmail(PROMOTION_SENDER_EMAIL, recipient_list, message)
            server.close()
            LOGGER.info("%s\tSuccessfully sent the email to %s",
                        log_id,  recipient_list)
            return "Successfully sent the email to: '{}'".format(recipient_list)
        except Exception as error:
            LOGGER.error(
                "%s\tThere was an error trying to send the email %s", log_id, error)
            return "There was an error trying to send the email: '{}'".format(error)
    else:
        LOGGER.info("%s\tUser email not found. Exiting.")
        return "User email not found. No action taken."
