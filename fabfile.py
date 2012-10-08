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

def deploy():
    pack()
    upload_tarball()
    with cd('/home/ubuntu/sites/gitcall/'):
        run('tar -xvf dist/gitcall.tar')