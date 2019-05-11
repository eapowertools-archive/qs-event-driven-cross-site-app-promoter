"""
Contains the function that is triggered on any app update.
This function is responsible for checking an app's custom
properties and promoting it to another server if certain
criteria has been met.
"""

import logging
from logging.handlers import RotatingFileHandler
import os
import json
from pathlib import Path
import uuid
import Modules.qrs_functions as qrs
import Modules.mailer as mailer

# configuration file
with open("static/config.json") as f:
    CONFIG = json.load(f)
    f.close()

# logging
LOG_LEVEL = CONFIG["logging"]["log_level"].lower()
LOGGER = logging.getLogger(__name__)

LOG_LOCATION = str(Path(__file__).parent.parent).replace("\\", "/") + "/Log/"

# LOG_LOCATION = (
#     os.path.expandvars("%ProgramData%\\Qlik\\Sense\\Log")
#     + "\\qs-event-driven-cross-site-app-promoter\\"
# )

if not os.path.exists(LOG_LOCATION):
    os.makedirs(LOG_LOCATION)

LOG_FILE = LOG_LOCATION + "app_update.log"
LOG_BYTES = int(CONFIG["logging"]["other_logs_bytes"])
LOG_ROLLING_BACKUP = int(CONFIG["logging"]["other_logs_rolling_backup_num"])

HANDLER = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=LOG_BYTES, backupCount=LOG_ROLLING_BACKUP
)

if LOG_LEVEL == "info":
    logging.basicConfig(level=logging.INFO)
else:
    logging.basicConfig(level=logging.DEBUG)

APP_CHANGE_ID = str(uuid.uuid4())
APP_CHANGE_STATUS = "Initializing"
FORMATTER = logging.Formatter(
    "%(asctime)s\t%(name)s\t%(levelname)s\t"
    + "%(process)d\t%(thread)d\t"
    + APP_CHANGE_STATUS
    + "\t%(message)s"
)
HANDLER.setFormatter(FORMATTER)
LOGGER.addHandler(HANDLER)
LOG_ID = str(uuid.uuid4())

# additional config
CUSTOM_PROPERTY_NAME_PROMOTE = CONFIG["promote_on_custom_property_change"][
    "custom_property_name_promote"
]
CUSTOM_PROPERTY_NAME_PROMOTE_STREAM = CONFIG["promote_on_custom_property_change"][
    "custom_property_name_promote_stream"
]
CUSTOM_PROPERTY_NAME_PROMOTE_APPROVAL = CONFIG["promote_on_custom_property_change"][
    "custom_property_name_promote_approval"
]
VERSIONING_CUSTOM_PROP_NAME = CONFIG["promote_on_custom_property_change"][
    "app_version_on_change"
]["custom_property_name"]
REMOTE_SERVERS = CONFIG["promote_on_custom_property_change"]["remote_servers"]
REMOTE_SERVER_ALIASES = [server["server_alias"].lower() for server in REMOTE_SERVERS]
AUTO_UNPUBLISH_ON_APPROVE_OR_DENY = CONFIG["promote_on_custom_property_change"][
    "auto_unpublish_on_approve_or_deny"
]["auto_unpublish"]
UNPUBLISH_CUSTOM_PROP_NAME = CONFIG["promote_on_custom_property_change"][
    "auto_unpublish_on_approve_or_deny"
]["custom_property_name"]
PROMOTE_ON_RELOAD = CONFIG["promote_on_reload"]["enabled"]
CUSTOM_PROPERTY_NAME_PROMOTE_ON_RELOAD = CONFIG["promote_on_reload"][
    "custom_property_name"
]
PROMOTE_ON_RELOAD_TAG_NAME = CONFIG["promote_on_reload"]["tag_name"]

AUTO_UNPUBLISH = False
if AUTO_UNPUBLISH_ON_APPROVE_OR_DENY == "true":
    AUTO_UNPUBLISH = True

if PROMOTE_ON_RELOAD == "true":
    PROMOTE_ON_RELOAD = True
else:
    PROMOTE_ON_RELOAD = False

# check for versioning
APP_VERSION_ON_CHANGE = CONFIG["promote_on_custom_property_change"][
    "app_version_on_change"
]["enabled"].lower()

AUTO_VERSION = CONFIG["promote_on_custom_property_change"]["app_version_on_change"][
    "auto_version_on_promote"
].lower()

if APP_VERSION_ON_CHANGE == "true":
    S3_BUCKET = CONFIG["promote_on_custom_property_change"]["app_version_on_change"][
        "s3_bucket"
    ]
    S3_PREFIX = CONFIG["promote_on_custom_property_change"]["app_version_on_change"][
        "prefix"
    ]
    AUTO_VERSION = CONFIG["promote_on_custom_property_change"]["app_version_on_change"][
        "auto_version_on_promote"
    ].lower()
    if AUTO_VERSION == "true":
        AUTO_VERSIONING = True

    try:
        import boto3
        from boto3.s3.transfer import S3Transfer
        import threading

        APP_VERSIONING = True
        # get the file path for the ExportedApps/ dir for later use
        EXPORTED_APP_DIRECTORY = (
            str(Path(__file__).parent.parent).replace("\\", "/") + "/ExportedApps/"
        )
    except ImportError:
        APP_VERSIONING = False
        LOGGER.error(
            "%s\tCould not import 'boto3' library which is used with s3. "
            "Please install the boto library for versioning to be enabled",
            LOG_ID,
        )
else:
    APP_VERSIONING = False
    AUTO_VERSIONING = False

PROMOTION_EMAIL_ALERTS = CONFIG["promote_on_custom_property_change"]["email_config"][
    "promotion_email_alerts"
].lower()
EMAIL_UDC_ATTRIBUTE_EXISTS = CONFIG["promote_on_custom_property_change"][
    "email_config"
]["email_UDC_attribute_exists"].lower()

SEND_EMAIL_ON_APPROVAL_STATUS = False
if PROMOTION_EMAIL_ALERTS == "true" and EMAIL_UDC_ATTRIBUTE_EXISTS == "true":
    SEND_EMAIL_ON_APPROVAL_STATUS = True

