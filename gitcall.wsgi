import sys
import os
import logging

activate_this = '/home/ubuntu/sites/gitcall/venv/bin/activate_this.py'
execfile(activate_this, dict(__file__ = activate_this))

sys.path.insert(0, '/home/ubuntu/sites/gitcall')
sys.path.insert(0, '/home/ubuntu/sites/gitcall/venv/lib/python2.7/site-packages')

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

from app import app as application
application.secret_key = os.urandom(24)