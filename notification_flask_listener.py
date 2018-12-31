"""
    Flask Listener
"""
import json
from flask import Flask, request
from Modules.app_promote import promote_app
from Modules.app_publish_review import email_on_publish_to_review

# Configuration
with open("CONFIG.json") as f:
    CONFIG = json.load(f)
    f.close()

INTERNAL_CENTRAL_NODE_IP = CONFIG["internal_central_node_IP"]
PORT = CONFIG["port"]

app = Flask(__name__)
app.url_map.strict_slashes = False

# any app update event will trigger this function


@app.route("/app/update/promote", methods=['POST'])
def app_update_promote():
    '''
    Function to promote an app to another Qlik Sense site on certain app updates
    '''
    response_json = request.get_json()

    app_id = response_json[0]['objectID']
    print(str(response_json))

    return promote_app(app_id)


@app.route("/app/publish/review", methods=['POST'])
def app_publish_review():
    '''
    Function that is triggered when an app is published to the stream
    configured as the "review"

    Function triggers an email alert to target address
    '''

    response_json = request.get_json()

    app_id = response_json[0]['objectID']

    return email_on_publish_to_review(app_id)


if __name__ == '__main__':
    app.run(host=INTERNAL_CENTRAL_NODE_IP, port=PORT)
