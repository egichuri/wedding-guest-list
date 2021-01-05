# -*- coding: utf-8 -*-
from django.contrib.auth.models import UserManager
from django.db.models import Manager
from django.db.models.query import QuerySet


class CaseInsensitiveQuerySet(QuerySet):
    def _filter_or_exclude(self, mapper, *args, **kwargs):
        fields = {'name', 'username', 'email', 'short_name', 'first_name', 'last_name'}
        for field in fields:
            if field in kwargs and type(kwargs.get(field)) == str:
                kwargs['{}__iexact'.format(field)] = kwargs[field]
                del kwargs[field]
        return super(CaseInsensitiveQuerySet, self)._filter_or_exclude(mapper, *args, **kwargs)


class CaseInsensitiveManager(Manager):
    def get_queryset(self):
        return CaseInsensitiveQuerySet(self.model)


class CustomUserManager(UserManager):
    def get_queryset(self):
        return CaseInsensitiveQuerySet(self.model)
