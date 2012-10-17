import os
import sys
import oauth2
import logging, string, random, json
from functools import wraps
from datetime import datetime
from flask import Flask, redirect, request, session, render_template, url_for, flash
from config import github_oauth_settings as oauth_settings
from config import plivo_settings
from flask.ext.sqlalchemy import SQLAlchemy
from github import Github
import plivo

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/gitcall.db'
app.config['SESSION_COOKIE_NAME'] = 'gitcall'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_LIFETIME'] = 6*60*60


db = SQLAlchemy(app)

if os.environ.get('ENV', 'prod') == 'dev':
    app.config['SECRET_KEY'] = 'development secret key here'
    app.config['SERVER_NAME'] = 'gitcall.local:5000'
    logging.basicConfig(filename='app.log', level=logging.DEBUG)
else:
    app.config['SERVER_NAME'] = 'gitcall.bibhas.in'
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

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

    notifications = db.relationship('Notification', backref='userrepo', lazy='joined')

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
    user_repo_id = db.Column(db.Integer, db.ForeignKey('user_repo.id'))
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

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            flash('You need to Login first!')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    if 'logged_in' not in session or not session['logged_in']:
        logging.debug('Not logged in %r' % session)
        return render_template(
            'home.html'
        )
    
    logging.debug('Logged in %r' % session)
    repolinks = UserRepo.query.filter_by(user_id = user.id).all()
    try:
        repos = cache.get('repos')
        logging.debug('Repositories from Cache: %r' % repos)
        if not repos:
            repos = session['gituser'].get_repos()
            logging.debug('Repositories from API: %r' % repos)
            cache.set('repos', repos, timeout = 60)
    except Exception as e:
        flash(str(e))
        repos = False

    return render_template(
        'home.html',
        repolinks = repolinks,
        repos = repos
    )        

@app.route('/add/mobile/', methods=['POST'])
@login_required
def add_mobile():
    try:
        user = User.query.filter_by(id = session['user'].id).first()
        user.mobile = request.form['mobile']
        db.session.commit()
        flash('Mobile number added.')
    except Exception as e:
        logging.debug(sys.exc_info())
        flash(str(e))
    return redirect(url_for('home'))

@app.route('/add/<repo_name>', methods=['GET'])
@login_required
def add_hook(repo_name):
    try:
        userrepo = UserRepo.query.filter_by(user_id=session['user'].id, repo_name=repo_name).first()
        logging.debug(userrepo)
        if userrepo is not None:
            flash('Already added the repository')
        
        repo = session['gituser'].get_repo(repo_name)
        userrepo = UserRepo(session['user'].id, repo.name)
        db.session.add(userrepo)
        db.session.commit()

        config = {
            "url": "http://%s/answer/%s" % (request.headers['HOST'], userrepo.token),
            "content_type": "json"
        }
        response = repo.create_hook('web', config)
        
        flash('Hook successfully added to Repository. Now Push a commit and see the magic!')
    except Exception as e:
        flash(str(e))

    return redirect(url_for('home'))

@app.route('/details/<repo_name>', methods=['GET'])
@login_required
def details(repo_name):
    logged_in = ('username' in session)
    repolink = UserRepo.query.filter_by(repo_name=repo_name).first_or_404()
    try:
        return render_template('repo.html')
    except Exception as e:
        flash(str(e))
    return redirect(url_for('home'))

@app.route('/answer/<token>', methods=['POST'])
def answer(token):
    plivo_client = plivo.RestAPI(plivo_settings['auth_id'], plivo_settings['auth_token'])
    req = json.loads(request.data)
    logging.debug(req)

    name = req['pusher']['name']
    repo = req['repository']['name']
    commit_msg = req['head_commit']['message']
    try:
        userrepo = UserRepo.query.filter_by(token = token).first()
        logging.debug(userrepo)
        if userrepo is None:
            logging.debug('Invalid token')
            return 'Invalid token: %s' % token

        if userrepo.repo_name != repo:
            logging.debug('Invalid hook')
            return 'Invalid hook: %r' % req

        app.message= '%s pushed a commit to %s, %s' % (name, repo, commit_msg)

        params = {
            'to': str(userrepo.user.mobile),
            'from': str(userrepo.user.mobile),
            'answer_url': 'http://%s/answer/plivo/' % request.headers['HOST'],
        }
        (status_code, response) = plivo_client.make_call(params)
        logging.debug(response)
    except Exception as e:
        logging.debug(str(e))
    return str('this should not be reachable')

@app.route('/answer/plivo/', methods=['POST'])
def answer_plivo():
    resp = plivo.Response()
    if request.form['Event'] == 'StartApp':
        resp.addSpeak('Hi, This is a Git hub notification.', voice = 'MAN')
        resp.addWait(length=1)
        resp.addSpeak(app.message)

        app.message = ''
    return resp.to_xml()

@app.route('/logout/', methods=['GET'])
def logout():
    session.pop('user', None)
    session.pop('logged_in', None)
    session.pop('gituser', None)
    session.pop('github', None)
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

        session['github'] = Github(access_token)
        session['gituser'] = session['github'].get_user()

        session['user'] = user
        session['logged_in'] = True
    except Exception as e:
        logging.debug('Login callback exc: %r' % e)
        flash(str(e))

    logging.debug(session)
    return redirect(url_for('home'))

if __name__ == '__main__':
    # Bind to PORT if defined, otherwise default to 5000.
    port = int(os.environ.get('PORT', 5000))
    ENV = os.environ.get('ENV', 'prod')
    debug = (ENV == 'dev')
    app.run(host='0.0.0.0', port=port, debug = debug)