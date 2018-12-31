# Status
[![Project Status: Active – The project has reached a stable, usable state and is being actively developed.](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)

# QRS API Notification Example DevOps Workflow -- Promoting Apps Cross Site with Approvals, Email Alerts, and Versioning

**This repository is intended to be used as an example and should not be used in Production**

## REQUIREMENTS

- Qlik Sense Enterprise April 2018+

## LAYOUT

- [About](#about)
- [Scenario & Workflow](#scenario-and-workflow)
- [Architecture & Components](#architecture-and-components)
- [Installation & Configuration (Including Video)](#installation-and-configuration)
- [Creating Windows Services](#creating-windows-services)
 
## About

Integrated workflow requests are becoming more and more common with Qlik Sense. What all of these requests have in common is: 
- when a particular event occurs in Qlik Sense, I want to automatically do x, y, z. 

Enter the Notification endpoint via the QRS API. The `/qrs/notification` endpoint allows you to "Add a change subscription that makes the QRS call a URL when the specified entity has changed." For example, whenever an app is updated, POST to this URL a JSON block including the GUID of the changed object, for which you can then construct some code to do x, y, z.

For more information on the Notification endpoint of the QRS API, please refer to:
- [Qlik's Developers docs](https://help.qlik.com/en-US/sense-developer/November2018/Subsystems/RepositoryServiceAPI/Content/Sense_RepositoryServiceAPI/RepositoryServiceAPI-Notification-Create-Change-Subscription.htm)
- the [Enterprise Architecture Team's blog on the details](https://eablog.qlikpoc.com/2018/11/01/qlik-sense-repository-notification-api/)


## Scenario and Workflow
The solution I've chosen to create to illustrates app promotion from Qlik Sense site → site with an integrated approval process, versioning, and email alerting. Traditional approaches to each of these facets would either require bulk queries against the Repository API or batch commands to be run at regular intervals. Rather than using approaches which are not coupled with actual events in Qlik Sense, I am using the Notification endpoint to issue a _push_ notification to a series of Python modules where the actions of users are evaluated in real time. This combined with a handful of custom properties applied to Qlik Sense applications, allows for granular control of an approval, versioning, and promotion work-flow. The end result is a more governed approach to development inside of Qlik Sense.

For example, if a user selects the value of _'Approve'_ in the _PromotionApproval_ custom property along with values in several other custom properties (whether to overwrite or duplicate the app, what stream(s) on the other server should it go to, should it be versioned in S3, should it be unpublished after promotion), on _submit_ of those custom properties, the Repository Service will ping an endpoint that will evaluate those custom properties and their values and promote the app to a new site (among other things) if the conditions have been met.


**High-level Workflow**

1. _Sales Rep_ creates an app that he wants to publish to the "Sales" stream on their `Dev` tier. They right-click and publish the app.
![workflow1](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/1_sales_rep_publish.png)
2. _Sales Manager_ gets an email alert that a new app has been published to the "Sales" stream, as he is pre-configured on a list of admin emails for the "Sales" stream.
![workflow1.5](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/2_sales_manager_email_alert.png)
3. _Sales Manager_ reviews the app, and chooses whether to _'Approve'_ or _'Deny'_ it for promotion to `Test`. _Sales Manager_ can see these custom properties, while _Sales Rep_ cannot. If _Sales Manager_ has selected _'Approve'_, they must also select values in the _"PromoteToServer"_ and _"PromoteToStream"_ to promote the app up to `Test`. These custom properties dictate whether the app will overwrite any existing apps with the same name in the destination stream(s) if they exist, or whether to instead duplicate the stream(s). If they select _'Deny'_, the app will not be promoted regardless of the other custom properties, and will instead (optionally) be duplicated and reassigned back to the owner and will also be deleted from the stream. Additionally, if the administrator has versioning in Amazon S3 enabled, they can choose to version the app in S3 by setting _"PromotionS3Versioning"_ to _'True'_.
![workflow3.1](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/3_sales_manager_approve_deny.png)
![workflow3.2](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/3_promotion_approval.png)
![workflow3.3](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/3_promote_to_server.png)
![workflow3.4](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/3_promote_to_stream.png)
![workflow3.5](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/3_promotion_s3_versioning.png)
![workflow3.6](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/3_final_custom_props.png)
4. _Sales Rep_ receives either an _approval_ or _denial_ email depending on what _Sales Manager_ decided.
![workflow4.1](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/approval_email.png)
![workflow4.2](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/denail_email.png)
5. _Optionally_, depending on how you've configured the program, it will duplicate the app and assign it back to the owner, and then delete the published app from the "Sales" stream -- ultimately _unpublishing_ it. This is the default behavior, but it can be modified if the app should stay in the stream.

**Versioning in Amazon S3**

As a part of this workflow, I've also chosen to allow the option to upload the app without data to an S3 bucket with versioning enabled. Enabling this functionality illustrates how to directly couple promotion of applications across tiers in Qlik Sense to versioning of applications. This can be configured easily in the config.json file, however it is setup assuming that your central node has programmatic access to the S3 bucket, e.g. an IAM Role or otherwise. This feature is toggled off by default. You could choose to use your AWS access key id and secret access key, but to do so would require some lightweight modifications to the code in _Modules/app_promote.py_. Right now you will see:

```
s3 = boto3.client("s3")`
```
That code would need to be altered per the boto3 docs to something like this:

```
s3 = boto3.client(
    's3',
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY
)
```
Please reference the boto3 docs here: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html

**Promotion Process**

Regarding the promotion specifically, the high-level concept is that you would select a single value in "PromoteToServer", e.g. 'Test Server - Duplicate', and then select 1-n streams from the "PromoteToStream" custom property. If the streams exist on the remote server, for each stream that exists, the application will export the app, upload it to the new server, and publish it. If the next cycle around, the user then selects 'Test Server - Overwrite', selects 1-n streams, then application would overwrite any existing applications on the server that match by name in the requested streams. If the streams exist on the server but there aren't any matching apps in it, it will upload the app and publish the app to those streams as well. There are additional custom properties regarding approval, versioning, and unpublishing that further enhance this process -- those are detailed below.

![workflow](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/new_workflow.png)


## Architecture and Components
I have chosen to develop the application in Python using Flask, however the same concept could be created in something like NodeJS and Express as well.

Two Python programs that should be run as windows services on system startup (no dependencies needed):

- The listener using Flask. This is the main application that listens for app changes, and acts on them accordingly
- A lightweight program that creates (and validates that the notification subscription exists) every 60 seconds. This is required as the notification subscriptions do not persist, and are gone after the repository service stops. This program runs continuously to ensure that they are always available, created the notification within 60 seconds of the repository service startup.


## Installation and Configuration
**This must be installed on the Central Node of your Qlik Sense site.**

**Installation Video**
[![installation-video](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/Qlik.png)](https://www.youtube.com/watch?v=_WrqiLIlBis)

1. This application is written in Python 3 and Flask requires Python 3.4+. 
2. Port 4242 open on the remote server. Port 4242 is required as we are leveraging certificates to securely communicate with the QRS API, as opposed to going over the proxy. The script could be modified to leverage NTLM, but that is not included in this example. No additional ports need to be opened on the Central Node, as that is where this application will be installed.
3. Once installed, run: ```pip install -r /path/to/requirements.txt``` or just: ```pip install requests flask boto3```
    - Note that `boto3` is only required if you have configured S3 versioning
4. Export certificates from the local Qlik site's QMC with the server name and no password, then do the same for the remote server

![export-certs](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/export_certs.png)

5. Take the client.pem and client_key.pem from the local site export and place them in the `/Certificates/LocalServerCerts/` folder
6. Take the client.pem and client_key.pem from the remote site export and place them in the `/Certificates/RemoteServerCerts/` folder
7. Create the following custom properties in the local server's QMC __(note that many of them start with 'Promot*', as this is key to a security rule that controls the visibility of custom properties by their names. You can change the names of these custom properties as they are referencing in a config, but ensure that any of the properties below that begin with 'Promot*' follow a similar naming convention that can be reflected in the associated security rule as well.)__:
    - PromoteToServer (**Apps**)
        - Contains an arbitrary name of your Qlik Sense site that you want the option of promoting to, as well as a the string 'Overwrite' or 'Duplicate'. Note that this custom property can only serve a single Qlik Sense site by default.
        - Example values:
            - `Test Server - Overwrite`
            - `Test Server - Duplicate`
            ![promote-to-server](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/promoteToServer.png)
    - PromoteToStream (**Apps**)
        - Contains the target stream names (verbatim) on the target server for which you want to give users the option to publish the apps to.
        - Example values:
            - `Everyone`
            - `Review`
            ![promote-to-stream](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/promoteToStream.png)
    - PromotionApproval (**Apps**)
        - Contains the values `Approve` and `Deny`
        - This custom property allows for users to _approve_ or _deny_ the promotion of applications.
        - ![promotion-approval](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/promotionApproval.png)
    - PromotionS3Versioning (**Apps**) *__Optional__*
        - Contains the value `True` that is applied to any app that you'd like versioned in your Amazon S3 bucket
        - ![promotion-s3-versioning](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/promotionS3Versioning.png)
    - PromotionUnpublish (**Apps**) *__Optional__*
        - Contains the value `True`
        - The default behavior of the program is to automatically unpublish the app (duplicate it, assign it to the owner, and then delete the published app -- essentially unpublish) on the approval or denial of the app's promotion. This however can be altered by changing "auto_unpublish" value in config.json to 'false' and providing another custom property. This will change the default behavior to _not_ unpublish the app unless the custom property _"PromotionUnpublish"_ exists with the value of `True` in conjunction with the _"PromotionApproval"_ `Approve` or `Deny`.
        - ![promotion-unpublish](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/promotionUnpublish.png)
    - CanPromote (**Users**)
        - Contains the value `True`
        - The purpose of this custom property is to only allow certain users the ability to promote an app to another Qlik Sense site. There are suggested security rules that leverage this custom property so that only users with this property applied can see custom properties that begin with 'Promot*'
        - ![can-promote](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/canPromote.png)
    - CanPromoteFrom (**Streams**)
        - Contains the value `True`
        - The purpose of this custom property is to control what streams _non-owners_ can promote from. If Bob publishes an app to the _Sales_ stream and Bill has the custom property _"CanPromote"_ with the value `True`, if the stream has _"CanPromoteFrom"_ set to `True` and matching group values (explained later), Bill could promote Bob's app. However, if Bill created the app and published it to the _Sales_ stream and that stream did *not* have the _"CanPromoteFrom"_ set to `True`, Bill could still promote the app, as he is the app owner and also has a value in _"CanPromote"_. The custom properties in these security rule examples are only modified such that some are either available or not.
        - ![can-promote-from](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/canPromoteFrom.png)
    - CanPromoteGroup (**Streams, Users**)
        - Contains _Group_ values that would be defined within your organization. This can just be directed to streams if you want to use something like AD groups instead with user.group. Note that this should be a higher privilege than your standard chosen group for _Read_ access. For example, users with the group of _Sales_ may have read access to the "Sales" stream, however you might only want users with the group of _SalesAdmins_ to have access to promote apps cross-site from "Sales"
        - Example values
            - `HR_Admin`
            - `Marketing_Admin`
            - `Sales_Admin`
        - The purpose for this additional custom property is to control _where_ a non-owner of an application that has the _"CanPromote"_ custom property can promote _from_. George might have the ability to see the _Sales_ stream and the _Marketing_ stream, but you might only want him to be able to promote apps from _Sales_. This custom property is used in a custom security rule to enable that functionality.
        - ![can-promote-group](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/canPromoteGroupNew2.png)
    - EmailAlertOnPublishTo (**Streams**) *__Optional__*
        - Contains the value `True`
        - If you have email alerts enabled in the config, this is the custom property that the program checks for whenever an app is published to a stream. If the stream has this custom property, alerts will be sent to the email addresses associated with the stream's ID in _ApprovalStreamsToEmailAddressMap.csv_.
        - Example csv extract:
            -       StreamID, ApprovalEmailAddress
                    90081726-8077-4a1b-8320-86986ac3e55c, you@you.net
                    cb2f9262-daf5-4131-ba4f-8c857caeca34, them@who.org
                    946d762a-6573-4bd7-86de-c8e2ce26b04d, bark@dog.woof
    - ![email-alert-on-publish-to](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/emailAlertOnPublishTo.png)
8. Security Rules
    - `OwnerUpdateApp`: **Disabled**
    - `ReadCustomProperties`: **Disabled**
    - New Rule #1
        - Purpose: _All users can see all custom properties except for any that begin with "Promot*" - only users with the "CanPromote" property filled have the right to those._
        - Resource filter: `CustomProperty*`
        - Actions: `Update`
        - Conditions `(!user.IsAnonymous() and !(resource.name like "Promot*")) or (!(user.@CanPromote.Empty()) and resource.name like "Promot*")`
        - Context: `Both in hub and QMC`
        ![securityRule#1](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/securityRule1.png)
    - New Rule #2
        - Purpose: _If the user owns the application or ((the stream as the custom property "CanPromoteFrom" and the user has "CanPromote") and (the stream "CanPromoteGroup" is equal to the user's "CanPromoteGroup"))._
        - Resource filter: `App_*`
        - Actions: `Update`
        - Conditions: `(resource.IsOwned() and resource.owner = user) or (!resource.stream.@CanPromoteFrom.empty() and !user.@CanPromote.Empty() and (resource.stream.@CanPromoteGroup = user.@CanPromoteGroup))`
        - Context: `Both in hub and QMC`
        ![securityRule#2](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/securityRule2New.png)
    - New Rule #3 (publish is optional here)
        - Purpose: _If the user's @Group (replace with AD group with .group if you'd like) equals the Stream's @Group, the user can read and publish to the stream._
        - Resource filter: `Stream_*`
        - Actions: `Read, Update`
        - Conditions: `((user.@Group=resource.@Group))`
        - Context: `Both in hub and QMC`
        ![securityRule#3](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/securityRule3.png)
9. Edit the config.json file:

- ```
    {
    	"log_level" 				: "INFO",
    	"internal_central_node_IP"	: "172.31.2.127",			
    	"port"	   					: "5000",
    	"qlik_share_location"		: "\\\\QLIK-DEV-DEMO\\QlikShare",
    	"promote_on_custom_property_change" : {
    		"custom_property_name_promote" 				: "PromoteToServer",
    		"custom_property_name_promote_stream" 		: "PromoteToStream",
    		"custom_property_name_promote_approval" 	: "PromotionApproval",
    		"auto_unpublish_on_approve_or_deny"	: {
    			"auto_unpublish"						: "true",
    			"custom_property_name"					: "PromotionUnpublish"
    		},
    		"local_server_FQDN"							: "qlik-dev-demo",
    		"remote_server_FQDN" 						: "qlik-test-devops.qlikpoc.com",
    		"user_directory" 							: "INTERNAL",
    		"user_id" 									: "sa_api",
    		"email_config": {
    			"promotion_email_alerts"						: "false",
    			"custom_property_name_stream_alert_on_publish"	: "EmailAlertOnPublishTo",
    			"email_UDC_attribute_exists"					: "false",
    			"promotion_sender_email"						: "you@gmail.com",
    			"promotion_sender_pass"							: "h@rdc0dedp@SSw0rd",
    			"promotion_SMTP"								: "smtp.gmail.com",
    			"promotion_SMTP_port"							: "587"
    		},
    		"app_version_on_change" : {
    			"enabled" 				: "false",
    			"custom_property_name" 	: "PromotionS3Versioning",
    			"s3_bucket" 	 		: "notification-api-app-versioning",
    			"prefix"				: "PromotedToTest/"
    		}
    	}
    }
    ```
10. For initial testing, manually run _notification_flask_listener.py_ and _notification_creator.py_
11. Create windows services out of the above two py files to run on system startup using something like NSSM (instructions below) – be sure to stop both of your manually run py files before running the services. Make sure the services are running with an account that is an administrator and that the account has access to the Qlik Sense fileshare location - as that is where it writes the logs to (see config.json above). You can always opt to run the services as the Qlik service account if the account is also an administrator (which it most commonly is).

## Creating Windows Services
I personally use NSSM to easily create windows services. You can follow the below examples, referencing your own Python path and directory path, running nssm from an elevated command prompt with the command nssm install <YourServiceName>

The default path for python.exe is `C:\Users\<USER>\AppData\Local\Programs\Python\{PythonVersion}\python.exe`

![nssm-flask-listener](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/notification_flask_listener.png)

![nssm-flask-listener](https://s3.amazonaws.com/dpi-sse/qlik-qrs-notification-app-promoter/notification_creator.png)
