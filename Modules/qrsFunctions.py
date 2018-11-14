import requests
import json
import urllib3
import uuid
import os
from datetime import datetime, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# configuration
with open('config.json') as f:
    config = json.load(f)

localServer = config['promoteOnCustomPropertyChange']['localServer']
remoteServer = config['promoteOnCustomPropertyChange']['remoteServer']
userDirectory = config['promoteOnCustomPropertyChange']['userDirectory']
userId = config['promoteOnCustomPropertyChange']['userId']

# build URLs
localBaseUrl = 'https://' + localServer + ':4242'
remoteBaseUrl = 'https://' + remoteServer + ':4242'


def establishRequestsSession(serverLocation):
    # Setup Session
    s = requests.Session()

    if serverLocation.lower() == 'local':
        certFolder = 'Certificates/LocalServerCerts'
        baseUrl = localBaseUrl
    elif serverLocation.lower() == 'remote':
        certFolder = 'Certificates/RemoteServerCerts'
        baseUrl = remoteBaseUrl

    # set headers
    headers = {
        "X-Qlik-Xrfkey":
        "abcdefg123456789",
        "X-Qlik-User":
        "UserDirectory=" + userDirectory + ";UserId=" + userId,
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36"
    }

    # add certs to headers
    s.headers.update(headers)
    s.cert = (certFolder + "/client.pem", certFolder + "/client_key.pem")
    s.verify = False

    return s, baseUrl


def closeRequestsSession(s):
    # close the session
    s.close()


def appFull(s, baseUrl, appID):
    # get app full
    r = s.get(baseUrl + "/qrs/app/full?filter=id eq " +
              appID + "&xrfkey=abcdefg123456789")
    rjson = r.json()[0]

    return r.status_code, rjson


def exportApp(s, baseUrl, appID, appName, skipData=False):
    temp_GUID = str(uuid.uuid4())
    if skipData:
        r = s.post(baseUrl + "/qrs/app/" + appID + "/export/" +
                   temp_GUID + "?skipData=true&xrfkey=abcdefg123456789")
    else:
        r = s.post(baseUrl + "/qrs/app/" + appID + "/export/" +
                   temp_GUID + "?xrfkey=abcdefg123456789")

    rjson = r.json()
    download_path = str(rjson["downloadPath"])
    r = s.get(baseUrl + download_path, stream=True)

    with open('ExportedApps/' + appName + '.qvf', 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
        f.close()

    return r.status_code


def uploadApp(s, baseUrl, appName):
    data = open('ExportedApps/' + appName + '.qvf', 'rb').read()
    r = s.post(
        baseUrl + "/qrs/app/upload?name=" + appName + "&xrfkey=abcdefg123456789",
        data=data,
        headers={"Content-Type": "application/vnd.qlik.sense.app"})
    rjson = r.json()
    newAppID = rjson['id']

    return r.status_code, newAppID


def getRemoteAppIdsByName(s, baseUrl, appName):
    r = s.get(baseUrl + "/qrs/app/full?filter=name eq '" +
              appName + "'&xrfkey=abcdefg123456789")
    rjson = r.json()

    return r.status_code, rjson


def getRemoteStreamIdsByName(s, baseUrl, streamName):
    r = s.get(baseUrl + "/qrs/stream/full?filter=name eq '" + streamName +
              "'&xrfkey=abcdefg123456789")
    rjson = r.json()
    try:
        streamID = rjson[0]['id']
    except IndexError:
        streamID = None

    return r.status_code, streamID, rjson


def publishToStream(s, baseUrl, appID, streamID):
    # publish the app
    r = s.put(baseUrl + "/qrs/app/" + appID + "/publish?stream=" + streamID +
              "&xrfkey=abcdefg123456789")

    return r.status_code


def appReplace(s, baseUrl, appID, targetAppID):
    # replace the app
    r = s.put(baseUrl + "/qrs/app/" + appID + "/replace?app=" + targetAppID +
              "&xrfkey=abcdefg123456789")

    return r.status_code


def appDelete(s, baseUrl, appID):
    # delete the app
    r = s.delete(baseUrl + "/qrs/app/" + appID + "?xrfkey=abcdefg123456789")

    return r.status_code


def duplicateApp(s, baseUrl, appID, appName):
    # coppy the app
    r = s.post(baseUrl + "/qrs/app/" + appID + "/copy?name=" +
               appName + "&xrfkey=abcdefg123456789")
    rjson = r.json()
    dupAppID = rjson['id']

    return r.status_code, dupAppID


def addTagToApp(s, baseUrl, appID, tagID):
    status, rjson = appFull(s, baseUrl, appID)

    rjson['tags'].append(dict({"id": tagID}))
    rjson['modifiedDate'] = str(
        ((datetime.today()) + timedelta(days=1)).isoformat() + 'Z')
    data = json.dumps(rjson)

    # add the tag to the app
    r = s.put(
        baseUrl + "/qrs/app/" + appID + "?xrfkey=abcdefg123456789",
        data=data,
        headers={"Content-Type": "application/json"})

    return r.status_code


def removeTagFromApp(s, baseUrl, appID, tagID):
    status, rjson = appFull(s, baseUrl, appID)

    for i in range(len(rjson['tags'])):
        if rjson['tags'][i]['id'] == tagID:
            del rjson['tags'][i]

    rjson['modifiedDate'] = str(
        ((datetime.today()) + timedelta(days=1)).isoformat() + 'Z')
    data = json.dumps(rjson)

    # put the app without the tag
    r = s.put(
        baseUrl + "/qrs/app/" + appID + "?xrfkey=abcdefg123456789",
        data=data,
        headers={"Content-Type": "application/json"})

    return r.status_code


def deleteLocalAppExport(appName):
    try:
        os.remove('ExportedApps/' + appName + '.qvf')
        return True
    except:
        return False


def modifyAppDescription(s, baseUrl, appID, description):
    status, rjson = appFull(s, baseUrl, appID)

    rjson['modifiedDate'] = str(
        ((datetime.today()) + timedelta(days=1)).isoformat() + 'Z')
    rjson['description'] = description

    data = json.dumps(rjson)

    r = s.put(
        baseUrl + "/qrs/app/" + appID + "?xrfkey=abcdefg123456789",
        data=data,
        headers={"Content-Type": "application/json"})

    return r.status_code
