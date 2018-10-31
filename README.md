# Status
[![Project Status: Active – The project has reached a stable, usable state and is being actively developed.](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)

# QRS API Notification Example DevOps Workflow -- Promoting Apps Cross Site

**This repository is intended to be used as an example and should not be used in Production**

## REQUIREMENTS

- Qlik Sense Enterprise June 2017+

## LAYOUT

- [About](#about)
- [Scenario & Example](#scenario-and-example)
- [Architecture & Components](#architecture-and-components)
- [Installation & Configuration](#installation-and-configuration)
- [Usage](#usage)
- [Example Output](#example-output)
- [Creating Windows Services](#creating-windows-services)
 
## About

Integrated workflow requests are becoming more and more common in 2018. What all of these requests have in common is: when a particular event occurs in Qlik Sense, I want to automatically do x, y, z. Enter the Notification endpoints via the QRS API. The `/qrs/notification` endpoint allows you to "Add a change subscription that makes the QRS call a URL when the specified entity has changed." For example, whenever an app is updated, POST to this URL a JSON block including the GUID of the changed object, for which you can then construct some code to do x, y, z.


## Scenario and Example
A common scenario that I've chosen to illustrate is: "How do I automatically/programatically promote apps through my Qlik Sense tiers, e.g. from Dev → Test → Prod, without doing it in batch with tools like the Qlik CLI?" In the example I've created, I have used the scenario above: whenever an app is updated, POST to this URL. Having this information sent every time the app is updated, allows me to then create a workflow to push and publish apps to other servers based off of conditions. The intended usage of this application is that it should be single site → single site. For example, it should be installed on 'Dev' with the option of promoting to 'Test', and then installed on 'Test' with the option of promoting to 'Prod'. The application could easily be edited to have the ability to post to multiple servers as well, but it defaults to one.

The application is managed via Qlik Sense custom properties and tags:

- Custom Properties (they can be named whatever you'd like, and are referenced in a config) applied at the App level:
    - PromoteToServer
        - Contains an arbitrary name of your Qlik Sense tier that you want the option of promoting to, as well as a the string 'Overwrite' or 'Duplicate'.
        - Example values:
            - 'Test Server - Overwrite'
            - 'Test Server - Duplicate'
    - PromoteToStream
        - Contains the target stream names (verbatim) on the target server for which you want to give users the option to publish the apps to
        - Example values:
            - 'Everyone'
            - 'Review'
- A single Tag:
    - A tag that will be applied to an app to illustrate that the app has been pushed to the server
    - Example tag: 'PromotedToTest'

Example (the tag gets added programmatically after the app has been promoted):

![customProps](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/custom_props.png)

The high-level concept is that you would select a single value in "PromoteToServer", e.g. 'Test Server - Duplicate', and then select 1-n streams from the "PromoteToStream" custom property. If the streams exist on the remote server and the app is not already tagged as promoted, for each stream that exists, the application will export the app, upload it to the new server, and publish it – thereby tagging the app on completion so the cycle doesn't continue on every app update. If the user then removes the custom properties (or tag directly), the tag will be removed from the app, and the cycle would continue. The user could then select 'Test Server - Overwrite', select 1-n streams, and the application would overwrite any existing applications on the server that match by name in the requested streams – and if the streams exist on the server but there aren't any matching apps in it, it will upload the app and publish the app to those streams as well.

![workflow](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/QRS+Notification+API+-+App+Promotion+Example+Workflow.png)

Please reference the application's complete decision workflow in the flowchart below. 
*Note that data will be sent to the URL on every app change, so if the criteria is not met, the application will simply do nothing.*

![decisionTree](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/Notification+API+Example+DevOps+Workflow+for+Promoting+Apps+Cross+Server+(5).png)

## Architecture and Components
I have chosen to develop the application in Python using Flask, however the same concept could be created in something like NodeJS and Express as well.

Two Python programs that should be run as windows services on system startup (no dependencies needed):

- The listener using Flask. This is the main application that listens for app changes, and acts on them accordingly
- A lightweight program that creates (and validates that the notification subscription exists) every 60 seconds. This is required as the notification subscriptions do not persist, and are gone after the repository service stops. This program runs continuously to ensure that they are always available, created the notification within 60 seconds of the repository service startup.


## Installation and Configuration
1. This application is written in Python 3 and Flask requires Python 3.4+. 
2. Port 4242 open on the remote server (and local server if you are running this somewhere other than the Qlik Sense server of the lower tier, which is assumed). Port 4242 is required as we are leveraging certificates to securely communicate with the QRS API, as opposed to going over the proxy. The script could be modified to leverage NTLM, but that is not included in this example.
3. Once installed, run: ```pip install -r /path/to/requirements.txt``` or just: ```pip install requests flask```
4. Export certificates from the local Qlik site's QMC with the server name and no password, then do the same for the remote server

![export-certs](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/export_certs.png)

5. Take the client.pem and client_key.pem from the local site export and place them in the `/Certificates/LocalServerCerts/` folder
6. Take the client.pem and client_key.pem from the remote site export and place them in the `/Certificates/RemoteServerCerts/` folder
7. Create two custom properties in the local server's QMC (they can be named whatever you'd like, and are referenced in a config):
    - PromoteToServer
        - Contains an arbitrary name of your Qlik Sense tier that you want the option of promoting to, as well as a the string 'Overwrite' or 'Duplicate'.
        - Example values:
            - 'Test Server - Overwrite'
            - 'Test Server - Duplicate'
            ![promote-to-server](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/promoteToServer.png)
    - PromoteToStream
        - Contains the target stream names (verbatim) on the target server for which you want to give users the option to publish the apps to
        - Example values:
            - 'Everyone'
            - 'Review'
            ![promote-to-stream](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/promoteToStream.png)
8. Create a tag that will be applied to an app to illustrate that the app has been pushed to the server
    - Example tag: 'Promoted'
9. Edit the config.json file:
    - Set your logging level. Default is "INFO", however "DEBUG" is also available
    - Set the name of your custom properties
    - Set the GUID of your created tag (you can get this from the QMC by clicking on 'Tag's, then selecting 'ID' via the column selector in the top right.
    - Set the URL for you local server
    - Set the URL for your remote server
    - Set the user directory and user id – I suggest leaving these as the default, "INTERNAL" "sa_api"
    ![config](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/config.png)
10. For initial testing, manually run _notificationFlaskListener.py_ and _notificationCreator.py_
11. Create windows services out of the above two py files to run on system startup using something like NSSM (instructions below) – be sure to stop both of your manually run py files before running the services


## Usage
You can edit these custom properties from both the QMC and the Hub (provided you are on a Qlik Sense version that offers that capability). The tag will programatically be applied to the app once the criteria has been met and the result successful, i.e.a single value in the "PromoteToServer" property exists and 1-n values in the "PromoteToStream" custom property exist. You can "pop-off" this tag by removing the "PromoteToServer" values and/or by removing values from both custom properties. This will then allow you to start the process over, by either duplicating the app to a new stream, or overwriting it. If the tag exists, nothing will happen on any app update, so it must be removed to start the process over again.

**On Dev Server – Manage App Properties from hub**

![promote-to-server-prop](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/promoteToServerProp.png)
![promote-to-server-prop](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/promoteToStreamProp.png)
![hit-apply](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/hitApply2.png)

**On Test Server**

![no-app](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/no_apps.png)

_moments later..._

![app](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/app.png)

**On Dev Server:**

![tag-on-success](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/tagOnSuccess.png)

Remove the custom property values for "PromoteToServer" or remove both values for both mandatory custom properties, and the tag will be popped off, allowing you to promote again.

**Example Output**
Here is an example logging output after setting the "PromoteToServer" custom property to overwrite to the test server, and setting three target streams ('Everyone', 'Review', and 'Foo'). The app with the same name on the remote server already exists in the 'Everyone' stream, so it is replaced, while the 'Review' stream exists but a matching app does not, so it is imported and published to, and finally the 'Foo' stream does not exist, so nothing happens there.

```
2018-10-25 15:15:31,713 - __main__ - INFO - _____________App Updated_____________
2018-10-25 15:15:31,715 - __main__ - INFO - App ID: 31ee79a6-0949-4175-ba0e-1866a60e3336
2018-10-25 15:15:31,717 - __main__ - INFO - Requesting app/full info on 31ee79a6-0949-4175-ba0e-1866a60e3336
2018-10-25 15:15:31,759 - __main__ - INFO - App Name: Demo Build
2018-10-25 15:15:31,759 - __main__ - INFO - App Number of Custom Properties: 4
2018-10-25 15:15:31,760 - __main__ - INFO - Checking to see if app is tagged as promoted
2018-10-25 15:15:31,761 - __main__ - INFO - App is tagged as not promoted
2018-10-25 15:15:31,761 - __main__ - INFO - Searching app/full to see if "PromoteToServer" and/or "PromoteToStream" custom properties exist
2018-10-25 15:15:31,762 - __main__ - INFO - Mandatory custom property "PromoteToServer" exists with the value of: Test - Overwrite
2018-10-25 15:15:31,763 - __main__ - INFO - Mandatory custom property "PromoteToStream" exists with the value of: Review
2018-10-25 15:15:31,764 - __main__ - INFO - Mandatory custom property "PromoteToStream" exists with the value of: Foo
2018-10-25 15:15:31,764 - __main__ - INFO - Mandatory custom property "PromoteToStream" exists with the value of: Everyone
2018-10-25 15:15:31,765 - __main__ - INFO - Both mandatory custom properties have values, proceeding
2018-10-25 15:15:31,765 - __main__ - INFO - Getting Stream ID's from remote server by name for streams ['Review', 'Foo', 'Everyone']
2018-10-25 15:15:31,868 - __main__ - INFO - Stream found: Review
2018-10-25 15:15:31,896 - __main__ - INFO - Stream not found: Foo
2018-10-25 15:15:31,915 - __main__ - INFO - Stream found: Everyone
2018-10-25 15:15:31,917 - __main__ - INFO - Stream ID List: ['88d0986f-b110-4c9e-8b60-d07ccc8b8caf', 'aaec8d41-5201-43ab-809f-3063750dfafd']
2018-10-25 15:15:31,918 - __main__ - INFO - Exporting local app
2018-10-25 15:15:33,832 - __main__ - INFO - Apps that exist with the same name in target streams will be overwritten.If they do not exist, they will be created.
2018-10-25 15:15:33,832 - __main__ - INFO - Looking up app ID's to be overwritten on the remote server by name
2018-10-25 15:15:34,062 - __main__ - INFO - App IDs found with matching names: 1
2018-10-25 15:15:34,064 - __main__ - INFO - Matching App ID's: ['c4e34866-de12-4eb0-82ed-e43e94e0de1a']
2018-10-25 15:15:34,064 - __main__ - INFO - Number of matching apps with matching names that are published to target streams: 1
2018-10-25 15:15:34,065 - __main__ - INFO - Matching app IDs that are published: ['c4e34866-de12-4eb0-82ed-e43e94e0de1a']
2018-10-25 15:15:34,066 - __main__ - INFO - Uploading app onto remote server and getting the new ID
2018-10-25 15:15:37,879 - __main__ - INFO - Overwriting existing apps with matching names published to target streams
2018-10-25 15:15:39,602 - __main__ - INFO - Deleting application that was used to overwrite
2018-10-25 15:15:40,042 - __main__ - INFO - Uploading and publishing apps to existing streams that did not contain any matching app names
2018-10-25 15:15:40,043 - __main__ - INFO - Uploading app onto remote server and getting the new ID
2018-10-25 15:15:43,534 - __main__ - INFO - Publishing app to stream: 88d0986f-b110-4c9e-8b60-d07ccc8b8caf
2018-10-25 15:15:43,857 - __main__ - INFO - Tagging app as promoted
```

## Creating Windows Services
I personally use NSSM to easily create windows services. You can follow the below examples, referencing your own Python path and directory path, running nssm from an elevated command prompt with the command nssm install {YourServiceName}

The default path for python.exe is `C:\Users\{USER}\AppData\Local\Programs\Python\{PythonVersion}\python.exe`

![nssm-flask-listener](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/nssm_flask_listener.png)

![nssm-flask-listener](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/nssm_notification_creator.png)

![nssm-services](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/nssm_Services.png)



Be sure to then start the services.
