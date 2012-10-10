import os
import oauth2
import logging, string, random
from flask import Flask, redirect, request
from config import github_oauth_settings as oauth_settings
from flask.ext.sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/gitcall.db'
db = SQLAlchemy(app)
logging.basicConfig(filename='app.log',level=logging.DEBUG)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120), unique=True)
    access_token = db.Column(db.String(64), unique=True)

    def __init__(self, username, email, token):
        self.username = username
        self.email = email
        self.token = token

    def __repr__(self):
        return '<User %r>' % self.username


class UserRepo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship(
        'User', 
        backref = db.backref('linked_repos', lazy='dynamic')
    )
    repo_id = db.Column(db.Integer, unique=True)
    repo_name = db.Column(db.String(256))
    token = db.Column(db.String(8), unique=True)
    create_date = db.Column(db.DateTime)

    def __init__(self, user, repo_id, repo_name):
        self.user = user
        self.repo_id = repo_id
        self.repo_name = repo_name
        self.token = ''.join([random.choice(string.ascii_lowercase + string.octdigits) for x in range(8)])
        self.create_date = datetime.utcnow()

    def __repr__(self):
        return '<UserRepo %r/%r>' % (self.user.username, self.repo_name)

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