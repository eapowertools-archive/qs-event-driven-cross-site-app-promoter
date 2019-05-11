import logging
from logging.handlers import RotatingFileHandler
import uuid
import os
from pathlib import Path
import json
import smtplib
import base64
import Modules.qrs_functions as qrs

# configuration file
with open("static/config.json") as f:
    CONFIG = json.load(f)
    f.close()

# logging
LOG_LEVEL = CONFIG["logging"]["log_level"].lower()

# LOG_LOCATION = (
#     os.path.expandvars("%ProgramData%\\Qlik\\Sense\\Log")
#     + "\\qs-event-driven-cross-site-app-promoter\\"
# )

LOG_LOCATION = str(Path(__file__).parent.parent).replace("\\", "/") + "/Log/"

if not os.path.exists(LOG_LOCATION):
    os.makedirs(LOG_LOCATION)

LOG_FILE = LOG_LOCATION + "approval_status_emailer.log"
LOG_BYTES = int(CONFIG["logging"]["other_logs_bytes"])
LOG_ROLLING_BACKUP = int(CONFIG["logging"]["other_logs_rolling_backup_num"])

LOGGER = logging.getLogger(__name__)
HANDLER = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=LOG_BYTES, backupCount=LOG_ROLLING_BACKUP
)

if LOG_LEVEL == "info":
    logging.basicConfig(level=logging.INFO)
else:
    logging.basicConfig(level=logging.DEBUG)

LOG_ID = str(uuid.uuid4())
APP_CHANGE_STATUS = "approval_email"
FORMATTER = logging.Formatter(
    "%(asctime)s\t%(name)s\t%(levelname)s\t"
    + "%(process)d\t%(thread)d\t"
    + APP_CHANGE_STATUS
    + "\t%(message)s"
)
HANDLER.setFormatter(FORMATTER)
LOGGER.addHandler(HANDLER)

PROMOTION_SENDER_EMAIL = CONFIG["promote_on_custom_property_change"]["email_config"][
    "promotion_sender_email"
]
PROMOTION_SENDER_PASS = CONFIG["promote_on_custom_property_change"]["email_config"][
    "promotion_sender_pass"
]
PROMOTION_SENDER_PASS_DECRYPTED = base64.b64decode(PROMOTION_SENDER_PASS).decode(
    "utf-8"
)
PROMOTION_SMTP = CONFIG["promote_on_custom_property_change"]["email_config"][
    "promotion_SMTP"
]
PROMOTION_SMTP_PORT = CONFIG["promote_on_custom_property_change"]["email_config"][
    "promotion_SMTP_port"
]


def email_approval_status(
    app_name,
    user_id,
    modified_by_user,
    stream_value_list,
    promote_server_value_list,
    approved=True,
):
    """
    Fires an email off whenever the custom property is changed on
    an app that is responsible for approving or denying an app's promotion
    """
    log_id = str(uuid.uuid4())

    s, base_url = qrs.establish_requests_session("local")
    LOGGER.info(
        "%s\tRequesting user info on '%s' who owns '%s'", log_id, user_id, app_name
    )
    user_full_Status, user_full_response = qrs.user_full(s, base_url, user_id)
    qrs.close_requests_session(s)

    user_directory = user_full_response["userDirectory"]
    user_id = user_full_response["userId"]
    user = user_directory + "\\" + user_id
    LOGGER.info("%s\tUser: '%s'", log_id, user)

    if user_full_Status != 200:
        LOGGER.error(
            "%s\tSomething went wrong while trying to get user/full: %s",
            log_id,
            user_full_Status,
        )
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
                app_name, modified_by_user
            )
            body = "Application: '{}' owned by: '{}' approved by: '{}'\nTarget Site(s): '{}'\nTarget Stream(s): '{}'".format(
                app_name,
                user,
                modified_by_user,
                [info["server_alias"] for info in promote_server_value_list],
                stream_value_list,
            )
            message = """From: %s\nTo: %s\nSubject: %s\n\n%s""" % (
                PROMOTION_SENDER_EMAIL,
                ", ".join(recipient_list),
                subject,
                body,
            )
        else:
            subject = "'{}' promotion denied by: '{}'".format(
                app_name, modified_by_user
            )
            body = "Application: '{}' owned by: '{}' denied by: '{}'".format(
                app_name, user, modified_by_user
            )
            message = """From: %s\nTo: %s\nSubject: %s\n\n%s""" % (
                PROMOTION_SENDER_EMAIL,
                ", ".join(recipient_list),
                subject,
                body,
            )
        try:
            server = smtplib.SMTP(PROMOTION_SMTP, PROMOTION_SMTP_PORT)
            server.ehlo()
            server.starttls()
            server.login(PROMOTION_SENDER_EMAIL, PROMOTION_SENDER_PASS_DECRYPTED)
            server.sendmail(PROMOTION_SENDER_EMAIL, recipient_list, message)
            server.close()
            LOGGER.info("%s\tSuccessfully sent the email to %s", log_id, recipient_list)
            return "Successfully sent the email to: '{}'".format(recipient_list)
        except Exception as error:
            LOGGER.error(
                "%s\tThere was an error trying to send the email %s", log_id, error
            )
            return "There was an error trying to send the email: '{}'".format(error)
    else:
        LOGGER.warning("%s\tUser email not found. Exiting.", log_id)
        return "User email not found. No action taken."