PROP_LIST = [
    CUSTOM_PROPERTY_NAME_PROMOTE,
    CUSTOM_PROPERTY_NAME_PROMOTE_STREAM,
    CUSTOM_PROPERTY_NAME_PROMOTE_APPROVAL,
    VERSIONING_CUSTOM_PROP_NAME,
    UNPUBLISH_CUSTOM_PROP_NAME,
]

APP_CHANGE_STATUS = "app_update"
FORMATTER = logging.Formatter(
    "%(asctime)s\t%(name)s\t%(levelname)s\t"
    + "%(process)d\t%(thread)d\t"
    + APP_CHANGE_STATUS
    + "\t%(message)s"
)
HANDLER.setFormatter(FORMATTER)
LOGGER.addHandler(HANDLER)


def promote_app(trigger_type, app_id, originator_node_id, originator_host_name):
    """
    Triggers every time an app is updated
    """

    met_criteria = False
    app_promoted = False

    log_id = str(uuid.uuid4())
    LOGGER.info("%s\t_____________App Updated_____________", log_id)
    LOGGER.info("%s\tTrigger type: '%s'", log_id, trigger_type)
    LOGGER.info("%s\tOriginator Node HostName: '%s'", log_id, originator_host_name)
    LOGGER.info("%s\tOriginator Node ID: '%s'", log_id, originator_node_id)

    s, base_url = qrs.establish_requests_session("local")
    LOGGER.info("%s\tRequesting app/full info on '%s'", log_id, app_id)
    app_full_status, app_full_response = qrs.app_full(s, base_url, app_id)
    qrs.close_requests_session(s)
    if app_full_status != 200:
        LOGGER.error(
            "%s\tSomething went wrong while trying to get app/full: %s",
            log_id,
            app_full_status,
        )
    else:
        LOGGER.debug("%s\tGot app/full data: %s", log_id, app_full_status)

    app_name = app_full_response["name"]
    LOGGER.info("%s\tApp Name: '%s'", log_id, app_name)

    app_owner_id = app_full_response["owner"]["id"]
    app_owner = app_full_response["owner"]["userId"]
    app_owner_user_directory = app_full_response["owner"]["userDirectory"]
    app_owner = "{}\\{}".format(app_owner_user_directory, app_owner)
    modified_by_user = app_full_response["modifiedByUserName"]
    modified_date = app_full_response["modifiedDate"]
    tags = app_full_response["tags"]

    # check to see if the app is tagged as auto-promote on reload
    app_tagged_auto_reload = False
    if PROMOTE_ON_RELOAD:
        for tag in tags:
            if tag["name"] == PROMOTE_ON_RELOAD_TAG_NAME:
                app_tagged_auto_reload = True

    # set the description that will be applied to promoted apps
    description = "App promoted from node: '{}' by: '{}' at: '{}' where it was owned by: '{}'".format(
        originator_host_name, modified_by_user, modified_date, app_owner
    )
    LOGGER.info(
        "%s\tApp updated on node: '%s' modified by: '%s' owned by: '%s'",
        log_id,
        originator_host_name,
        modified_by_user,
        app_owner,
    )

    app_num_custom_properties = len(app_full_response["customProperties"])
    LOGGER.info(
        "%s\tApp Number of Custom Properties: '%s'", log_id, app_num_custom_properties
    )

    # if the app is not published, no action will be taken
    LOGGER.info("%s\tChecking to see if app is published", log_id)

    app_is_published = app_full_response["published"]
    if app_is_published:
        LOGGER.info("%s\tApp is published", log_id)
    else:
        LOGGER.info("%s\tApp is not published.", log_id)

    promote_on_reload_value_true = False
    if app_num_custom_properties >= 1 and app_is_published:
        promote_custom_prop_found = False
        promote_stream_custom_prop_found = False
        promotion_approved = False
        promotion_approval_empty = True
        promotion_approval_bad_input = False
        app_versioning_value_true = False
        unpublish_app_custom_prop_found = False
        unpublish_app_value_true = False
        send_approval_email = False

        LOGGER.info(
            "%s\tSearching app/full to see if '%s' and/or '%s' custom properties exist",
            log_id,
            CUSTOM_PROPERTY_NAME_PROMOTE,
            CUSTOM_PROPERTY_NAME_PROMOTE_STREAM,
        )
        promote_server_value_list = []
        stream_value_list = []
        custom_prop_version_value_count = 0
        for custom_prop in app_full_response["customProperties"]:
            if custom_prop["definition"]["name"] == CUSTOM_PROPERTY_NAME_PROMOTE:
                promote_raw_value = custom_prop["value"].lower()
                if "-" in custom_prop["value"]:
                    server_alias = custom_prop["value"].split("-")[0].strip().lower()
                    if server_alias in REMOTE_SERVER_ALIASES:
                        for server in REMOTE_SERVERS:
                            if server["server_alias"].lower() == server_alias:
                                server_fqdn = server["remote_server"]
                                promote_server_value_list.append(
                                    {
                                        "server_alias": server_alias,
                                        "server": server_fqdn,
                                        "value": promote_raw_value,
                                    }
                                )
                        LOGGER.info(
                            "%s\tMandatory custom property '%s' exists with the value of: '%s', which maps to: '%s'",
                            log_id,
                            CUSTOM_PROPERTY_NAME_PROMOTE,
                            server_alias,
                            server_fqdn,
                        )
                        promote_custom_prop_found = True
                    else:
                        LOGGER.error(
                            "%s\tAlias '%s' not found in listed aliases '%s'",
                            log_id,
                            server_alias,
                            REMOTE_SERVER_ALIASES,
                        )
                else:
                    LOGGER.error(
                        "%s\tAlias and 'duplicate' or 'overwrite' must be separated by the '-' character, such as 'Test - Overwrite'",
                        log_id,
                    )
            elif (
                custom_prop["definition"]["name"] == CUSTOM_PROPERTY_NAME_PROMOTE_STREAM
            ):
                promote_stream_value = custom_prop["value"]
                LOGGER.info(
                    "%s\tMandatory custom property '%s' exists with the value of: '%s'",
                    log_id,
                    CUSTOM_PROPERTY_NAME_PROMOTE_STREAM,
                    promote_stream_value,
                )
                promote_stream_custom_prop_found = True
                stream_value_list.append(promote_stream_value)
            elif (
                custom_prop["definition"]["name"]
                == CUSTOM_PROPERTY_NAME_PROMOTE_ON_RELOAD
            ):
                if PROMOTE_ON_RELOAD:
                    promote_on_reload_value = custom_prop["value"].lower()
                    LOGGER.info(
                        "%s\tAuto promote on reload custom property '%s' with the value of: '%s'",
                        log_id,
                        CUSTOM_PROPERTY_NAME_PROMOTE_ON_RELOAD,
                        promote_on_reload_value,
                    )
                    if promote_on_reload_value == "true":
                        LOGGER.info(
                            "%s\tThe custom property '%s' is found with the value 'True' (case insenstive). The app will attempt to be auto-promoted on reloads.",
                            log_id,
                            CUSTOM_PROPERTY_NAME_PROMOTE_ON_RELOAD,
                        )
                        promote_on_reload_value_true = True
                    else:
                        LOGGER.warning(
                            "%s\tAuto-promotion on reloads is enabled however the value 'True' is not found. The app will not be auto-promoted on reloads.",
                            log_id,
                        )
                else:
                    LOGGER.warning(
                        "%s\tAuto-promotion on reloads is disabled, however the promote on reload custom property '%s' is found. The app will not be auto-promoted on reloads.",
                        log_id,
                        CUSTOM_PROPERTY_NAME_PROMOTE,
                    )
            elif (
                custom_prop["definition"]["name"]
                == CUSTOM_PROPERTY_NAME_PROMOTE_APPROVAL
                and not promote_on_reload_value_true
            ):
                promotion_approval_empty = False
                promote_approval_value = custom_prop["value"]
                LOGGER.info(
                    "%s\tMandatory custom property '%s' exists with the value of: '%s'",
                    log_id,
                    CUSTOM_PROPERTY_NAME_PROMOTE_APPROVAL,
                    promote_approval_value,
                )
                if "approve" in promote_approval_value.lower():
                    LOGGER.info(
                        "%s\tApp versioning custom property '%s' with the value of: '%s'",
                        log_id,
                        CUSTOM_PROPERTY_NAME_PROMOTE_APPROVAL,
                        promote_approval_value,
                    )
                    promotion_approved = True
                    LOGGER.info(
                        "%s\tPromotion has been approved by: '%s'",
                        log_id,
                        modified_by_user,
                    )
                    if SEND_EMAIL_ON_APPROVAL_STATUS:
                        send_approval_email = True
                elif "den" in promote_approval_value.lower():
                    LOGGER.info(
                        "%s\tPromotion has been denied by: '%s'",
                        log_id,
                        modified_by_user,
                    )
                    if SEND_EMAIL_ON_APPROVAL_STATUS:
                        LOGGER.info("%s\tAttempting to send denial email", log_id)
                        email_approval_status_response = mailer.email_approval_status(
                            app_name,
                            app_owner_id,
                            modified_by_user,
                            None,
                            None,
                            approved=False,
                        )
                        LOGGER.info(
                            "%s\tEmail response: '%s'",
                            log_id,
                            email_approval_status_response,
                        )
                else:
                    LOGGER.info(
                        "%s\tThis app will not be promoted as the approval value does not contain 'approve' or 'den'.",
                        log_id,
                    )
                    promotion_approval_bad_input = True
            elif custom_prop["definition"]["name"] == UNPUBLISH_CUSTOM_PROP_NAME:
                unpublish_app_custom_prop_found = True
                custom_prop_unpublish_value = custom_prop["value"].lower()
                if AUTO_UNPUBLISH:
                    LOGGER.warning(
                        "%s\tThe custom property '%s' is found but the config file has the unpublish set to auto. This custom property will have no impact.",
                        log_id,
                        UNPUBLISH_CUSTOM_PROP_NAME,
                    )
                else:
                    if "true" in custom_prop_unpublish_value:
                        LOGGER.info(
                            "%s\tThe custom property '%s' is found with the value 'True' (case insenstive). The app will be unpublished on successful approval or denial.",
                            log_id,
                            UNPUBLISH_CUSTOM_PROP_NAME,
                        )
                        unpublish_app_value_true = True
                    else:
                        LOGGER.warning(
                            "%s\tThe custom property '%s' is found with the value '%s'. The value must be set to 'True' (case insensitive) for this custom property to be leveraged",
                            log_id,
                            UNPUBLISH_CUSTOM_PROP_NAME,
                            custom_prop_unpublish_value,
                        )
            elif APP_VERSIONING and APP_VERSION_ON_CHANGE == "true":
                if custom_prop["definition"]["name"] == VERSIONING_CUSTOM_PROP_NAME:
                    custom_prop_version_value_count += 1
                    versioning_custom_prop_value = custom_prop["value"].lower()
                    if versioning_custom_prop_value == "true":
                        LOGGER.info(
                            "%s\tApp versioning custom property '%s' with the value of: '%s'",
                            log_id,
                            VERSIONING_CUSTOM_PROP_NAME,
                            versioning_custom_prop_value,
                        )
                        app_versioning_value_true = True
                    elif custom_prop_version_value_count == 1:
                        LOGGER.warning(
                            "%s\tThis app will not be versioned as the value must be set to 'True' (case insensitive)",
                            log_id,
                        )
            elif custom_prop["definition"]["name"] == VERSIONING_CUSTOM_PROP_NAME:
                LOGGER.info(
                    "%s\tVersioning is not enabled though the custom property '%s' is found. No action taken.",
                    log_id,
                    VERSIONING_CUSTOM_PROP_NAME,
                )

        if not AUTO_UNPUBLISH and not unpublish_app_custom_prop_found:
            LOGGER.warning(
                "%s\tAuto unpublish is not enabled and the custom property '%s' is not found. The app will not be unpublished.",
                log_id,
                UNPUBLISH_CUSTOM_PROP_NAME,
            )

        if (
            not app_tagged_auto_reload
            and promote_on_reload_value_true
            and promote_custom_prop_found
            and promote_stream_custom_prop_found
        ):
            s, base_url = qrs.establish_requests_session("local")
            LOGGER.info(
                "%s\tTagging app '%s' with tag named '%s'",
                log_id,
                app_name,
                PROMOTE_ON_RELOAD_TAG_NAME,
            )
            add_tag_status = qrs.add_tag_to_app(
                s, base_url, app_id, PROMOTE_ON_RELOAD_TAG_NAME
            )
            qrs.close_requests_session(s)
            if add_tag_status != 200:
                LOGGER.error(
                    "%s\tSomething went wrong while trying to add the tag to the app: '%s'",
                    log_id,
                    add_tag_status,
                )
            else:
                LOGGER.debug("%s\tTag added: '%s'", log_id, add_tag_status)
        elif (
            not app_tagged_auto_reload
            and promote_on_reload_value_true
            and promote_custom_prop_found
        ):
            LOGGER.info(
                "%s\tApp is missing a valid target stream value so will not be tagged for auto-promotion.",
                log_id,
            )
        elif (
            not app_tagged_auto_reload
            and promote_on_reload_value_true
            and promote_stream_custom_prop_found
        ):
            LOGGER.info(
                "%s\tApp is missing a valid target server value so will not be tagged for auto-promotion.",
                log_id,
            )
        elif not app_tagged_auto_reload and promote_on_reload_value_true:
            LOGGER.info(
                "%s\tApp is missing a valid target server and stream values so will not be tagged for auto-promotion.",
                log_id,
            )
        elif app_tagged_auto_reload:
            LOGGER.info("%s\tApp tagged for auto-promote on reloads already.", log_id)
        if (
            promotion_approved
            and promote_custom_prop_found
            and promote_stream_custom_prop_found
            and trigger_type == "updated"
            and not promote_on_reload_value_true
        ) or (
            promote_on_reload_value_true
            and promote_custom_prop_found
            and promote_stream_custom_prop_found
            and trigger_type == "reloaded"
        ):

            met_criteria = True

            LOGGER.info(
                "%s\tMandatory custom properties have values, proceeding", log_id
            )

            LOGGER.info("%s\tAttempting to send approval email", log_id)
            if send_approval_email and trigger_type=="updated":
                email_approval_status_response = mailer.email_approval_status(
                    app_name,
                    app_owner_id,
                    modified_by_user,
                    stream_value_list,
                    promote_server_value_list,
                )
                LOGGER.info(
                    "%s\tEmail response: '%s'", log_id, email_approval_status_response
                )

            target_remote_servers = len(promote_server_value_list)
            target_remote_server_tracker = 0
            already_versioned = False
            promotion_results = []
            streams_not_found = []
            for server in promote_server_value_list:
                log_id_server = log_id + '|' + server["server_alias"]
                target_remote_server_tracker += 1
                alias = server["server_alias"]
                # lookup all of the streams by name to see if they are valid
                stream_id_list = []
                matching_stream_list = []
                final_id_list = []

                i = -1
                s, base_url = qrs.establish_requests_session(alias)
                LOGGER.info(
                    "%s\tGetting Stream IDs from remote server by name for streams: '%s'",
                    log_id_server,
                    stream_value_list,
                )
                for stream in stream_value_list:
                    i += 1

                    stream_id_status, stream_id = qrs.get_remote_stream_id_by_name(
                        s, base_url, stream
                    )
                    if stream_id_status != 200:
                        LOGGER.error(
                            "%s\tSomething went wrong while trying to get the ID for stream: '%s'",
                            log_id_server,
                            stream,
                        )
                        LOGGER.error("%s\tStatus: '%s'", log_id_server, stream_id_status)
                        LOGGER.debug(
                            "%s\tGet stream ID call status: '%s'",
                            log_id_server,
                            stream_id_status,
                        )
                    if stream_id != None:
                        matching_stream_list.append(stream_value_list[i])
                        stream_id_list.append([stream_id, stream])
                        LOGGER.info(
                            "%s\tStream found: '%s'", log_id_server, stream_value_list[i]
                        )
                    else:
                        streams_not_found.append([stream_value_list[i], server])
                        LOGGER.warning(
                            "%s\tStream not found: '%s'", log_id_server, stream_value_list[i]
                        )

                qrs.close_requests_session(s)
                LOGGER.info(
                    "%s\tStream ID List: '%s'",
                    log_id_server,
                    [stream[0] for stream in stream_id_list],
                )
                stream_existing_count = len(matching_stream_list)

                if stream_existing_count >= 1 and (
                    "overwrite" in server["value"] or "duplicate" in server["value"]
                ):

                    if target_remote_server_tracker == 1:
                        s, base_url = qrs.establish_requests_session("local")
                        LOGGER.info("%s\tExporting local app", log_id_server)
                        export_app_status = qrs.export_app(
                            s, base_url, app_id, app_name
                        )
                        qrs.close_requests_session(s)
                        if export_app_status != 200:
                            LOGGER.error(
                                "%s\tSomething went wrong while trying to export the app: '%s'",
                                log_id_server,
                                export_app_status,
                            )
                        else:
                            LOGGER.debug(
                                "%s\tApp exported: '%s'", log_id_server, export_app_status
                            )

                    if "overwrite" in server["value"] and stream_existing_count >= 1:
                        LOGGER.info(
                            "%s\tApps that exist with the same name in target streams will be overwritten. If they do not exist, they will be created.",
                            log_id_server,
                        )
                        s, base_url = qrs.establish_requests_session(alias)
                        LOGGER.info(
                            "%s\tLooking up app IDs to be overwritten on the remote server by name",
                            log_id_server,
                        )
                        remote_app_id_status, remote_app_id_json = qrs.get_remote_app_ids_by_name(
                            s, base_url, app_name
                        )
                        num_remote_app_ids = len(remote_app_id_json)

                        if remote_app_id_status != 200:
                            LOGGER.error(
                                "%s\tSomething went wrong when looking up apps by name: '%s'",
                                log_id_server,
                                remote_app_id_status,
                            )
                        else:
                            LOGGER.debug(
                                "%s\tCall to look up apps status: '%s'",
                                log_id_server,
                                remote_app_id_status,
                            )

                        LOGGER.info(
                            "%s\tApp IDs found with matching names: '%s'",
                            log_id_server,
                            num_remote_app_ids,
                        )

                        remote_app_detail_list = []
                        matching_app_ids = []
                        matching_published_app_ids = []
                        num_remote_found_target_published = 0
                        if num_remote_app_ids >= 1:
                            for app in remote_app_id_json:
                                remote_app_id = app["id"]
                                matching_app_ids.append(remote_app_id)
                                remote_app_published = app["published"]
                                if remote_app_published:
                                    remote_stream_id = app["stream"]["id"]
                                    remote_stream_name = app["stream"]["name"]

                                    for sid in stream_id_list:
                                        if sid[0] == remote_stream_id:
                                            matching_published_app_ids.append(
                                                remote_app_id
                                            )
                                            remote_app_detail_list.append(
                                                {
                                                    "app_id": remote_app_id,
                                                    "published": remote_app_published,
                                                    "stream_id": remote_stream_id,
                                                    "stream_name": remote_stream_name,
                                                }
                                            )

                            qrs.close_requests_session(s)
                            num_remote_found_target_published = len(
                                remote_app_detail_list
                            )

                            LOGGER.info(
                                "%s\tMatching App IDs: '%s'", log_id_server, matching_app_ids
                            )
                            LOGGER.info(
                                "%s\tMatching apps with matching names that are published to target streams: '%s'",
                                log_id_server,
                                matching_published_app_ids,
                            )
                            LOGGER.debug(
                                "%s\tApp info: '%s'", log_id_server, remote_app_detail_list
                            )

                        left_over_stream_id_list = stream_id_list
                        if num_remote_found_target_published >= 1:
                            s, base_url = qrs.establish_requests_session(alias)
                            LOGGER.info(
                                "%s\tUploading app onto remote server and getting the new ID",
                                log_id_server,
                            )
                            upload_app_status, new_app_id = qrs.upload_app(
                                s, base_url, app_name
                            )
                            if upload_app_status != 201:
                                LOGGER.error(
                                    "%s\tSomething went wrong while trying to upload the app: '%s'",
                                    log_id_server,
                                    upload_app_status,
                                )
                            else:
                                LOGGER.debug(
                                    "%s\tApp uploaded: '%s'", log_id_server, upload_app_status
                                )
                            qrs.close_requests_session(s)

                            s, base_url = qrs.establish_requests_session(alias)
                            LOGGER.info(
                                "%s\tOverwriting existing apps with matching names published to target streams",
                                log_id_server,
                            )
                            for remote_app_id in remote_app_detail_list:
                                app_replaced_status = qrs.app_replace(
                                    s, base_url, new_app_id, remote_app_id["app_id"]
                                )
                                qrs.close_requests_session(s)
                                if app_replaced_status != 200:
                                    LOGGER.error(
                                        "%s\tSomething went wrong while trying to replace the app(s): '%s'",
                                        log_id_server,
                                        app_replaced_status,
                                    )
                                else:
                                    LOGGER.info(
                                        "%s\tSuccessfully replaced app: '%s' in the stream: '%s'",
                                        log_id_server,
                                        remote_app_id["app_id"],
                                        remote_app_id["stream_name"],
                                    )
                                    app_promoted = True
                                    promotion_results.append(
                                        {
                                            "app_name": app_name,
                                            "remote_server_alias": alias,
                                            "remote_app_id": remote_app_id["app_id"],
                                            "remote_stream_name": remote_app_id[
                                                "stream_name"
                                            ],
                                            "remote_server_fqdn": server["server"],
                                        }
                                    )
                                    final_id_list.append(remote_app_id["app_id"])

                                for x in stream_id_list:
                                    if x[0] == remote_app_id["stream_id"]:
                                        left_over_stream_id_list.remove(x)

                            qrs.close_requests_session(s)

                            LOGGER.info(
                                "%s\tDeleting application that was used to overwrite",
                                log_id_server,
                            )
                            s, base_url = qrs.establish_requests_session(alias)
                            qrs.app_delete(s, base_url, new_app_id)
                            if app_replaced_status != 200:
                                LOGGER.error(
                                    "%s\tSomething went wrong while trying to delete the app: '%s'",
                                    log_id_server,
                                    app_replaced_status,
                                )
                            else:
                                LOGGER.debug(
                                    "%s\tSuccessfully deleted the app: '%s'",
                                    log_id_server,
                                    app_replaced_status,
                                )
                            qrs.close_requests_session(s)

                        if len(left_over_stream_id_list) >= 1:
                            LOGGER.info(
                                "%s\tUploading and publishing apps to existing streams that did not contain any matching app names",
                                log_id_server,
                            )
                            i = -1
                            for stream_id in left_over_stream_id_list:
                                i += 1
                                if stream_id[0] != None:
                                    s, base_url = qrs.establish_requests_session(alias)
                                    LOGGER.info(
                                        "%s\tUploading app onto remote server and getting the new ID",
                                        log_id_server,
                                    )
                                    upload_app_status, new_app_id = qrs.upload_app(
                                        s, base_url, app_name
                                    )
                                    if upload_app_status != 201:
                                        LOGGER.error(
                                            "%s\tSomething went wrong while trying to upload the app: '%s'",
                                            log_id_server,
                                            upload_app_status,
                                        )
                                    else:
                                        LOGGER.debug(
                                            "%s\tApp uploaded: '%s'",
                                            log_id_server,
                                            upload_app_status,
                                        )
                                    qrs.close_requests_session(s)

                                    s, base_url = qrs.establish_requests_session(alias)
                                    LOGGER.info(
                                        "%s\tPublishing app '%s' to stream '%s'",
                                        log_id_server,
                                        new_app_id,
                                        stream_id[0],
                                    )
                                    app_published_status = qrs.publish_to_stream(
                                        s, base_url, new_app_id, stream_id[0]
                                    )
                                    qrs.close_requests_session(s)
                                    if app_published_status != 200:
                                        LOGGER.error(
                                            "%s\tSomething went wrong while trying to publish the app to: '%s', '%s'",
                                            log_id_server,
                                            stream_id[0],
                                            app_published_status,
                                        )
                                    else:
                                        LOGGER.debug(
                                            "%s\tApp published status: '%s'",
                                            log_id_server,
                                            app_published_status,
                                        )
                                        LOGGER.info(
                                            "%s\tSuccessfully published app '%s' to stream '%s'",
                                            log_id_server,
                                            new_app_id,
                                            stream_id[0],
                                        )
                                        app_promoted = True

                                        promotion_results.append(
                                            {
                                                "app_name": app_name,
                                                "remote_server_alias": alias,
                                                "remote_app_id": new_app_id,
                                                "remote_stream_name": stream_id[1],
                                                "remote_server_fqdn": server["server"],
                                            }
                                        )
                                        final_id_list.append(new_app_id)
                                else:
                                    pass

                    # the app will not overwrite an app unless the target stream
                    # exists
                    elif "overwrite" in server["value"]:
                        LOGGER.info(
                            "%s\tApp is set to overwrite, but no target streams exist. Exiting.",
                            log_id_server,
                        )

                    # if the app is set to duplicate and if any target streams exist on the server, new apps will be uploaded and published
                    # to them, regardless if any apps previously existed or not
                    elif "duplicate" in server["value"] and stream_existing_count >= 1:
                        LOGGER.info(
                            "%s\tNew copies of the application will be published to the target streams if they exist",
                            log_id_server,
                        )
                        i = -1
                        for stream_id in stream_id_list:
                            i += 1
                            if stream_id[0] != None:
                                s, base_url = qrs.establish_requests_session(alias)
                                LOGGER.info(
                                    "%s\tUploading app onto remote server and getting the new ID",
                                    log_id_server,
                                )
                                upload_app_status, new_app_id = qrs.upload_app(
                                    s, base_url, app_name
                                )
                                if upload_app_status != 201:
                                    LOGGER.error(
                                        "%s\tSomething went wrong while trying to upload the app: '%s'",
                                        log_id_server,
                                        upload_app_status,
                                    )
                                else:
                                    LOGGER.debug(
                                        "%s\tApp uploaded: '%s'",
                                        log_id_server,
                                        upload_app_status,
                                    )
                                qrs.close_requests_session(s)

                                s, base_url = qrs.establish_requests_session(alias)
                                LOGGER.info(
                                    "%s\tPublishing app to: '%s'", log_id_server, stream_id[0]
                                )
                                app_published_status = qrs.publish_to_stream(
                                    s, base_url, new_app_id, stream_id[0]
                                )
                                qrs.close_requests_session(s)
                                if app_published_status != 200:
                                    LOGGER.error(
                                        "%s\tSomething went wrong while trying to publish: '%s'",
                                        log_id_server,
                                        app_published_status,
                                    )
                                else:
                                    LOGGER.debug(
                                        "%s\tApp published status: '%s'",
                                        log_id_server,
                                        app_published_status,
                                    )
                                    LOGGER.info(
                                        "%s\tSuccessfully published app '%s' to stream '%s'",
                                        log_id_server,
                                        new_app_id,
                                        stream_id[0],
                                    )

                                    app_promoted = True

                                    promotion_results.append(
                                        {
                                            "app_name": app_name,
                                            "remote_server_alias": alias,
                                            "remote_app_id": new_app_id,
                                            "remote_stream_name": stream_id[1],
                                            "remote_server_fqdn": server["server"],
                                        }
                                    )
                                    final_id_list.append(new_app_id)
                            else:
                                LOGGER.debug(
                                    "%s\tCould not find stream: '%s'",
                                    log_id_server,
                                    stream_id[0],
                                )

                    elif "duplicate" in server["value"]:
                        LOGGER.info(
                            "%s\tApp set to duplicate, but no target streams exist. Exiting.",
                            log_id_server,
                        )
                    else:
                        LOGGER.info("%s\tSomething went wrong. Exiting.", log_id_server)

                else:
                    LOGGER.warning(
                        "%s\tNo matching streams exist on the server. Exiting.", log_id_server
                    )

                # if the app successfully published any apps, it will consider
                # it a success
                if app_promoted:
                    # check if versioning is enabled
                    # if so, push to s3
                    LOGGER.info(
                        "%s\tApp promoted from:'%s' to '%s'",
                        log_id_server,
                        originator_host_name,
                        alias,
                    )
                    if (
                        APP_VERSIONING
                        and (app_versioning_value_true or AUTO_VERSIONING)
                        and not already_versioned
                    ):
                        LOGGER.info("%s\tVersioning the app", log_id_server)
                        app_name_no_data = app_name + "-Template"

                        s, base_url = qrs.establish_requests_session("local")
                        LOGGER.info(
                            "%s\tExporting local app without data for versioning",
                            log_id_server,
                        )
                        export_app_status = qrs.export_app(
                            s, base_url, app_id, app_name_no_data, skip_data=True
                        )
                        qrs.close_requests_session(s)
                        if export_app_status != 200:
                            LOGGER.error(
                                "%s\tSomething went wrong while trying to export the app without data: '%s'",
                                log_id_server,
                                export_app_status,
                            )
                        else:
                            LOGGER.debug(
                                "%s\tApp exported without data: '%s'",
                                log_id_server,
                                export_app_status,
                            )

                        LOGGER.info("%s\tAttempting to connect s3", log_id_server)
                        app_file_name = app_name_no_data + ".qvf"
                        app_abs_path = EXPORTED_APP_DIRECTORY + app_file_name
                        key = S3_PREFIX + app_file_name
                        try:
                            s3 = boto3.client("s3")
                            transfer = S3Transfer(s3)
                            LOGGER.info("%s\tConnected to s3", log_id_server)
                            try:
                                LOGGER.info(
                                    "%s\tTrying to upload the app '%s' to the bucket '%s' with prefix '%s'",
                                    log_id_server,
                                    app_file_name,
                                    S3_BUCKET,
                                    S3_PREFIX,
                                )
                                transfer.upload_file(app_abs_path, S3_BUCKET, key)
                                LOGGER.info(
                                    "%s\tApp uploaded successfully to '%s'",
                                    log_id_server,
                                    S3_BUCKET,
                                )
                                try:
                                    LOGGER.info(
                                        "%s\tGetting the version id of the s3 object",
                                        log_id_server,
                                    )
                                    s3 = boto3.resource("s3")
                                    app_s3_version_id = str(
                                        s3.Object(S3_BUCKET, key).version_id
                                    )
                                    description += (
                                        "\n\nS3 Version ID: " + app_s3_version_id
                                    )
                                    LOGGER.info(
                                        "%s\tApp s3 version id: '%s'",
                                        log_id_server,
                                        app_s3_version_id,
                                    )
                                    already_versioned = True
                                    template_app_deleted_status = qrs.delete_local_app_export(
                                        app_name_no_data
                                    )
                                    if not template_app_deleted_status:
                                        LOGGER.error(
                                            "%s\tSomething went wrong while trying to delete the template app: '%s'",
                                            log_id_server,
                                            template_app_deleted_status,
                                        )
                                    else:
                                        LOGGER.debug(
                                            "%s\tLocal app deleted: '%s'",
                                            log_id_server,
                                            template_app_deleted_status,
                                        )
                                except Exception as error:
                                    LOGGER.error(
                                        "%s\tSomething went wrong while getting the version id from s3: '%s'",
                                        log_id_server,
                                        error,
                                    )
                            except Exception as error:
                                LOGGER.error(
                                    "%s\tCould not upload the app: '%s'",
                                    log_id_server,
                                    error,
                                )
                        except Exception as error:
                            LOGGER.error(
                                "%s\tCould not connect to s3: '%s'", log_id_server, error
                            )
                            LOGGER.error(
                                "%s\tPlease ensure that your server has programmatic access such as an IAM role to the bucket enabled",
                                log_id_server,
                            )

                    # update the description for each of the published apps
                    s, base_url = qrs.establish_requests_session(alias)
                    LOGGER.info(
                        "%s\tAdding a description to the remote app(s)", log_id_server
                    )
                    for published_app_id in final_id_list:
                        # add a description to the remote app that
                        # states who promoted it and when
                        description_status_code = qrs.modify_app_description(
                            s, base_url, published_app_id, description
                        )
                        if description_status_code != 200:
                            LOGGER.error(
                                "%s\tSomething went wrong while trying to add a description to the app: '%s'",
                                log_id_server,
                                description_status_code,
                            )
                        else:
                            LOGGER.info(
                                "%s\tDescription successfully added to the app: '%s', '%s'",
                                log_id_server,
                                description_status_code,
                                published_app_id,
                            )
                    qrs.close_requests_session(s)

                    if (
                        (AUTO_UNPUBLISH or unpublish_app_value_true)
                        and not promote_on_reload_value_true
                        and target_remote_server_tracker == target_remote_servers
                    ):
                        LOGGER.info(
                            "%s\tDuplicating the local application: '%s'",
                            log_id_server,
                            app_name,
                        )
                        s, base_url = qrs.establish_requests_session("local")
                        duplicated_app_status_code, duplicate_app_id = qrs.duplicate_app(
                            s, base_url, app_id, app_name
                        )
                        qrs.close_requests_session(s)
                        if duplicated_app_status_code != 201:
                            LOGGER.error(
                                "%s\tSomething went wrong while duplicating the app: '%s'",
                                log_id_server,
                                duplicated_app_status_code,
                            )
                        else:
                            LOGGER.info(
                                "%s\tSuccessfully duplicated app: '%s'",
                                log_id_server,
                                app_name,
                            )

                        LOGGER.info(
                            "%s\tChanging the owner of the duplicated app back to '%s'",
                            log_id_server,
                            app_owner,
                        )
                        s, base_url = qrs.establish_requests_session("local")
                        change_app_owner_status = qrs.change_app_owner(
                            s, base_url, duplicate_app_id, app_owner_id
                        )
                        qrs.close_requests_session(s)

                        if change_app_owner_status != 200:
                            LOGGER.error(
                                "%s\tSomething went wrong while trying to change the app owner: '%s'",
                                log_id_server,
                                change_app_owner_status,
                            )
                        else:
                            LOGGER.info(
                                "%s\tSuccessfully changed the app owner to: '%s'",
                                log_id_server,
                                app_owner,
                            )

                        LOGGER.info("%s\tDeleting the published app", log_id_server)
                        s, base_url = qrs.establish_requests_session("local")
                        app_delete_status = qrs.app_delete(s, base_url, app_id)
                        qrs.close_requests_session(s)

                        if app_delete_status != 204:
                            LOGGER.error(
                                "%s\tSomething went wrong while trying to delete the app with id: '%s'",
                                log_id_server,
                                app_id,
                            )
                        else:
                            LOGGER.info(
                                "%s\tSuccessfully deleted the app with id: '%s'",
                                log_id_server,
                                app_id,
                            )
                    else:
                        if (
                            not promote_on_reload_value_true
                            and target_remote_server_tracker
                            == target_remote_servers
                        ):
                            LOGGER.info(
                                "%s\tRemoving promotion related custom properties if they exist from the published app including: '%s'",
                                log_id_server,
                                PROP_LIST,
                            )

                            s, base_url = qrs.establish_requests_session("local")
                            removed_props_status = qrs.remove_props_from_app(
                                s, base_url, app_id, PROP_LIST
                            )
                            qrs.close_requests_session(s)

                            if removed_props_status != 200:
                                LOGGER.error(
                                    "%s\tSomething went wrong while trying to remove custom properties from the app: '%s'",
                                    log_id_server,
                                    removed_props_status,
                                )
                            else:
                                LOGGER.info(
                                    "%s\tSuccessfully removed promotion related custom properties from the app app: '%s'",
                                    log_id_server,
                                    app_name,
                                )

                    # delete the local copy of the exported app
                    if target_remote_server_tracker == target_remote_servers:
                        local_app_deleted_status = qrs.delete_local_app_export(
                            app_name
                        )
                        if not local_app_deleted_status:
                            LOGGER.error(
                                "%s\tSomething went wrong while trying to delete the app: '%s'",
                                log_id_server,
                                local_app_deleted_status,
                            )
                        else:
                            LOGGER.info(
                                "%s\tLocal app deleted: '%s'",
                                log_id_server,
                                local_app_deleted_status,
                            )

        elif (
            not promotion_approved
            and not promotion_approval_empty
            and not promotion_approval_bad_input
            and (AUTO_UNPUBLISH or unpublish_app_value_true)
        ):

            LOGGER.info(
                "%s\tApplication approval for '%s' has been denied", log_id, app_name
            )
            LOGGER.info("%s\tDuplicating the local application: '%s'", log_id, app_name)
            s, base_url = qrs.establish_requests_session("local")
            duplicated_app_status_code, duplicate_app_id = qrs.duplicate_app(
                s, base_url, app_id, app_name
            )
            qrs.close_requests_session(s)
            if duplicated_app_status_code != 201:
                LOGGER.error(
                    "%s\tSomething went wrong while duplicating the app: '%s'",
                    log_id,
                    duplicated_app_status_code,
                )
            else:
                LOGGER.info("%s\tSuccessfully duplicated app: '%s'", log_id, app_name)

            LOGGER.info(
                "%s\tChanging the owner of the duplicated app back to '%s'",
                log_id,
                app_owner,
            )
            s, base_url = qrs.establish_requests_session("local")
            change_app_owner_status = qrs.change_app_owner(
                s, base_url, duplicate_app_id, app_owner_id
            )
            qrs.close_requests_session(s)

            if change_app_owner_status != 200:
                LOGGER.error(
                    "%s\tSomething went wrong while trying to change the app owner: '%s'",
                    log_id,
                    change_app_owner_status,
                )
            else:
                LOGGER.info(
                    "%s\tSuccessfully changed the app owner to: '%s'", log_id, app_owner
                )

            LOGGER.info("%s\tDeleting the published app", log_id)
            s, base_url = qrs.establish_requests_session("local")
            app_delete_status = qrs.app_delete(s, base_url, app_id)
            qrs.close_requests_session(s)

            if app_delete_status != 204:
                LOGGER.error(
                    "%s\tSomething went wrong while trying to delete the app with id: '%s'",
                    log_id,
                    app_id,
                )
            else:
                LOGGER.info(
                    "%s\tSuccessfully deleted the app with id: '%s'", log_id, app_id
                )

        elif (
            not promotion_approved
            and not promotion_approval_empty
            and not promotion_approval_bad_input
            and not AUTO_UNPUBLISH
        ):

            LOGGER.info(
                "%s\tRemoving promotion related custom properties if they exist from the published app including: '%s'",
                log_id,
                PROP_LIST,
            )

            s, base_url = qrs.establish_requests_session("local")
            removed_props_status = qrs.remove_props_from_app(
                s, base_url, app_id, PROP_LIST
            )
            qrs.close_requests_session(s)

            if removed_props_status != 200:
                LOGGER.error(
                    "%s\tSomething went wrong while trying to remove custom properties from the app: '%s'",
                    log_id,
                    removed_props_status,
                )
            else:
                LOGGER.info(
                    "%s\tSuccessfully removed promotion related custom properties from the app app: '%s'",
                    log_id,
                    app_name,
                )

        elif promote_custom_prop_found and not promote_stream_custom_prop_found:
            LOGGER.info(
                "%s\tCustom property '%s' could not be found. Exiting.",
                log_id,
                CUSTOM_PROPERTY_NAME_PROMOTE_STREAM,
            )
        elif promote_stream_custom_prop_found and not promote_custom_prop_found:
            LOGGER.info(
                "%s\tCustom property '%s' could not be found. Exiting.",
                log_id,
                CUSTOM_PROPERTY_NAME_PROMOTE,
            )
        elif not promote_custom_prop_found and not promote_stream_custom_prop_found:
            LOGGER.info(
                "%s\tNeither the '%s' or the '%s' could be found. Exiting.",
                log_id,
                CUSTOM_PROPERTY_NAME_PROMOTE,
                CUSTOM_PROPERTY_NAME_PROMOTE_STREAM,
            )
        elif promotion_approval_empty and not promote_on_reload_value_true:
            LOGGER.info(
                "%s\tThere is no mandatory value for '%s'. Exiting.",
                log_id,
                CUSTOM_PROPERTY_NAME_PROMOTE_APPROVAL,
            )
        elif (
            promotion_approved
            and promote_custom_prop_found
            and promote_stream_custom_prop_found
            and trigger_type == "updated"
            and promote_on_reload_value_true
        ):
            LOGGER.info(
                "%s\tThis was an app update trigger however the custom property of '%s' was found. This app will only be promoted through a reload trigger.",
                log_id,
                CUSTOM_PROPERTY_NAME_PROMOTE_ON_RELOAD,
            )
    if app_num_custom_properties == 0:
        LOGGER.info("%s\tNo custom properties could be found. Exiting.", log_id)

    if app_tagged_auto_reload and not promote_on_reload_value_true:
        s, base_url = qrs.establish_requests_session("local")
        LOGGER.info(
            "%s\tUntagging app '%s' with tag named '%s'",
            log_id,
            app_name,
            PROMOTE_ON_RELOAD_TAG_NAME,
        )
        remove_tag_status = qrs.remove_tag_from_app(
            s, base_url, app_id, PROMOTE_ON_RELOAD_TAG_NAME
        )
        qrs.close_requests_session(s)
        if remove_tag_status != 200:
            LOGGER.error(
                "%s\tSomething went wrong while trying to remove the tag from the app: '%s'",
                log_id,
                remove_tag_status,
            )
        else:
            LOGGER.debug("%s\tTag removed: '%s'", log_id, remove_tag_status)
    if (
        promote_on_reload_value_true
        and promote_custom_prop_found
        and promote_stream_custom_prop_found
        and trigger_type == "updated"
    ):
        LOGGER.info("%s\tThe app will be auto-promoted on reloads. Exiting.", log_id)

    if met_criteria and not app_tagged_auto_reload:
        LOGGER.info("%s\tPromotion results: '%s'", log_id, promotion_results)
        LOGGER.info("%s\tStreams not found: '%s'", log_id, streams_not_found)
        LOGGER.info("%s\tAttempting to send promotion results email", log_id)
        email_promotion_results_response = mailer.email_promotion_results(
            app_name,
            app_owner_id,
            modified_by_user,
            promotion_results,
            streams_not_found,
        )
        LOGGER.info("%s\tEmail response: '%s", log_id, email_promotion_results_response)

    return "Finished"
