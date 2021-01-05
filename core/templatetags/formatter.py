# -*- coding: utf-8 -*-
from django import template

from core.utils import locked

register = template.Library()


@register.filter
def no_underscore(value):
    return value.replace("_", " ")


def to_bool(val):
    if val in ["true", True, 1, "yes"]:
        return True
    return False


@register.simple_tag(takes_context=True)
def edit_locked(context, attendee=None, for_input=False, radio=False, ignore_user=False):
    for_input = to_bool(for_input)
    radio = to_bool(radio)
    user = context.request.user if not ignore_user else None
    yes = True
    if for_input:
        yes = "readonly"
    elif radio:
        yes = "disabled"
    no = "" if for_input else False
    if locked(user=user):
        return yes
    if attendee and attendee.get('attends_as').lower() == "couple":
        return yes
    return no
