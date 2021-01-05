# -*- coding: utf-8 -*-
import time
import uuid

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django_cryptography.fields import encrypt

from core.constants import AFTER_PARTY, AttendsAs, PER_TABLE_COUNT, RECEPTION, SERVICE, TABLE_COUNT
from core.managers import CustomUserManager
from core.utils import format_phone_number


def default_attendance(service=False, reception=False, after_party=False):
    return {SERVICE: service, RECEPTION: reception, AFTER_PARTY: after_party}


def default_ordinal():
    return int(time.time() * 100)


class BaseModel(models.Model):
    class Meta:
        abstract = True

    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def prep_delete(self, **kwargs):
        pass

    def soft_delete(self, **kwargs):
        if self.is_active or not self.deleted_at:
            self.prep_delete(**kwargs)
            self.deleted_at = timezone.now()
            self.is_active = False
            self.save()

    def undelete(self):
        if self.deleted_at or not self.is_active:
            self.deleted_at = None
            self.is_active = True
            self.save()


class User(AbstractUser, BaseModel):
    phone_number = models.CharField(max_length=30, blank=True, null=True)
    residence = models.CharField(max_length=64, blank=True, null=True)
    id_number = encrypt(
        models.DecimalField(null=True, blank=True, decimal_places=0, max_digits=10)
    )

    objects = CustomUserManager()

    class Meta:
        ordering = ['username']

    def __str__(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username or self.uid

    def clean(self):
        if self.phone_number and self._state.adding:
            exists = User.objects.filter(phone_number=self.phone_number).exists()
            if exists:
                raise ValidationError("User with this phone number already exists")

    def save(self, *args, **kwargs):
        if not self.password:
            self.set_unusable_password()
        if self.email:
            self.email = self.email.lower()
        self.phone_number = format_phone_number(self.phone_number)
        if self.username:
            self.username = self.username.lower()
        else:
            self.username = default_ordinal()
        self.full_clean()
        super().save(*args, **kwargs)


class Invite(BaseModel):
    YES = 'yes'
    NO = 'no'

    RSVP_CHOICES = [(YES, 'yes'), (NO, 'no')]
    user = models.OneToOneField('User', on_delete=models.PROTECT, related_name='invites')
    rsvp = models.CharField(choices=RSVP_CHOICES, blank=True, null=True, max_length=3)
    received = models.BooleanField(default=False)
    parties = models.PositiveIntegerField(default=1)
    added_for = models.IntegerField(choices=AttendsAs.choices, default=AttendsAs.GUEST)
    kids_allowed = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        ordering = ['user__first_name', 'user__last_name']

    def __str__(self):
        return f'{self.user.first_name} {self.user.last_name}'

    def clean(self):
        if (
            self.added_for == AttendsAs.KIDS
            and self._state.adding
            and (self.parties != 1 or self.kids_allowed)
        ):
            raise ValidationError("Cannot add invites for kids directly")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        if self.kids_allowed:
            kids_user, _ = User.objects.get_or_create(first_name="kids", last_name="")
            invite, created = Invite.objects.get_or_create(
                user=kids_user, added_for=AttendsAs.KIDS
            )
            total_kids = Invite.objects.filter(kids_allowed__gt=0).values_list(
                "kids_allowed", flat=True
            )
            invite.parties = sum(total_kids)
            invite.save()


class Attendee(BaseModel):
    user = models.OneToOneField('User', on_delete=models.PROTECT, related_name='invitation')
    invite = models.ForeignKey('Invite', on_delete=models.PROTECT, related_name='attendees')
    attendance = models.JSONField(default=default_attendance)
    ordinal = models.PositiveBigIntegerField(default=default_ordinal)
    table = models.PositiveIntegerField(blank=True, null=True)
    attends_as = models.IntegerField(choices=AttendsAs.choices, default=AttendsAs.GUEST)

    class Meta:
        ordering = ['ordinal']

    def __str__(self):
        return str(self.ordinal)

    def prep_delete(self, **kwargs):
        self.table = None

    def clean(self):
        if self.attends_as in [AttendsAs.COUPLE, AttendsAs.BRIDAL_TEAM]:
            self.table = 0
        elif self.table == 0:
            raise ValidationError("Table number 0 is reserved for the bridal party.")
        elif not self.is_active:
            self.table = None
        elif self.table:
            count = Attendee.objects.filter(table=self.table).count()
            if self._state.adding:
                if not count < PER_TABLE_COUNT:
                    raise ValidationError(f"Only {PER_TABLE_COUNT} people allowed per table.")
            elif not count <= PER_TABLE_COUNT:
                raise ValidationError(f"Only {PER_TABLE_COUNT} people allowed per table.")
            if self.table > TABLE_COUNT:
                raise ValidationError(
                    f"Table number should be less than {TABLE_COUNT}. ({self.table} provided)"
                )
        if self.attendance:
            defaults = default_attendance()
            if self.attendance.keys() != defaults.keys():
                raise ValidationError("Invalid value for attendance")

    def save(self, *args, **kwargs):
        if self.attends_as == AttendsAs.COUPLE:
            self.attendance = default_attendance(service=True, reception=True, after_party=True)
            if (
                self._state.adding
                and self._meta.model.objects.filter(attends_as=AttendsAs.COUPLE).count() > 1
            ):
                raise ValidationError("Only 2 attendees can be the couple")

        self.full_clean()
        super().save(*args, **kwargs)


class Settings(BaseModel):
    data = models.JSONField(default=dict, blank=True, null=True)
    user = models.OneToOneField(
        'User', on_delete=models.PROTECT, related_name='settings', blank=True, null=True
    )
    sitewide = models.BooleanField(default=False)

    def clean(self):
        if sum(map(bool, [self.sitewide, self.user])) != 1:
            raise ValidationError("Sitewide settings should not be tied to a user")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
