# -*- coding: utf-8 -*-
"""Helper utilities and decorators."""
import typing as t
from email.message import EmailMessage
from smtplib import SMTP_SSL

from flask import flash
from flask import render_template

from medb.settings import SMTP_PASS
from medb.settings import SMTP_PORT
from medb.settings import SMTP_SENDER
from medb.settings import SMTP_SERVER


def send_email(subject: str, to: str, tmpl: str, **data: t.Any) -> None:
    """
    Send an email using the configured SMTP server

    Be a good email sender and send a MIME multipart/alternative message with
    both text and HTML. The body of the message is provided by templates, one
    for text and one for HTML.

    :param subject: subject line of message
    :param to: recipient of message
    :param tmpl: base name of template. Suffixes ".html" and ".txt" will be
      appended to get the final template names used.
    :param data: data passed to templates
    """
    html = render_template(f"{tmpl}.html", **data)
    text = render_template(f"{tmpl}.txt", **data)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_SENDER
    msg["To"] = to
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    with SMTP_SSL(host=SMTP_SERVER, port=SMTP_PORT) as smtp:
        smtp.login(SMTP_SENDER, SMTP_PASS)
        smtp.send_message(msg)


def flash_errors(form, category="warning"):
    """Flash all errors for a form."""
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"{getattr(form, field).label.text} - {error}", category)
