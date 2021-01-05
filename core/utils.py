# -*- coding: utf-8 -*-
import datetime
import logging
import re

import environ
import requests
from django.core.exceptions import ValidationError
from django.core.mail import send_mail

from core.constants import AttendsAs

env = environ.Env()

KENYA_PHONE_REGEX = r'^\+?(254)?0?([7|1])(\d{8})$'


log = logging.getLogger(__name__)


class PhoneValidationError(ValidationError):
    pass


def format_phone_number(phone):
    if not phone:
        return
    try:
        int(phone)
    except ValueError:
        raise PhoneValidationError("Value must be a number")
    phone = re.sub('[^0-9]', '', phone)

    match = re.match(KENYA_PHONE_REGEX, phone)
    if match and len(match.groups()) > 2:
        one = match.groups()[-2]
        two = match.groups()[-1]
        phone = f'254{one}{two}'
        return phone
    raise PhoneValidationError('Invalid phone number provided')


def send_email(emails, subject, text, sender, html=None):
    domain = env("MAILGUN_DOMAIN", default=None)
    api_key = env("MAILGUN_API_KEY", default=None)
    data = {"from": sender, "to": emails, "subject": subject, "text": text}
    if html:
        data["html"] = html
    if all([domain, api_key]):
        resp = requests.post(
            f"https://api.mailgun.net/v3/{domain}/messages", auth=("api", api_key), data=data
        )
    else:
        resp = send_mail(subject, text, sender, emails, html_message=html)
    return resp


def masked(string, first=None, last=None):
    if not string:
        return string
    first = first or 1
    last = last or 2
    return f"{string[:first]}******{string[-last::]}"


def user_is_couple(user):
    try:
        invitation = user.invitation
    except Exception:
        return False
    return invitation.attends_as == AttendsAs.COUPLE


def locked(user=None):
    if user_is_couple(user):
        return False

    from core.models import Settings

    settings = Settings.objects.get(sitewide=True)
    wedding_date = settings.data.get('date')
    as_date = datetime.datetime.strptime(wedding_date, '%Y-%m-%d')
    diff = as_date.date() - datetime.date.today()
    if diff.days < env("CUTOFF", default=2):
        return True
    return False


def is_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        invitation = user.invitation
    except Exception:
        return False
    return invitation.attends_as <= 2
