import sys
import os.path
import logging
activate_this = '/home/ubuntu/sites/gitcall/venv/bin/activate_this.py'
execfile(activate_this, dict(__file__ = activate_this))
sys.path.insert(0, '/home/ubuntu/sites/gitcall')
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
from app import app as application