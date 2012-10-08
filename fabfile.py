from fabric.api import *

# the user to use for the remote commands
env.user = 'ubuntu'
# the servers where the commands are executed
env.hosts = ['23.21.195.1']
env.key_filename = ["/home/bibhas/.ssh/ec2bi.pem"]

def test():
    run('whoami')