import logging
from logging.handlers import RotatingFileHandler
from Modules.qrsFunctions import *
from pathlib import Path
import os
import time
import uuid

# configuration file
with open('config.json') as f:
    config = json.load(f)

# logging
logLevel = config['logLevel'].lower()
logger = logging.getLogger(__name__)
# rolling logs with max 2 MB files with 3 backups
handler = logging.handlers.RotatingFileHandler(
    'Log/flask_listener.log', maxBytes=2000000, backupCount=3)


if logLevel == 'info':
    logging.basicConfig(level=logging.INFO)
else:
    logging.basicConfig(level=logging.DEBUG)

appChangeID = str(uuid.uuid4())
appChangeStatus = 'Initializing'
formatter = logging.Formatter('%(asctime)s\t%(name)s\t%(levelname)s\t' + 
    appChangeID + '\t' + appChangeStatus + '\t%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.info('Log level set to: ' + logLevel)

# additional config
customPropertyNamePromote = config['promoteOnCustomPropertyChange']['customPropertyNamePromote']
logger.info('Custom property name for promotion: ' + customPropertyNamePromote)
customPropertyNamePromoteStream = config['promoteOnCustomPropertyChange'][
    'customPropertyNamePromoteStream']
logger.info('Custom property name containing stream names: ' + customPropertyNamePromoteStream)
appPromotedTagID = config['promoteOnCustomPropertyChange']['appPromotedTagID']
logger.info('ID of the tag used to signify whether the app is promoted or not: ' + appPromotedTagID)
versioningCustomPropName = config['promoteOnCustomPropertyChange']['appVersionOnChange']['customPropertyName']
logger.info('Custom property name used for versioning if enabled: ' + versioningCustomPropName)
localServer = config['promoteOnCustomPropertyChange']['localServer']

# check for versioning
appVersionOnChange = config['promoteOnCustomPropertyChange']['appVersionOnChange']['enabled'].lower()
if appVersionOnChange == 'true':
    logger.info('App versioning enabled with s3')
    s3bucket = config['promoteOnCustomPropertyChange']['appVersionOnChange']['s3bucket']
    logger.info('Target s3 bucket: ' + str(s3bucket))
    s3Prefix = config['promoteOnCustomPropertyChange']['appVersionOnChange']['prefix']
    logger.info('Prefix: ' + str(s3Prefix))

    try:
        import boto3
        from boto3.s3.transfer import S3Transfer
        import threading
        appVersioning = True
        # get the file path for the ExportedApps/ dir for later use
        exportedAppDirectory = str(Path(__file__).parent.parent).replace('\\','/') + '/ExportedApps/'

        # https://boto3.amazonaws.com/v1/documentation/api/latest/_modules/boto3/s3/transfer.html
        class S3ProgressPercentage(object):
            def __init__(self, filename):
                self._filename = filename
                self._size = float(os.path.getsize(filename))
                self._seen_so_far = 0
                self._lock = threading.Lock()

            def __call__(self, bytes_amount):
                with self._lock:
                    self._seen_so_far += bytes_amount
                    percentage = (self._seen_so_far / self._size) * 100
                    logger.debug(
                        "\r%s  %s / %s  (%.2f%%)" % (
                            self._filename, self._seen_so_far, self._size,
                            percentage))

    except ImportError:
        appVersioning = False
        logger.info('Could not import "boto3" library which is used with s3. Please install the boto library for versioning to be enabled')
else:
    logger.info('App versioning is not enabled.')
    appVersioning = False

f.close()

def promoteApp(appID):
    appChangeID = str(uuid.uuid4())
    appChangeStatus = 'Executing'
    formatter = logging.Formatter('%(asctime)s\t%(name)s\t%(levelname)s\t' + 
        appChangeID + '\t' + appChangeStatus + '\t%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.info('_____________App Updated_____________')

    s, baseUrl = establishRequestsSession('local')
    logger.info('Requesting app/full info on "' + appID + '"')
    appFullStatus, appFullResponse = appFull(s, baseUrl, appID)
    closeRequestsSession(s)
    if appFullStatus != 200:
        logger.error('Something went wrong while trying to get app/full: ' + str(appFullStatus))
    else:
        logger.debug('Got app/full data: ' + str(appFullStatus))

    appName = appFullResponse['name']
    logger.info('App Name: "' + appName + '"')

    appOwnerID = appFullResponse['owner']['userId']
    appOwnerUserDirectory = appFullResponse['owner']['userDirectory']
    appOwner = str(str(appOwnerUserDirectory) + '\\' + str(appOwnerID))
    modifiedByUser = str(appFullResponse['modifiedByUserName'])
    modifiedDate = str(appFullResponse['modifiedDate'])

    # set the description that will be applied to promoted apps
    description = 'App promoted from: "' + localServer + '" by: "' + modifiedByUser + '" at: "' + modifiedDate + '" where it was owned by: "' + appOwner + '".'
    logger.info('App updated on: "' + localServer + '" modified by: "' + modifiedByUser + '"" owned by: "' + appOwner + '"')

    appNumCustomProperties = len(appFullResponse['customProperties'])
    logger.info('App Number of Custom Properties: "' + str(appNumCustomProperties) + '"')

    # if the promote custom property is not found, the app promoted tag will be bounced (removed) if it exists
    logger.info('Checking to see if app is tagged as promoted')

    appIsPromoted = False
    if len(appFullResponse['tags']) >= 1:
        for tag in appFullResponse['tags']:
            if tag['id'] == appPromotedTagID:
                appIsPromoted = True
                break

    if appIsPromoted:
        logger.info('The app is tagged as promoted')
    else:
        logger.info('App is tagged as not promoted')

    if appNumCustomProperties >= 1:
        promoteCustomPropFound = False
        promoteStreamCustomPropFound = False
        appVersioningValueTrue = False

        logger.info('Searching app/full to see if "' + customPropertyNamePromote + '" and/or "' +
                    customPropertyNamePromoteStream + '" custom properties exist')
        streamValueList = []
        customPropertyNamePromoteValueCount = 0
        customPropVersionValueCount = 0
        for customProp in appFullResponse['customProperties']:
            if customProp['definition']['name'] == customPropertyNamePromote:
                promoteValue = customProp['value']
                logger.info('Mandatory custom property "' + customPropertyNamePromote +
                            '" exists with the value of: "' + str(promoteValue) + '"')
                promoteCustomPropFound = True
                customPropertyNamePromoteValueCount += 1
            elif customProp['definition']['name'] == customPropertyNamePromoteStream:
                promoteStreamValue = customProp['value']
                logger.info('Mandatory custom property "' + customPropertyNamePromoteStream +
                            '" exists with the value of: "' + str(promoteStreamValue) + '"')
                promoteStreamCustomPropFound = True
                streamValueList.append(promoteStreamValue)
            elif appVersioning and appVersionOnChange == 'true':
                if customProp['definition']['name'] == versioningCustomPropName:
                    customPropVersionValueCount += 1
                    versioningCustomPropValue = customProp['value'].lower()
                    if versioningCustomPropValue == 'true':
                        logger.info('App versioning custom property "' + versioningCustomPropName +
                            '"" with the value of: "' + versioningCustomPropValue + '"')
                        appVersioningValueTrue = True
                    elif customPropVersionValueCount == 1:
                        logger.warning('This app will not be versioned as the value ' +
                            'must be set to "true" (case insensitive)')
            elif customProp['definition']['name'] == versioningCustomPropName:
                logger.info('Versioning is not enabled though the custom property ' +
                        '"' + versioningCustomPropName + '" is found. No action taken.')

        if promoteCustomPropFound and promoteStreamCustomPropFound and customPropertyNamePromoteValueCount == 1:
            logger.info('Both mandatory custom properties have values, proceeding')
            if appIsPromoted:
                logger.info('App is already promoted. No action will be taken. Exiting.')
            else:
                # lookup all of the streams by name to see if they are valid
                streamIDList = []
                matchingStreamList = []
                finalIDList = []
                i = -1
                s, baseUrl = establishRequestsSession('remote')
                logger.info("Getting Stream ID's from remote server by name for streams " +
                            '"' + str(streamValueList) + '"')
                for stream in streamValueList:
                    i += 1

                    streamIDStatus, streamID, rjson = getRemoteStreamIdsByName(s, baseUrl, stream)
                    if streamIDStatus != 200:
                        logger.error(
                            'Something went wrong while trying to get the ID for stream: "' + 
                            str(stream) + '"')
                        logger.error('Status: "' + str(streamIDStatus) + '"')
                        logger.debug('Get stream ID call status: "' + str(streamIDStatus) + '"')
                    if streamID != None:
                        matchingStreamList.append(streamValueList[i])
                        streamIDList.append(streamID)
                        logger.info('Stream found: "' + streamValueList[i] + '"')
                    else:
                        logger.warning('Stream not found: "' + streamValueList[i] + '"')

                closeRequestsSession(s)
                logger.info('Stream ID List: "' + str(streamIDList) + '"')
                streamExistingCount = len(matchingStreamList)

                if streamExistingCount >= 1 and ('overwrite' in promoteValue.lower() or
                                                 'duplicate' in promoteValue.lower()):

                    s, baseUrl = establishRequestsSession('local')
                    logger.info('Exporting local app')
                    exportAppStatus = exportApp(s, baseUrl, appID, appName)
                    closeRequestsSession(s)
                    if exportAppStatus != 200:
                        logger.error('Something went wrong while trying to export the app: "' +
                                     str(exportAppStatus) + '"')
                    else:
                        logger.debug('App exported: "' + str(exportAppStatus) + '"')

                    if 'overwrite' in promoteValue.lower() and streamExistingCount >= 1:
                        logger.info(
                            'Apps that exist with the same name in target streams will be overwritten.'
                            + 'If they do not exist, they will be created.')
                        s, baseUrl = establishRequestsSession('remote')
                        logger.info(
                            "Looking up app ID's to be overwritten on the remote server by name")
                        remoteAppIDstatus, remoteAppIDJSON = getRemoteAppIdsByName(
                            s, baseUrl, appName)
                        numRemoteAppIDs = len(remoteAppIDJSON)

                        if remoteAppIDstatus != 200:
                            logger.error('Something went wrong when looking up apps by name: "' +
                                         str(remoteAppIDstatus) + '"')
                        else:
                            logger.debug('Call to look up apps status: "' + str(remoteAppIDstatus) + '"')

                        logger.info('App IDs found with matching names: "' + str(numRemoteAppIDs) + '"')

                        remoteAppDetailList = []
                        matchingAppIDs = []
                        matchingPublishedAppIDs = []
                        numRemoteFoundTargetPublished = 0
                        if numRemoteAppIDs >= 1:
                            for app in remoteAppIDJSON:
                                remoteAppID = app['id']
                                matchingAppIDs.append(remoteAppID)
                                remoteAppPublished = app['published']
                                if remoteAppPublished == True:
                                    remoteStreamID = app['stream']['id']
                                    remoteStreamName = app['stream']['name']

                                    for sID in streamIDList:
                                        if sID == remoteStreamID:
                                            matchingPublishedAppIDs.append(remoteAppID)
                                            remoteAppDetailList.append({
                                                'appID':
                                                remoteAppID,
                                                'published':
                                                remoteAppPublished,
                                                'streamID':
                                                remoteStreamID,
                                                'streamName':
                                                remoteStreamName
                                            })

                            closeRequestsSession(s)
                            numRemoteFoundTargetPublished = len(remoteAppDetailList)

                            logger.info("Matching App ID's: " + '"' + 
                                str(matchingAppIDs) + '"')
                            logger.info(
                                'Matching apps with matching names that are published to target streams: "'
                                + str(matchingPublishedAppIDs) + '"')
                            logger.debug('App info: "' + str(remoteAppDetailList) + '"')

                        leftOverStreamIDList = streamIDList
                        if numRemoteFoundTargetPublished >= 1:
                            s, baseUrl = establishRequestsSession('remote')
                            logger.info('Uploading app onto remote server and getting the new ID')
                            uploadAppStatus, newAppID = uploadApp(s, baseUrl, appName)
                            if uploadAppStatus != 201:
                                logger.error('Something went wrong while trying to upload the app: "'
                                             + str(uploadAppStatus) + '"')
                            else:
                                logger.debug('App uploaded: "' + str(uploadAppStatus) + '"')
                            closeRequestsSession(s)

                            s, baseUrl = establishRequestsSession('remote')
                            logger.info(
                                "Overwriting existing apps with matching names published to target streams"
                            )
                            for remoteAppID in remoteAppDetailList:
                                appReplacedStatus = appReplace(s, baseUrl, newAppID,
                                                               remoteAppID['appID'])
                                closeRequestsSession(s)
                                if appReplacedStatus != 200:
                                    logger.error(
                                        'Something went wrong while trying to replace the app(s): "' +
                                        str(appReplacedStatus) + '"')
                                else:
                                    logger.info('Successfully replaced app: "' +
                                        str(remoteAppID['appID']) + '"' +
                                        ' in the stream: "' + str(remoteAppID['streamName']) + '"')
                                    appPromoted = True
                                    finalIDList.append(remoteAppID['appID'])
                                try:
                                    popThis = remoteAppID['streamID']
                                    leftOverStreamIDList.remove(popThis)
                                except:
                                    pass
                            closeRequestsSession(s)

                            logger.info('Deleting application that was used to overwrite')
                            s, baseUrl = establishRequestsSession('remote')
                            appDelete(s, baseUrl, newAppID)
                            if appReplacedStatus != 200:
                                logger.error('Something went wrong while trying to delete the app: "'
                                             + str(appReplacedStatus) + '"')
                            else:
                                logger.debug('Successfully deleted the app: "' +
                                             str(appReplacedStatus) + '"')
                            closeRequestsSession(s)

                        if len(leftOverStreamIDList) >= 1:
                            logger.info(
                                'Uploading and publishing apps to existing streams that did not contain'
                                + ' any matching app names')
                            i = -1
                            for streamID in leftOverStreamIDList:
                                i += 1
                                if streamID != None:
                                    s, baseUrl = establishRequestsSession('remote')
                                    logger.info(
                                        'Uploading app onto remote server and getting the new ID')
                                    uploadAppStatus, newAppID = uploadApp(s, baseUrl, appName)
                                    if uploadAppStatus != 201:
                                        logger.error(
                                            'Something went wrong while trying to upload the app: "' +
                                            str(uploadAppStatus) + '"')
                                    else:
                                        logger.debug('App uploaded: "' + str(uploadAppStatus) + '"')
                                    closeRequestsSession(s)

                                    s, baseUrl = establishRequestsSession('remote')
                                    logger.info('Publishing app: "' + str(newAppID) + 
                                        '"" to stream: "' + str(streamID) + '"')
                                    appPublishedStatus = publishToStream(
                                        s, baseUrl, newAppID, streamID)
                                    closeRequestsSession(s)
                                    if appPublishedStatus != 200:
                                        logger.error(
                                            'Something went wrong while trying to publish the app to: "'
                                            + str(streamID) + '"')
                                    else:
                                        logger.debug('App published status: "' +
                                                     str(appPublishedStatus) + '"')
                                        logger.info('Successfully published app: "' +
                                            str(newAppID) + '" to stream: "' + str(streamID) + '"')
                                        appPromoted = True
                                        finalIDList.append(newAppID)
                                else:
                                    pass

                    # the app will not overwrite an app unless the target stream exists
                    elif 'overwrite' in promoteValue.lower():
                        logger.info('App is set to overwrite, but no target streams exist. Exiting.')

                    # if the app is set to duplicate and if any target streams exist on the server, new apps will be uploaded and published
                    # to them, regardless if any apps previously existed or not
                    elif 'duplicate' in promoteValue.lower() and streamExistingCount >= 1:
                        logger.info(
                            'New copies of the application will be published to the target streams if they exist'
                        )
                        i = -1
                        for streamID in streamIDList:
                            i += 1
                            if streamID != None:
                                s, baseUrl = establishRequestsSession('remote')
                                logger.info(
                                    'Uploading app onto remote server and getting the new ID')
                                uploadAppStatus, newAppID = uploadApp(s, baseUrl, appName)
                                if uploadAppStatus != 201:
                                    logger.error(
                                        'Something went wrong while trying to upload the app: "' +
                                        str(uploadAppStatus) + '"')
                                else:
                                    logger.debug('App uploaded: "' + str(uploadAppStatus) + '"')
                                closeRequestsSession(s)

                                s, baseUrl = establishRequestsSession('remote')
                                logger.info('Publishing app to: "' + str(streamID) + '"')
                                appPublishedStatus = publishToStream(s, baseUrl, newAppID, streamID)
                                closeRequestsSession(s)
                                if appPublishedStatus != 200:
                                    logger.error('Something went wrong while trying to publish: "' +
                                                 str(appPublishedStatus) + '"')
                                else:
                                    logger.debug('App published status: "' + str(appPublishedStatus) + '"')
                                    logger.info('Successfully published app: "' +
                                        str(newAppID) + '" to stream:"' + str(streamID) + '"')
                                    appPromoted = True
                                    finalIDList.append(newAppID)
                            else:
                                logger.debug('Could not find stream: "' + str(streamID) + '"')

                    elif 'duplicate' in promoteValue.lower():
                        logger.info('App set to duplicate, but no target streams exist. Exiting.')
                    else:
                        logger.info('Something went wrong. Exiting.')

                    # if the app successfully published any apps,
                    # it will consider it a success, and will tag the Qlik Sense app as promoted
                    if appPromoted:
                        # check if versioning is enabled
                        # if so, push to s3
                        if appVersioning and appVersioningValueTrue:
                            logger.info('Versioning the app')
                            appNameNoData = appName + '-Template'

                            s, baseUrl = establishRequestsSession('local')
                            logger.info('Exporting local app without data for versioning')
                            exportAppStatus = exportApp(s, baseUrl, appID, appNameNoData, skipData=True)
                            closeRequestsSession(s)
                            if exportAppStatus != 200:
                                logger.error('Something went wrong while trying to export the app without data: "' +
                                             str(exportAppStatus) + '"')
                            else:
                                logger.debug('App exported without data: "' + str(exportAppStatus) + '"')

                            logger.info('Attempting to connect s3')
                            appFileName = appNameNoData + '.qvf'
                            appAbsPath = exportedAppDirectory + appFileName
                            key = s3Prefix + appFileName
                            try:
                                s3 = boto3.client('s3')
                                transfer = S3Transfer(s3)
                                logger.info('Connected to s3')
                                try:
                                    logger.info('Trying to upload the app: ' + appFileName +
                                        ' to the bucket: "' + str(s3bucket) + '"" with prefix: "' +
                                        str(s3Prefix) + '"')
                                    transfer.upload_file(appAbsPath, s3bucket, key,
                                        callback=S3ProgressPercentage(appAbsPath))
                                    logger.info('App uploaded successfully to: "' + str(s3bucket) + '"')
                                    try:
                                        logger.info('Getting the version id of the s3 object')
                                        s3 = boto3.resource('s3')
                                        appS3VersionID = str(s3.Object(s3bucket,key).version_id)
                                        description += '\n\nS3 Version ID: ' + appS3VersionID
                                        logger.info('App s3 version id: "' + appS3VersionID + '"')
                                        templateAppDeletedStatus = deleteLocalAppExport(appNameNoData)
                                        if not templateAppDeletedStatus:
                                            logger.error('Something went wrong while trying to delete the template app: "' +
                                                         str(templateAppDeletedStatus) + '"')
                                        else:
                                            logger.debug('Local app deleted: "' + str(templateAppDeletedStatus) + '"')
                                    except Exception as e:
                                        logger.error('Something went wrong while getting the version id from s3')
                                except Exception as e:
                                    logger.error('Could not upload the app: "' + str(e) + '"')
                            except Exception as e:
                                logger.error('Could not connect to s3: "' + str(e) + '"')
                                logger.error('Please ensure that your server has programmatic access such as an IAM role to the bucket enabled')

                        # update the description for each of the published apps
                        s, baseUrl = establishRequestsSession('remote')
                        logger.info('Adding a description to the remote app')
                        for publishedAppID in finalIDList:
                            # add a description to the remote app that
                            # states who promoted it and when
                            descriptionStatusCode = modifyAppDescription(s, baseUrl, publishedAppID, description)
                            if descriptionStatusCode != 200:
                                logger.error('Something went wrong while trying to add a description to the app: "' +
                                    str(descriptionStatusCode) + '"')
                            else:
                                logger.debug('Description successfully added to the app: "' + str(descriptionStatusCode) + '"')
                        closeRequestsSession(s)

                        # tag the local as promoted
                        s, baseUrl = establishRequestsSession('local')
                        logger.info('Tagging app as promoted')
                        tagAddedStatus = addTagToApp(s, baseUrl, appID, appPromotedTagID)
                        closeRequestsSession(s)
                        if tagAddedStatus != 200:
                            logger.error(
                                'Something went wrong while trying to add the promoted tag to the app: "'
                                + str(tagAddedStatus) + '"')
                        else:
                            logger.debug('Promoted tag added to the app: "' + str(tagAddedStatus) + '"')

                        # delete the local copy of the app
                        localAppDeletedStatus = deleteLocalAppExport(appName)
                        if not localAppDeletedStatus:
                            logger.error('Something went wrong while trying to delete the app: "' +
                                         str(localAppDeletedStatus) + '"')
                        else:
                            logger.debug('Local app deleted: "' + str(localAppDeletedStatus) + '"')

                else:
                    logger.warning('No matching streams exist on the server. Exiting.')

        elif customPropertyNamePromoteValueCount > 1:
            logger.error('There can only be a single value in the custom property: "' +
                        str(customPropertyNamePromote) + '". Exiting.')
        # if the promote custom property is not found,
        # the app promoted tag will be bounced (removed) if it exists
        elif not promoteCustomPropFound and appIsPromoted:
            logger.info('The "' + customPropertyNamePromote + '"" custom property is empty')
            if appIsPromoted:
                logger.info('App is promoted, however the "' + customPropertyNamePromote +
                            '"" does not exist')
                logger.info('Removing the promoted tag')
                s, baseUrl = establishRequestsSession('local')
                removeTagStatus = removeTagFromApp(s, baseUrl, appID, appPromotedTagID)
                closeRequestsSession(s)
                if removeTagStatus != 200:
                    logger.error('Something went wrong while trying to remove the promoted tag: "' +
                                 str(removeStatus) + '"')
                else:
                    logger.debug('Tag removed: "' + str(removeTagStatus) + '"')

        elif promoteCustomPropFound and not promoteStreamCustomPropFound:
            logger.info('Custom property "' + customPropertyNamePromoteStream +
                        '" could not be found. Exiting.')
        elif promoteStreamCustomPropFound and not promoteCustomPropFound:
            logger.info('Custom property "' + customPropertyNamePromote +
                        '" could not be found. Exiting.')
        elif not promoteCustomPropFound and not promoteStreamCustomPropFound:
            logger.info('Neither the "' + customPropertyNamePromote + '" or the "' +
                        customPropertyNamePromoteStream + '" could be found. Exiting.')

    elif appIsPromoted and appNumCustomProperties == 0:
        logger.info('App is promoted, however the "' + customPropertyNamePromote + '"" does not exist')
        logger.info('Removing the promoted tag')
        s, baseUrl = establishRequestsSession('local')
        removeTagStatus = removeTagFromApp(s, baseUrl, appID, appPromotedTagID)
        closeRequestsSession(s)
        if removeTagStatus != 200:
            logger.error('Something went wrong while trying to remove the promoted tag: "' +
                         str(removeStatus) + '"')
        else:
            logger.debug('Tag removed: "' + str(removeTagStatus) + '"')

    if appNumCustomProperties == 0:
        logger.info('No custom properties could be found. Exiting.')

    return 'Finished'