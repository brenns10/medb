# -*- coding: utf-8 -*-
"""Application configuration.
Most configuration is set via environment variables.
For local development, use a .env file to set
environment variables.
"""
from environs import Env

env = Env()
env.read_env()
env.read_env('.env.secret')

ENV = env.str("FLASK_ENV", default="production")
DEBUG = ENV == "development"
SQLALCHEMY_DATABASE_URI = env.str("DATABASE_URL")
SECRET_KEY = env.str("SECRET_KEY")
BCRYPT_LOG_ROUNDS = env.int("BCRYPT_LOG_ROUNDS", default=13)
DEBUG_TB_ENABLED = DEBUG
DEBUG_TB_INTERCEPT_REDIRECTS = False
SQLALCHEMY_TRACK_MODIFICATIONS = False

PLAID_CLIENT_ID = env.str('PLAID_CLIENT_ID')
PLAID_SECRET = env.str('PLAID_SECRET')
PLAID_PUBLIC_KEY = env.str('PLAID_PUBLIC_KEY')
PLAID_PRODUCTS = env.str('PLAID_PRODUCTS')
PLAID_COUNTRY_CODES = env.str('PLAID_COUNTRY_CODES')
PLAID_ENV = env.str('PLAID_ENV')
