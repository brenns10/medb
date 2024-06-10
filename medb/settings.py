# -*- coding: utf-8 -*-
"""Application configuration.
Most configuration is set via environment variables.
For local development, use a .env file to set
environment variables.
"""
from environs import Env

env = Env()
env.read_env()
env.read_env(".env.secret", override=True)

ENV = env.str("FLASK_ENV", default="production")
DEBUG = ENV == "development"
SERVER_NAME = env.str("SERVER_NAME")
PREFERRED_URL_SCHEME = env.str("PREFERRED_URL_SCHEME")
SQLALCHEMY_DATABASE_URI = env.str("DATABASE_URL")
CELERY_BROKER_URL = env.str("CELERY_BROKER_URL")
SECRET_KEY = env.str("SECRET_KEY")
BCRYPT_LOG_ROUNDS = env.int("BCRYPT_LOG_ROUNDS", default=13)
DEBUG_TB_ENABLED = DEBUG
DEBUG_TB_INTERCEPT_REDIRECTS = False
SQLALCHEMY_TRACK_MODIFICATIONS = False

PLAID_CLIENT_ID = env.str("PLAID_CLIENT_ID")
PLAID_SECRET = env.str("PLAID_SECRET")
PLAID_ENV = env.str("PLAID_ENV")

SMTP_PASS = env.str("SMTP_PASS")
SMTP_PORT = env.str("SMTP_PORT")
SMTP_SENDER = env.str("SMTP_SENDER")
SMTP_SERVER = env.str("SMTP_SERVER")

DEPLOY = env.str("MEDB_DEPLOY", default="(development, no deploy info)")
