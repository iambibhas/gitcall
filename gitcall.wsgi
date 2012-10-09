import sys
import os.path
activate = 'home/ubuntu/sites/gitcall/venv/bin/activate'
execfile(activate, dict(__file__ = activate))
sys.path.insert(0, os.path.dirname(__file__))
from app import app as application