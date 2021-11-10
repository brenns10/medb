# -*- coding: utf-8 -*-
"""The app module, containing the app factory function."""
import logging
import sys

from celery.schedules import crontab
from flask import Flask
from flask import render_template

import medb.shiso.models  # noqa
import medb.shiso.views
import medb.speedtest.models  # noqa
import medb.speedtest.views
import medb.user.models  # noqa
import medb.user.views
from medb import public
from medb.extensions import bcrypt
from medb.extensions import celery
from medb.extensions import csrf_protect
from medb.extensions import db
from medb.extensions import debug_toolbar
from medb.extensions import login_manager
from medb.extensions import migrate


def create_app(config_object="medb.settings"):
    """
    Create application factory, as explained here:
    http://flask.pocoo.org/docs/patterns/appfactories/.
    :param config_object: The configuration object to use.
    """
    app = Flask(__name__.split(".")[0])
    app.config.from_object(config_object)
    register_extensions(app)
    register_blueprints(app)
    register_errorhandlers(app)
    register_shellcontext(app)
    register_commands(app)
    configure_logger(app)
    return app


def register_extensions(app):
    """Register Flask extensions."""
    bcrypt.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    csrf_protect.init_app(app)
    login_manager.init_app(app)
    debug_toolbar.init_app(app)
    celery.init_app(app)
    register_periodic_tasks()
    return None


def register_blueprints(app):
    """Register Flask blueprints."""
    app.register_blueprint(public.blueprint)
    app.register_blueprint(medb.user.views.blueprint)
    app.register_blueprint(medb.shiso.views.blueprint)
    app.register_blueprint(medb.speedtest.views.blueprint)
    return None


def register_errorhandlers(app):
    """Register error handlers."""

    def render_error(error):
        """Render error template."""
        # If a HTTPException, pull the `code` attribute; default to 500
        error_code = getattr(error, "code", 500)
        return render_template(f"{error_code}.html"), error_code

    for errcode in [401, 404, 500]:
        app.errorhandler(errcode)(render_error)
    return None


def register_shellcontext(app):
    """Register shell context objects."""

    def shell_context():
        """Shell context objects."""
        return {"db": db}

    app.shell_context_processor(shell_context)


def register_commands(app):
    """Register Click commands."""
    pass


def configure_logger(app):
    """Configure loggers."""
    handler = logging.StreamHandler(sys.stdout)
    if not app.logger.handlers:
        app.logger.addHandler(handler)


def register_periodic_tasks():
    celery.conf.beat_schedule = {
        "regular_speedtest": {
            "task": "medb.speedtest.tasks.perform_speedtest",
            "schedule": crontab(minute=3),
            "args": (),
        },
        "regular_iptest": {
            "task": "medb.speedtest.tasks.perform_ipcheck",
            "schedule": crontab(minute=7),
            "args": (),
        },
    }
