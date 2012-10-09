import os
import oauth2
import logging
from flask import Flask, redirect, request
from config import github_oauth_settings as oauth_settings

app = Flask(__name__)
logging.basicConfig(filename='app.log',level=logging.DEBUG)

@app.route('/')
def home():
    return 'Hello World rlad!'

@app.route('/answer/', methods=['POST'])
def answer():
    return 'answered'

@app.route('/login/', methods=['GET'])
def login():
    oauth_client = oauth2.Client2(
        oauth_settings['client_id'],
        oauth_settings['client_secret'],
        oauth_settings['base_url'],
        disable_ssl_certificate_validation=True
    )
    authorization_url = oauth_client.authorization_url(
        redirect_uri=oauth_settings['redirect_url'],
        params={'scope': 'user,repo'}
    )
    logging.debug('authorization_url: %s' % authorization_url)
    return redirect(authorization_url)

@app.route('/login/callback/', methods=['GET'])
def callback():
    oauth_client = oauth2.Client2(
        oauth_settings['client_id'],
        oauth_settings['client_secret'],
        oauth_settings['base_url'],
        disable_ssl_certificate_validation=True
    )
    code = request.args.get('code', '')
    data = oauth_client.access_token(
        code, 
        oauth_settings['redirect_url'],
    )
    access_token = data.get('access_token')
    logging.debug(access_token)
    (headers, body) = oauth_client.request(
        'https://api.github.com/user',
        access_token=access_token,
        token_param='access_token'
    )
    logging.debug(headers.get('status'))
    logging.debug(body)
    return body

if __name__ == '__main__':
    # Bind to PORT if defined, otherwise default to 5000.
    port = int(os.environ.get('PORT', 5000))
    ENV = os.environ.get('ENV', 'prod')
    debug = (ENV == 'dev')
    app.run(host='0.0.0.0', port=port, debug = debug)