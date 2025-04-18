# File: config.py
import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'synagogue_app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Load the API Key ---
    ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY')