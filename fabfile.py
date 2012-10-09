from fabric.api import *

# the user to use for the remote commands
env.user = 'ubuntu'
# the servers where the commands are executed
env.hosts = ['23.21.195.1']
env.key_filename = ["/home/bibhas/.ssh/ec2bi.pem"]

def test():
    run('whoami')

def pack():
    local('git archive HEAD > dist/gitcall.tar')

def upload_tarball():
    # /home/ubuntu/sites/gitcall/
    put('dist/gitcall.tar', '/home/ubuntu/sites/gitcall/dist/')

def restart_apache():
    sudo('/etc/init.d/apache2 restart')

def setup_vhost():
    with cd('/home/ubuntu/sites/gitcall/'):
        sudo('cp gitcall.vhost /etc/apache2/sites-available/gitcall.bibhas.in')
        sudo('a2dissite gitcall.bibhas.in')
        restart_apache()
        sudo('a2ensite gitcall.bibhas.in')
        restart_apache()

def setup_venv():
    with cd('/home/ubuntu/sites/gitcall/'):
        run('virtualenv venv')
        with prefix('source venv/bin/activate'):
            run('pip install -r requirements.txt')

def deploy():
    pack()
    upload_tarball()
    # Extract files
    with cd('/home/ubuntu/sites/gitcall/'):
        run('tar -xvf dist/gitcall.tar')
    setup_venv()
    # create virtualhost
    setup_vhost()