def email_promotion_results(
    app_name, user_id, modified_by_user, promotion_results, streams_not_found
):
    """
    Fires an email off to the app owner with the promotion results
    """
    log_id = str(uuid.uuid4())

    s, base_url = qrs.establish_requests_session("local")
    LOGGER.info(
        "%s\tRequesting user info on '%s' who owns '%s'", log_id, user_id, app_name
    )
    user_full_Status, user_full_response = qrs.user_full(s, base_url, user_id)
    qrs.close_requests_session(s)

    user_directory = user_full_response["userDirectory"]
    user_id = user_full_response["userId"]
    user = user_directory + "\\" + user_id
    LOGGER.info("%s\tUser: '%s'", log_id, user)

    if user_full_Status != 200:
        LOGGER.error(
            "%s\tSomething went wrong while trying to get user/full: %s",
            log_id,
            user_full_Status,
        )
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
        subject = "'{}' promotion results".format(app_name)
        body = "Application: '{}' has been promoted!\n\n".format(app_name)

        body += "Succesfully promoted the following apps:\n\n"
        for promotion in promotion_results:
            alias = promotion["remote_server_alias"]
            app_id = promotion["remote_app_id"]
            stream_name = promotion["remote_stream_name"]
            fqdn = promotion["remote_server_fqdn"]

            body += "Successfully deployed to server with alias: '{}'\n".format(alias)
            body += "Successfully deployed to server: '{}'\n".format(fqdn)
            body += "Successfully deployed to stream: '{}'\n".format(stream_name)
            body += "New app id: '{}'\n".format(app_id)
            application_url = "https://" + fqdn + "/sense/app/" + app_id
            body += "Application url: '{}'\n\n".format(application_url)

        if len(streams_not_found) >= 1:
            body += "\nStreams not found:\n\n"

            for promotion_failure in streams_not_found:
                stream_name = promotion_failure[0]
                alias = promotion_failure[1]["server_alias"]
                fqdn = promotion_failure[1]["server"]
                body += "Stream '{}' not found on server '{}' with alias '{}'\n".format(
                    stream_name, fqdn, alias
                )

        message = """From: %s\nTo: %s\nSubject: %s\n\n%s""" % (
            PROMOTION_SENDER_EMAIL,
            ", ".join(recipient_list),
            subject,
            body,
        )
        try:
            server = smtplib.SMTP(PROMOTION_SMTP, PROMOTION_SMTP_PORT)
            server.ehlo()
            server.starttls()
            server.login(PROMOTION_SENDER_EMAIL, PROMOTION_SENDER_PASS_DECRYPTED)
            server.sendmail(PROMOTION_SENDER_EMAIL, recipient_list, message)
            server.close()
            LOGGER.info("%s\tSuccessfully sent the email to %s", log_id, recipient_list)
            return "Successfully sent the email to: '{}'".format(recipient_list)
        except Exception as error:
            LOGGER.error(
                "%s\tThere was an error trying to send the email %s", log_id, error
            )
            return "There was an error trying to send the email: '{}'".format(error)
    else:
        LOGGER.warning("%s\tUser email not found. Exiting.", log_id)
        return "User email not found. No action taken."
