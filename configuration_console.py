"""
    Configuration Console
"""
import json
from flask import Flask, request
from datetime import timedelta
import base64
import urllib3
import requests
import Modules.smtp_tester as smtp_tester

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
with open("console_port.json") as f:
    CONFIG = json.load(f)

LOCAL_SERVER = "localhost"
PORT = CONFIG["console_port"]

app = Flask(__name__, static_url_path="")
app.url_map.strict_slashes = False

HEADERS = {
    "X-Qlik-Xrfkey": "abcdefg123456789",
    "X-Qlik-User": "UserDirectory=INTERNAL;UserId=sa_api",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36",
}


@app.route("/console")
def root():
    return app.send_static_file("index.html")


@app.route("/write-config", methods=["POST", "OPTIONS"])
def write_config():
    response_json = request.get_json()

    with open("static/config.json") as f:
        config = json.load(f)

    stored_encrypted_pass = config["promote_on_custom_property_change"]["email_config"][
        "promotion_sender_pass"
    ]
    incoming_pass = response_json["promote_on_custom_property_change"]["email_config"][
        "promotion_sender_pass"
    ]

    if stored_encrypted_pass != incoming_pass:
        encoded_pass = base64.b64encode(
            response_json["promote_on_custom_property_change"]["email_config"][
                "promotion_sender_pass"
            ].encode("utf-8")
        ).decode("utf-8")
        response_json["promote_on_custom_property_change"]["email_config"][
            "promotion_sender_pass"
        ] = encoded_pass

    with open("static/config.json", "w") as outfile:
        json.dump(response_json, outfile, indent=4, sort_keys=True)

    return "200"


@app.route("/qrs-test", methods=["POST"])
def qrs_test():
    response_json = request.get_json()
    server = response_json["server"]
    serverType = response_json["serverType"]
    if serverType == "local":
        cert_folder = "Certificates/LocalServerCerts"
    else:
        serverAlias = response_json["serverAlias"]
        cert_folder = "Certificates/" + serverAlias

    s = requests.Session()
    s.headers.update(HEADERS)
    s.cert = (cert_folder + "/client.pem", cert_folder + "/client_key.pem")
    s.verify = False

    try:
        url = (
            "https://"
            + server
            + ":4242/qrs/servernodeconfiguration?xrfkey=abcdefg123456789"
        )
        r = s.get(url)
        rjson = r.json()
        s.close()
        return str([str(r.status_code), url, str(rjson)])
    except Exception as e:
        s.close()
        return str(["Error: ", str(e)])


@app.route("/smtp-test", methods=["POST"])
def smtp_test():
    response_json = request.get_json()
    smtp = response_json["smtp"]
    smtp_port = response_json["smtp_port"]
    sender_address = response_json["sender_address"]
    password = response_json["password"]
    password_decoded = base64.b64decode(password).decode("utf-8")
    destination_address = response_json["destination_address"]

    subject = "QS App Promoter Test Email"
    body = "It works. You're the best."

    try:
        email_test_response = smtp_tester.send_test_email(
            smtp,
            smtp_port,
            sender_address,
            password_decoded,
            destination_address,
            subject,
            body,
        )
        if email_test_response == "200":
            return "200"
        else:
            return email_test_response
    except Exception as e:
        return str(["Error: ", str(e)])


if __name__ == "__main__":
    app.run(host=LOCAL_SERVER, port=PORT)
