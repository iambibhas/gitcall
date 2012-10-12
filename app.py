import os
import oauth2
import logging, string, random, json
from datetime import datetime
from flask import Flask, redirect, request, session, render_template, url_for, flash
from config import github_oauth_settings as oauth_settings
from flask.ext.sqlalchemy import SQLAlchemy
from github import Github

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/gitcall.db'
db = SQLAlchemy(app)
logging.basicConfig(filename='app.log',level=logging.DEBUG)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120))
    access_token = db.Column(db.String(64), unique=True)
    linked_repos = db.relationship('UserRepo', backref='user', lazy='select')

    def __init__(self, username, email, access_token):
        self.username = username
        self.email = email
        self.access_token = access_token

    def __repr__(self):
        return '<User %r>' % self.username


class UserRepo(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    repo_name = db.Column(db.String(256))
    token = db.Column(db.String(8), unique=True)
    create_date = db.Column(db.DateTime)

    def __init__(self, user_id, repo_name):
        self.user_id = user_id
        self.repo_name = repo_name
        self.token = ''.join([random.choice(string.ascii_lowercase + string.octdigits) for x in range(8)])
        self.create_date = datetime.utcnow()

    def __repr__(self):
        return '<UserRepo %r/%r>' % (self.user.username, self.repo_name)

@app.route('/')
def home():
    logged_in = False
    
    if 'username' not in session:
        return render_template(
            'home.html', 
            logged_in = logged_in
        )
    
    logged_in = True
    user = User.query.filter_by(username = session['username']).first()
    repolinks = UserRepo.query.filter_by(user_id = user.id).all()
    repos = app.github.get_user().get_repos()

    return render_template(
        'home.html', 
        logged_in = logged_in,
        user = user,
        repolinks = repolinks,
        repos = repos
    )        

@app.route('/add/<repo_name>', methods=['GET'])
def add_hook(repo_name):
    if 'username' not in session:
        return redirect(url_for('home'))

    try:
        repo = app.github.get_user().get_repo(repo_name)

        userrepo = UserRepo(session['userid'], repo.name)
        db.session.add(userrepo)
        db.session.commit()
        
        return redirect(url_for('home'))
    except Exception as e:
        return redirect(url_for('home'))

@app.route('/answer/', methods=['POST'])
def answer():
    return 'answered'

@app.route('/logout/', methods=['GET'])
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

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
    bodyobj = json.loads(body)
    logging.debug(bodyobj)

    user = User.query.filter_by(username = bodyobj['login']).first()
    if user is None:
        user = User(bodyobj['login'], bodyobj['email'], access_token)
        db.session.add(user)
        db.session.commit()

    app.github = Github(access_token)

    session['username'] = bodyobj['login']
    session['userid'] = user.id
    return redirect(url_for('home'))

if __name__ == '__main__':
    # Bind to PORT if defined, otherwise default to 5000.
    port = int(os.environ.get('PORT', 5000))
    ENV = os.environ.get('ENV', 'prod')
    debug = (ENV == 'dev')
    app.secret_key = os.urandom(24)
    app.run(host='0.0.0.0', port=port, debug = debug)