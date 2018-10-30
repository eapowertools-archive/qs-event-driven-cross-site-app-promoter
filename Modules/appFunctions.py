import logging
from logging.handlers import RotatingFileHandler
from Modules.qrsFunctions import *

# configuration file
with open('config.json') as f:
    config = json.load(f)

# logging
logLevel = config['logLevel']
logger = logging.getLogger(__name__)
# rolling logs with max 2 MB files with 3 backups
handler = logging.handlers.RotatingFileHandler(
    'Log/flask_listener.log', maxBytes=2000000, backupCount=3)
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

# additional config
customPropertyNamePromote = config['promoteOnCustomPropertyChange']['customPropertyNamePromote']
logger.info('Custom property name for promotion: ' + customPropertyNamePromote)
customPropertyNamePromoteStream = config['promoteOnCustomPropertyChange'][
    'customPropertyNamePromoteStream']
logger.info('Custom property name containing stream names: ' + customPropertyNamePromoteStream)
appPromotedTagID = config['promoteOnCustomPropertyChange']['appPromotedTagID']
logger.info('ID of the tag used to signify whether the app is promoted or not: ' + appPromotedTagID)


def promoteApp(appID):
    logger.info('_____________App Updated_____________')

    s, baseUrl = establishRequestsSession('local')
    logger.info('Requesting app/full info on ' + appID)
    appFullStatus, appFullResponse = appFull(s, baseUrl, appID)
    closeRequestsSession(s)
    if appFullStatus != 200:
        logger.debug('Something went wrong while trying to get app/full: ' + str(appFullStatus))
    else:
        logger.debug('Got app/full data: ' + str(appFullStatus))

    appName = appFullResponse['name']
    logger.info('App Name: ' + appName)

    appNumCustomProperties = len(appFullResponse['customProperties'])
    logger.info('App Number of Custom Properties: ' + str(appNumCustomProperties))

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

        logger.info('Searching app/full to see if "' + customPropertyNamePromote + '" and/or "' +
                    customPropertyNamePromoteStream + '" custom properties exist')
        streamValueList = []
        customPropertyNamePromoteValueCount = 0
        for customProp in appFullResponse['customProperties']:
            if customProp['definition']['name'] == customPropertyNamePromote:
                promoteValue = customProp['value']
                logger.info('Mandatory custom property "' + customPropertyNamePromote +
                            '" exists with the value of: ' + str(promoteValue))
                promoteCustomPropFound = True
                customPropertyNamePromoteValueCount += 1
            elif customProp['definition']['name'] == customPropertyNamePromoteStream:
                promoteStreamValue = customProp['value']
                logger.info('Mandatory custom property "' + customPropertyNamePromoteStream +
                            '" exists with the value of: ' + str(promoteStreamValue))
                promoteStreamCustomPropFound = True
                streamValueList.append(promoteStreamValue)

        if promoteCustomPropFound and promoteStreamCustomPropFound and customPropertyNamePromoteValueCount == 1:
            logger.info('Both mandatory custom properties have values, proceeding')
            if appIsPromoted:
                logger.info('App is already promoted. No action will be taken. Exiting.')
            else:
                # lookup all of the streams by name to see if they are valid
                streamIDList = []
                matchingStreamList = []
                i = -1
                s, baseUrl = establishRequestsSession('remote')
                logger.info("Getting Stream ID's from remote server by name for streams " +
                            str(streamValueList))
                for stream in streamValueList:
                    i += 1

                    streamIDStatus, streamID, rjson = getRemoteStreamIdsByName(s, baseUrl, stream)
                    if streamIDStatus != 200:
                        logger.debug(
                            'Something went wrong while trying to get the ID for stream: ' + stream)
                        logger.debug('Status: ' + str(streamIDStatus))
                    else:
                        logger.debug('Get stream ID call status: ' + str(streamIDStatus))
                    if streamID != None:
                        matchingStreamList.append(streamValueList[i])
                        streamIDList.append(streamID)
                        logger.info('Stream found: ' + streamValueList[i])
                    else:
                        logger.info('Stream not found: ' + streamValueList[i])

                closeRequestsSession(s)
                logger.info('Stream ID List: ' + str(streamIDList))
                streamExistingCount = len(matchingStreamList)

                if streamExistingCount >= 1 and ('overwrite' in promoteValue.lower() or
                                                 'duplicate' in promoteValue.lower()):

                    s, baseUrl = establishRequestsSession('local')
                    logger.info('Exporting local app')
                    exportAppStatus = exportApp(s, baseUrl, appID, appName)
                    closeRequestsSession(s)
                    if exportAppStatus != 200:
                        logger.debug('Something went wrong while trying to export the app: ' +
                                     str(exportAppStatus))
                    else:
                        logger.debug('App exported: ' + str(exportAppStatus))

                    if 'overwrite' in promoteValue.lower() and streamExistingCount >= 1:
                        logger.info(
                            'Apps that exist with the same name in target streams will be overwritten.'
                            + 'If they do not exist, they will be created.')
                        s, baseUrl = establishRequestsSession('remote')
                        logger.info(
                            "Looking up app ID's to be overwritten on the remote server by name")
                        #remoteAppIDstatus, remoteAppIDs = getRemoteAppIdsByName(s, baseUrl, appName)
                        remoteAppIDstatus, remoteAppIDJSON = getRemoteAppIdsByName(
                            s, baseUrl, appName)
                        numRemoteAppIDs = len(remoteAppIDJSON)

                        if remoteAppIDstatus != 200:
                            logger.debug('Something went wrong when looking up apps by name: ' +
                                         str(remoteAppIDstatus))
                        else:
                            logger.debug('Call to look up apps status: ' + str(remoteAppIDstatus))

                        logger.info('App IDs found with matching names: ' + str(numRemoteAppIDs))

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
                                            })

                            closeRequestsSession(s)
                            numRemoteFoundTargetPublished = len(remoteAppDetailList)

                            logger.info("Matching App ID's: " + str(matchingAppIDs))
                            logger.info(
                                'Number of matching apps with matching names that are published to target streams: '
                                + str(numRemoteFoundTargetPublished))
                            logger.info('Matching app IDs that are published: ' +
                                        str(matchingPublishedAppIDs))
                            logger.debug('App info: ' + str(remoteAppDetailList))

                        leftOverStreamIDList = streamIDList
                        if numRemoteFoundTargetPublished >= 1:
                            s, baseUrl = establishRequestsSession('remote')
                            logger.info('Uploading app onto remote server and getting the new ID')
                            uploadAppStatus, newAppID = uploadApp(s, baseUrl, appName)
                            if uploadAppStatus != 201:
                                logger.debug('Something went wrong while trying to upload the app: '
                                             + str(uploadAppStatus))
                            else:
                                logger.debug("App uploaded: " + str(uploadAppStatus))
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
                                    logger.debug(
                                        "Something went wrong while trying to replace the app(s): " +
                                        str(appReplacedStatus))
                                else:
                                    logger.debug("Successfully replaced app(s): " +
                                                 str(appReplacedStatus))
                                    appPromoted = True

                                try:
                                    popThis = remoteAppID['streamID']
                                    leftOverStreamIDList.remove(popThis)
                                except:
                                    pass
                            closeRequestsSession(s)

                            logger.info("Deleting application that was used to overwrite")
                            s, baseUrl = establishRequestsSession('remote')
                            appDelete(s, baseUrl, newAppID)
                            if appReplacedStatus != 200:
                                logger.debug("Something went wrong while trying to delete the app: "
                                             + str(appReplacedStatus))
                            else:
                                logger.debug("Successfully deleted the app: " +
                                             str(appReplacedStatus))
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
                                        logger.debug(
                                            'Something went wrong while trying to upload the app: ' +
                                            str(uploadAppStatus))
                                    else:
                                        logger.debug("App uploaded: " + str(uploadAppStatus))
                                    closeRequestsSession(s)

                                    s, baseUrl = establishRequestsSession('remote')
                                    logger.info('Publishing app to stream: ' + str(streamID))
                                    appPublishedStatus = publishToStream(
                                        s, baseUrl, newAppID, streamID)
                                    closeRequestsSession(s)
                                    if appPublishedStatus != 200:
                                        logger.debug(
                                            'Something went wrong while trying to publish the app to: '
                                            + str(streamID))
                                    else:
                                        logger.debug('App published status: ' +
                                                     str(appPublishedStatus))
                                        logger.debug('App has been published to ' + str(streamID))
                                        appPromoted = True
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
                                    logger.debug(
                                        'Something went wrong while trying to upload the app: ' +
                                        str(uploadAppStatus))
                                else:
                                    logger.debug("App uploaded: " + str(uploadAppStatus))
                                closeRequestsSession(s)

                                s, baseUrl = establishRequestsSession('remote')
                                logger.info('Publishing app to ' + str(streamID))
                                appPublishedStatus = publishToStream(s, baseUrl, newAppID, streamID)
                                closeRequestsSession(s)
                                if appPublishedStatus != 200:
                                    logger.debug('Something went wrong while trying to publish: ' +
                                                 str(appPublishedStatus))
                                else:
                                    logger.debug('App published status: ' + str(appPublishedStatus))
                                    logger.debug('App has been published to ' + str(streamID))
                                    appPromoted = True
                            else:
                                logger.debug('Could not find stream: ' + str(streamID))

                    elif 'duplicate' in promoteValue.lower():
                        logger.info('App set to duplicate, but no target streams exist. Exiting.')
                    else:
                        logger.info('Something went wrong. Exiting.')

                    # if the app successfully published any apps,
                    # it will consider it a success, and will tag the Qlik Sense app as promoted
                    if appPromoted:
                        s, baseUrl = establishRequestsSession('local')
                        logger.info('Tagging app as promoted')
                        tagAddedStatus = addTagToApp(s, baseUrl, appID, appPromotedTagID)
                        closeRequestsSession(s)
                        if tagAddedStatus != 200:
                            logger.debug(
                                'Something went wrong while trying to add the promoted tag to the app: '
                                + str(tagAddedStatus))
                        else:
                            logger.debug('Promoted tag added to the app: ' + str(tagAddedStatus))
                        localAppDeletedStatus = deleteLocalAppExport(appName)
                        if not localAppDeletedStatus:
                            logger.debug('Something went wrong while trying to delete the app: ' +
                                         str(localAppDeletedStatus))
                        else:
                            logger.debug('Local app deleted: ' + str(localAppDeletedStatus))

                else:
                    logger.info('No matching streams exist on the server. Exiting.')

        elif customPropertyNamePromoteValueCount > 1:
            logger.info('There can only be a single value in the custom property: ' +
                        str(customPropertyNamePromote) + '. Exiting.')
        # if the promote custom property is not found,
        # the app promoted tag will be bounced (removed) if it exists
        elif not promoteCustomPropFound and appIsPromoted:
            logger.info('The ' + customPropertyNamePromote + ' custom property is empty')
            if appIsPromoted:
                logger.info('App is promoted, however the ' + customPropertyNamePromote +
                            ' does not exist')
                logger.info('Removing the promoted tag')
                s, baseUrl = establishRequestsSession('local')
                removeTagStatus = removeTagFromApp(s, baseUrl, appID, appPromotedTagID)
                closeRequestsSession(s)
                if removeTagStatus != 200:
                    logger.debug('Something went wrong while trying to remove the promoted tag: ' +
                                 str(removeStatus))
                else:
                    logger.debug('Tag removed: ' + str(removeTagStatus))

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
        logger.info('App is promoted, however the ' + customPropertyNamePromote + ' does not exist')
        logger.info('Removing the promoted tag')
        s, baseUrl = establishRequestsSession('local')
        removeTagStatus = removeTagFromApp(s, baseUrl, appID, appPromotedTagID)
        closeRequestsSession(s)
        if removeTagStatus != 200:
            logger.debug('Something went wrong while trying to remove the promoted tag: ' +
                         str(removeStatus))
        else:
            logger.debug('Tag removed: ' + str(removeTagStatus))

    if appNumCustomProperties == 0:
        logger.info('No custom properties could be found. Exiting.')

    return 'Finished'