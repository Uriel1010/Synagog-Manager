import os
from dotenv import load_dotenv

load_dotenv() # Load variables from .env file

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess-this-super-secret-key' # CHANGE THIS!
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'synagogue_app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Add other configurations if needed (e.g., mail server for password resets)