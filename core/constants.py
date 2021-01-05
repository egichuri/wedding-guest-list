# -*- coding: utf-8 -*-
import environ
from django.db import models

env = environ.Env()
PER_TABLE_COUNT = env("PER_TABLE_COUNT", default=7)
TABLE_COUNT = env("TABLE_COUNT", default=30)

SERVICE = "wedding_ceremony"
RECEPTION = "reception"
AFTER_PARTY = "evening_party"

ATTENDANCE_MAP = {
    "1": "Couple",
    "2": "Planner",
    "3": "Bridal Team",
    "4": "Family",
    "5": "Guest",
    "6": "Service Provider",
    "7": "Group",
    "8": "Kids",
}


class AttendsAs(models.IntegerChoices):
    COUPLE = 1
    PLANNER = 2
    BRIDAL_TEAM = 3
    FAMILY = 4
    GUEST = 5
    SERVICE_PROVIDER = 6
    GROUP = 7
    KIDS = 8
