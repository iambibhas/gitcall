import sys
import os.path
activate_this = os.path.dirname(__file__) + '/venv/bin/activate_this.py'
execfile(activate_this, dict(__file__ = activate_this))
sys.path.insert(0, os.path.dirname(__file__))
from app import app as application