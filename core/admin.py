# -*- coding: utf-8 -*-
from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

app = apps.get_app_config('core')
User = get_user_model()
user_fields = (
    'first_name',
    'last_name',
    'username',
    'email',
    'id_number',
    'phone_number',
    'residence',
    "is_active",
    'is_superuser',
    'is_staff',
)
UserAdmin.fieldsets = ((None, {'classes': ('wide',), 'fields': user_fields}),)
UserAdmin.add_fieldsets = ((None, {'classes': ('wide',), 'fields': user_fields}),)


for model_name, model in app.models.items():
    model_admin = type(model_name + "Admin", (admin.ModelAdmin,), {})
    if model == User:
        model_admin = UserAdmin
    model_admin.list_display = (
        model.admin_list_display
        if hasattr(model, 'admin_list_display')
        else tuple([field.name for field in model._meta.fields if field.name != 'password'])
    )
    model_admin.list_display_links = (
        model.admin_list_display_links if hasattr(model, 'admin_list_display_links') else ()
    )

    model_admin.list_editable = (
        model.admin_list_editable if hasattr(model, 'admin_list_editable') else ()
    )
    model_admin.search_fields = (
        model.admin_search_fields if hasattr(model, 'admin_search_fields') else ()
    )

    admin.site.register(model, model_admin)
