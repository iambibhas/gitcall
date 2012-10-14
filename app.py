import os
import sys
import oauth2
import logging, string, random, json
from datetime import datetime
from flask import Flask, redirect, request, session, render_template, url_for, flash
from config import github_oauth_settings as oauth_settings
from config import plivo_settings
from flask.ext.sqlalchemy import SQLAlchemy
from github import Github
import plivo

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/gitcall.db'
db = SQLAlchemy(app)

if os.environ.get('ENV', 'prod') == 'dev':
    logging.basicConfig(filename='app.log',level=logging.DEBUG)
else:
    logging.basicConfig(stream=sys.stderr)

from werkzeug.contrib.cache import SimpleCache
cache = SimpleCache()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120))
    mobile = db.Column(db.Integer)
    access_token = db.Column(db.String(64), unique=True)

    linked_repos = db.relationship('UserRepo', backref='user', lazy='joined')
    notifications = db.relationship('Notification', backref='user', lazy='joined')

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
        return '<UserRepo %r/%r>' % (self.user_id, self.repo_name)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    # Commit messages can be huge. Saving some of it.
    # Also, max 'Speak' text length of Plivo is not defined. :-/
    text = db.Column(db.String(512))
    create_time = db.Column(db.DateTime)

    def __init__(self, user_id, text):
        self.user_id = user_id
        self.text = text
        self.create_time = datetime.utcnow()

    def __repr__(self):
        return '<Notification %r:%r>' % (self.user_id, self.create_time)


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
    try:
        repos = cache.get('repos')
        if repos is None:
            repos = app.gituser.get_repos()
            cache.set('repos', repos, timeout = 60)
    except Exception as e:
        flash(str(e))
        repos = False

    return render_template(
        'home.html', 
        logged_in = logged_in,
        user = user,
        repolinks = repolinks,
        repos = repos
    )        

@app.route('/add/mobile/', methods=['POST'])
def add_mobile():
    if 'username' not in session:
        return redirect(url_for('home'))

    try:
        user = User.query.filter_by(id = session['userid']).first()
        user.mobile = request.form['mobile']
        db.session.commit()
        flash('Mobile number added.')
    except Exception as e:
        logging.debug(sys.exc_info())
        flash(str(e))

    return redirect(url_for('home'))

@app.route('/add/<repo_name>', methods=['GET'])
def add_hook(repo_name):
    if 'username' not in session:
        return redirect(url_for('home'))

    try:
        userrepo = UserRepo.query.filter_by(user_id=session['userid'], repo_name=repo_name).first()
        logging.debug(userrepo)
        if userrepo is not None:
            flash('Already added the repository')
        
        repo = app.gituser.get_repo(repo_name)
        userrepo = UserRepo(session['userid'], repo.name)
        db.session.add(userrepo)
        db.session.commit()

        config = {
            "url": "http://%s/answer/%s" % (request.headers['HOST'], userrepo.token),
            "content_type": "json"
        }
        response = repo.create_hook('web', config)
        
        flash('Repository successfully added')
    except Exception as e:
        flash(str(e))

    return redirect(url_for('home'))

@app.route('/answer/<token>', methods=['POST'])
def answer(token):
    response = json.loads(request.data)
    name = response['pusher']['name']
    repo = response['repository']['name']
    commit_msg = response['head_commit']['message']

    userrepo = UserRepo.query.filter_by(token = token).first()
    if userrepo is None:
        return 'Invalid token'

    if userrepo.user.username != name or userrepo.repo_name != repo:
        return 'Invalid hook'

    app.message= '%s pushed a commit to %s, %s' % (name, repo, commit_msg)

    params = {
        'to': '919836510821',
        'from': '919836510821',
        'answer_url': 'http://%s/answer/plivo/' % request.headers['HOST'],
    }
    (status_code, response) = app.plivo_client.make_call(params)
    return str(response)

@app.route('/answer/plivo/', methods=['POST'])
def answer_plivo():
    resp = plivo.Response()
    if request.form['Event'] == 'StartApp':
        resp.addSpeak('Hi, This is a Git hub notification.', voice = 'MAN')
        resp.addWait(length=1)
        resp.addSpeak(app.message, voice = 'MAN')

        app.message = ''

    return resp.to_xml()

@app.route('/logout/', methods=['GET'])
def logout():
    session.pop('username', None)
    session.pop('userid', None)
    app.user = None
    return redirect(url_for('home'))

@app.route('/login/', methods=['GET'])
def login():
    try:
        oauth_client = oauth2.Client2(
            oauth_settings['client_id'],
            oauth_settings['client_secret'],
            oauth_settings['base_url'],
            disable_ssl_certificate_validation=True
        )
        authorization_url = oauth_client.authorization_url(
            redirect_uri='http://%s/login/callback/' % request.headers['HOST'],
            params={'scope': 'user,repo'}
        )
        logging.debug('authorization_url: %s' % authorization_url)
        return redirect(authorization_url)
    except Exception as e:
        flash(str(e))
        return redirect(url_for('home'))

@app.route('/login/callback/', methods=['GET'])
def callback():
    try:
        oauth_client = oauth2.Client2(
            oauth_settings['client_id'],
            oauth_settings['client_secret'],
            oauth_settings['base_url'],
            disable_ssl_certificate_validation=True
        )
        code = request.args.get('code', '')
        data = oauth_client.access_token(
            code, 
            'http://%s/login/callback/' % request.headers['HOST'],
        )
        access_token = data.get('access_token')
        logging.debug(access_token)
        (headers, body) = oauth_client.request(
            'https://api.github.com/user',
            access_token=access_token,
            token_param='access_token'
        )
        logging.debug(headers.get('status'))
        # logging.debug(body)
        bodyobj = json.loads(body)
        # logging.debug(bodyobj)

        user = User.query.filter_by(username = bodyobj['login']).first()
        if user is None:
            user = User(bodyobj['login'], bodyobj['email'], access_token)
            db.session.add(user)
            db.session.commit()

        app.github = Github(access_token)
        app.gituser = app.github.get_user()

        session['username'] = bodyobj['login']
        session['userid'] = user.id

    except Exception as e:
        flash(str(e))

    return redirect(url_for('home'))

if __name__ == '__main__':
    # Bind to PORT if defined, otherwise default to 5000.
    port = int(os.environ.get('PORT', 5000))
    ENV = os.environ.get('ENV', 'prod')
    debug = (ENV == 'dev')
    app.secret_key = os.urandom(24)
    app.plivo_client = plivo.RestAPI(plivo_settings['auth_id'], plivo_settings['auth_token'])
    app.run(host='0.0.0.0', port=port, debug = debug)