from fabric.api import *
from fabric.contrib import files

# the user to use for the remote commands
env.user = 'ubuntu'
# the servers where the commands are executed
env.hosts = ['23.21.195.1']
env.project = 'gitcall'
env.hostname = '%s.bibhas.in' % env.project
env.key_filename = ["/home/bibhas/.ssh/ec2bi.pem"]
env.project_path = '/home/ubuntu/sites/gitcall'

def test():
    run('whoami')

def pack():
    local('git archive HEAD | gzip > dist/%s.tar.gz' % env.project)

def upload_tarball():
    with cd(env.project_path):
        # saving last deployment tarball for backup
        # run('mv dist/%s.tar dist/last_deploy.tar' % env.project)
        put('dist/%s.tar.gz' % env.project, 'dist/')

def reload_apache():
    sudo('/etc/init.d/apache2 reload')

def setup_vhost():
    with cd(env.project_path):
        sudo('cp gitcall.vhost /etc/apache2/sites-available/%s' % env.hostname)
        sudo('a2dissite %s' % env.hostname)
        reload_apache()
        sudo('a2ensite %s' % env.hostname)
        reload_apache()

def setup_venv():
    with cd(env.project_path):
        run('rm -rf venv')
        run('virtualenv -p /usr/bin/python2.7 venv')
        with prefix('source venv/bin/activate'):
            run('pip install -r requirements.txt')
        put('venv/lib/python2.7/site-packages/oauth2/__init__.py', 'venv/lib/python2.7/site-packages/oauth2/')

def setup_db():
    with cd(env.project_path):
        with prefix('source venv/bin/activate'):
            run('python initdb.py')

def deploy():
    pack()
    upload_tarball()
    # Extract files
    with cd(env.project_path):
        run('tar -zxvf dist/%s.tar.gz' % env.project)
    if not files.exists('%s/venv/' % env.project_path):
        setup_venv()
    # create virtualhost
    setup_vhost()

def tail_apache():
    run('tail -f /var/log/apache2/error.log')