# -*- coding: utf-8 -*-
"""Extensions module. Each extension is initialized in the app factory located in app.py."""
from celery import Celery
from flask_bcrypt import Bcrypt
from flask_bootstrap import Bootstrap4
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

bcrypt = Bcrypt()
bootstrap = Bootstrap4()
csrf_protect = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "user.login"
login_manager.login_message_category = "info"
db = SQLAlchemy()
migrate = Migrate()


class CeleryExtension(Celery):
    def __init__(self):
        pass

    def init_app(self, app):
        super().__init__(
            app.import_name,
            broker=app.config["CELERY_BROKER_URL"],
            include=[
                "medb.shiso.tasks",
                "medb.speedtest.tasks",
            ],
        )
        self.conf.update(app.config)

        class ContextTask(self.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        self.Task = ContextTask


celery = CeleryExtension()
