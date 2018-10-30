from flask import Flask, request
from Modules.appFunctions import promoteApp

app = Flask(__name__)
app.url_map.strict_slashes = False


# any app update event will trigger this function
@app.route("/app/update", methods=['POST'])
def appupdate():
    '''
    Function to promote an app to another Qlik Sense site on certain app updates
    '''

    responseJSON = request.get_json()

    appID = responseJSON[0]['objectID']

    return promoteApp(appID)


if __name__ == '__main__':
    app.run(port=5000)