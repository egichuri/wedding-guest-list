# -*- coding: utf-8 -*-
import logging
import string
from collections import defaultdict

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.functions import Lower
from django.shortcuts import redirect, render
from django.template.exceptions import TemplateDoesNotExist
from django.template.loader import get_template
from django.views import View
from sesame.utils import get_query_string

from core.constants import ATTENDANCE_MAP, PER_TABLE_COUNT, TABLE_COUNT
from core.models import Attendee, AttendsAs, Invite, Settings, User
from core.utils import (
    format_phone_number,
    is_admin,
    locked,
    masked,
    PhoneValidationError,
    send_email,
    user_is_couple,
)

logger = logging.getLogger(__name__)


def _get_ord(val):
    if val[0].lower() == "bridal party":
        return 0
    try:
        return int(val[0])
    except ValueError:
        return -1


def setup_complete():
    required_fields = [
        'b_first_name',
        'b_last_name',
        'b_email',
        'a_first_name',
        'a_last_name',
        'a_email',
        'date',
    ]
    settings, _ = Settings.objects.get_or_create(sitewide=True)
    data = settings.data or {}
    return all([data.get(each) for each in required_fields])


def formatted(word, default=None, mask=False, country_code=True, first=None):
    if not word:
        return default or ""
    word = str(word)
    if not country_code:
        word = word.replace("254", "0", 1)
    if mask:
        return masked(string.capwords(word), first=first)
    return string.capwords(word)


def serialize_invite(invite, host, default=None, mask=False, country_code=True):
    if not host.endswith('/'):
        host = f"{host}/"
    default = default or ""
    id_number = ""
    if invite.user.id_number:
        id_number = str(invite.user.id_number)
    parties = invite.parties
    link = None
    plus = 0

    if parties > 0:
        plus = parties - 1
        link = f"{host}?invite={invite.uid.hex}"
    return {
        "uid": invite.uid,
        "first_name": formatted(invite.user.first_name, default=default),
        "last_name": formatted(invite.user.last_name, default=default),
        "phone_number": formatted(
            invite.user.phone_number,
            default=default,
            mask=mask,
            country_code=country_code,
            first=3,
        ),
        "id_number_disp": formatted(id_number, default=default, mask=True),
        "received": invite.received,
        "rsvp": formatted(invite.rsvp, default=default),
        "rsvp_count": invite.attendees.filter(is_active=True).count(),
        "is_active": invite.is_active,
        "parties": parties,
        "plus": plus,
        "link": link,
        "kids_allowed": invite.kids_allowed,
        "added_for": ATTENDANCE_MAP[str(invite.added_for)],
    }


def get_and_serialize_attendees(
    invite_code=None,
    order_by=None,
    active_only=False,
    confirmed=False,
    default_value=None,
    mask=False,
    country_code=True,
):
    filters = {}
    if invite_code:
        filters['invite__uid'] = invite_code
    if active_only:
        filters['is_active'] = True
    if confirmed:
        filters['invite__rsvp'] = "yes"
    attendees = Attendee.objects.select_related().filter(**filters)
    if order_by == "name":
        attendees = attendees.order_by(Lower("user__first_name"), Lower("user__last_name"))
    elif order_by == "invite_name":
        attendees = attendees.order_by(
            Lower("invite__user__first_name"), Lower("invite__user__last_name")
        )
    data = []
    couple = []
    allocated = 0
    for attendee in attendees:
        id_number = ""
        if attendee.user.id_number:
            id_number = str(attendee.user.id_number)
        table = attendee.table
        if table is not None:
            allocated += 1
        if table == 0:
            table = "Bridal Party"
        serialized = {
            "uid": attendee.uid,
            "first_name": formatted(attendee.user.first_name, default=default_value),
            "last_name": formatted(attendee.user.last_name, default=default_value),
            "residence": formatted(attendee.user.residence, default=default_value),
            "invite": f"{formatted(attendee.invite.user.first_name, default=default_value)} {formatted(attendee.invite.user.last_name, default=default_value)}",
            "phone_number": formatted(
                attendee.user.phone_number,
                default=default_value,
                mask=mask,
                country_code=country_code,
                first=3,
            ),
            "id_number": formatted(id_number, mask=mask),
            "id_number_disp": formatted(id_number, default=default_value, mask=True),
            "attendance": attendee.attendance,
            "table": formatted(table, default=default_value),
            "is_active": attendee.is_active,
            "ordinal": attendee.ordinal,
            "attends_as": ATTENDANCE_MAP[str(attendee.attends_as)],
        }
        if attendee.attends_as == AttendsAs.COUPLE:
            couple.append(serialized)
            continue
        data.append(serialized)
    return data, couple, allocated


def get_and_serialize_guests(
    host, default_value=None, order_by=None, mask=False, country_code=True
):
    invites = Invite.objects.select_related()
    if order_by == "name":
        invites = invites.order_by(Lower("user__first_name"), Lower("user__last_name"))
    data = []
    count = {"kids": 0, "guests": 0}
    for invite in invites:
        serialized = serialize_invite(
            invite, host, default=default_value, mask=mask, country_code=country_code
        )
        if invite.added_for == AttendsAs.KIDS:
            count["kids"] += invite.parties
        else:
            count["guests"] += serialized["parties"]
        data.append(serialized)
    return data, count


def get_invitation_data(code, host):
    if not code:
        return None
    try:
        invite = Invite.objects.select_related().get(uid=code)
    except Exception as e:
        logger.warning('%s: %s', e, code)
        return None
    return serialize_invite(invite, host)


def get_template_to_render(template, default=None):
    try:
        template_to_render = template
        get_template(template)
    except TemplateDoesNotExist:
        if default:
            return get_template_to_render(default)
        template_to_render = 'maintenance.html'
        logger.info("Template: {} not found".format(template))
    return template_to_render


def handler403(request, exception):
    return render(request, '403.html', status=403)


def handler404(request, exception):
    return render(request, '404.html', status=404)


def handler500(request):
    return render(request, '500.html', status=500)


def handler503(request, exception):
    return render(request, '503.html', status=503)


def get_user_by_phone_number_or_uid(
    phone_number, first_name, last_name, residence=None, id_number=None, uid=None
):
    try:
        phone_number = format_phone_number(phone_number)
    except PhoneValidationError:
        raise
    user = None
    if uid:
        try:
            attendee = Attendee.objects.get(uid=uid)
        except Exception as ex:
            logger.warning(ex)
        else:
            user = attendee.user
    if not user:
        filters = {}
        if phone_number:
            filters["phone_number"] = phone_number
        else:
            filters["first_name"] = first_name
            filters["last_name"] = last_name
        user, _ = User.objects.get_or_create(**filters)
    if not user.id_number:
        user.id_number = int(id_number) if id_number else None
    if phone_number and user.phone_number != phone_number:
        user.phone_number = phone_number
    if first_name and user.first_name != first_name:
        user.first_name = first_name
    if last_name and user.last_name != last_name:
        user.last_name = last_name
    if residence and not user.residence:
        user.residence = residence
    user.save()
    return user


@transaction.atomic
def handle_data_save(data):
    first_name = data.get("first_name").strip()
    last_name = data.get("last_name").strip()
    phone_number = data.get("phone_number").replace(" ", "")
    slots = data.get("slots")
    kids = data.get("kids") or 0
    category = data.get("category") or str(AttendsAs.GUEST)

    try:
        user = get_user_by_phone_number_or_uid(phone_number, first_name, last_name)
    except PhoneValidationError:
        return {"invite_created": False, "phone_number": "Invalid phone number"}

    try:
        invite = Invite.objects.create(
            user=user, parties=slots, kids_allowed=kids, added_for=category
        )
        if category != str(AttendsAs.GROUP):
            Attendee.objects.create(user=user, invite=invite, attends_as=category)
    except IntegrityError:
        errors = {"invite": "Invite for this user/group already exists", "invite_created": False}
        return errors
    except Exception as ex:
        logger.exception(ex)
        ex_errors = ex.error_dict
        errors = {"invite_created": False}
        for key, val in ex_errors.items():
            errors[key] = val[0].messages[0]
        return errors
    return {"invite_created": True}


class DashBoard(UserPassesTestMixin, View):
    template_name = get_template_to_render('dashboard.html')
    blank_template = get_template_to_render('blank.html')

    def _get_context_data(self):
        host = self.request.get_host()
        user = self.request.user
        tables = defaultdict(int)
        [tables.update({str(key + 1): 0}) for key in range(TABLE_COUNT)]
        guests, count = get_and_serialize_guests(host, default_value="-")
        attendees, couple, allocated = get_and_serialize_attendees(
            order_by="name", active_only=True, confirmed=True, default_value="-"
        )
        for attendee in attendees:
            tables[attendee["table"]] += 1

        is_couple = user_is_couple(user)

        context = {
            'blank_template': self.blank_template,
            "guests": guests,
            "attendees": attendees,
            "all_attendees": couple + attendees,
            "couple": couple,
            "count": count,
            "table_count": PER_TABLE_COUNT,
            "tables": dict(sorted(tables.items(), key=lambda item: _get_ord(item))),
            "allocated": allocated,
            "is_couple": is_couple,
            "confirmed": len(attendees) + len(couple),
        }
        settings = Settings.objects.get(sitewide=True)
        context.update(settings.data)
        return context

    def test_func(self):
        return is_admin(self.request.user)

    def handle_no_permission(self):
        return redirect('/login')

    def get(self, request, *args, **kwargs):
        context = self._get_context_data()
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        content = {}
        data = request.POST
        if data:
            src = data.get('src')
            if src == "table-edit":
                table_number = data.get("table_after")
                attendee_uid = data.get("uid")
                try:
                    attendee = Attendee.objects.get(uid=attendee_uid)
                    attendee.table = int(table_number) if table_number else None
                    attendee.save()
                except ValidationError as ex:
                    content['result'] = {"table_errors": ex.messages}
                except ValueError:
                    content['result'] = {"table_errors": ["Table number must be a number"]}
                except Exception as ex:
                    logger.warning(ex.error_dict)
                else:
                    return redirect('dashboard')
            else:
                result = handle_data_save(data)
                content['result'] = result
        context = self._get_context_data()
        context["content"] = content
        return render(request, self.template_name, context)


class Home(View):
    template_name = get_template_to_render('index.html')
    base_template = get_template_to_render('base.html')

    def _get_context_data(self):
        data = {}
        session_code = self.request.session.get('code')
        code = self.request.GET.get('invite') or session_code
        host = self.request.get_host()
        invitation = get_invitation_data(code, host)
        if invitation:
            attendees, couple, _ = get_and_serialize_attendees(invite_code=code, active_only=True)
            attendees += couple
            attendees = sorted(attendees, key=lambda x: x.get("ordinal"))
            invite_count = invitation.get("parties")
            diff = invite_count - len(attendees)
            user = self.request.user
            if diff > 0 and not locked(user=user):
                for _ in range(diff):
                    attendees.append({})
            self.request.session['code'] = code
            data["admits"] = len(attendees)
            data["invitation"] = invitation
            data["attendees"] = attendees
        elif session_code:
            del self.request.session['code']
        settings = Settings.objects.get(sitewide=True)
        data.update(settings.data)
        return data

    def get(self, request, *args, **kwargs):
        complete = setup_complete()
        if not complete:
            return redirect('setup')
        data = self._get_context_data()

        content = {'base_template': self.base_template, 'data': data}
        return render(request, self.template_name, content)

    def post(self, request, *args, **kwargs):
        data = request.POST
        count = data.get('count')
        src = data.get('src')
        errors = 0
        saved = 0
        invite_uid = data.get("invite_uid")
        invite = Invite.objects.select_related().get(uid=invite_uid)
        rsvp = data.get("rsvp")
        if src == "rsvp" and rsvp:
            invite.rsvp = rsvp
            invite.save()
            attendees = invite.attendees.all()
            if rsvp == "no":
                for each in attendees:
                    each.soft_delete()
            else:
                for each in attendees:
                    each.undelete()

            try:
                name = f"{invite.user.first_name} {invite.user.last_name}"
                text = f"{name} - {rsvp}"
                recipients = Attendee.objects.filter(attends_as=AttendsAs.COUPLE)
                if recipients:
                    emails = [each.user.email for each in recipients]
                    send_email(emails, "Invite edited", text)
            except Exception:
                pass
        elif src == "details":
            if count:
                count = int(count)
            else:
                count = 0
            for item in range(count):
                attendee_data = {}
                delete = data.get(f"delete{item + 1}")
                if delete:
                    _, uid = delete.split(",")
                    if uid:
                        attendee = Attendee.objects.get(uid=uid)
                        attendee.soft_delete()
                    if invite.parties > 1:
                        invite.parties -= 1
                        invite.save()
                    continue
                attendee_data["invite"] = invite
                attendee_data["uid"] = data.get(f"uid{item + 1}")
                attendee_data["first_name"] = data.get(f"first_name{item + 1}")
                attendee_data["last_name"] = data.get(f"last_name{item + 1}")
                attendee_data["phone_number"] = data.get(f"phone_number{item + 1}")
                attendee_data["id_number"] = data.get(f"id_number{item + 1}")
                attendee_data["service"] = data.get(f"service{item + 1}")
                attendee_data["reception"] = data.get(f"reception{item + 1}")
                attendee_data["evening_party"] = data.get(f"evening_party{item + 1}")
                attendee_data["residence"] = data.get(f"residence{item + 1}")
                try:
                    success = self._process_attendee(attendee_data)
                except Exception:
                    logger.exception("error")
                    errors += 1
                else:
                    if not success:
                        errors += 1
                    else:
                        saved += 1

        content = self._get_context_data()
        content["errors"] = errors
        content["saved"] = saved
        content = {'base_template': self.base_template, 'data': content}
        return render(request, self.template_name, content)

    def _process_attendee(self, attendee_data):
        phone_number = attendee_data.get("phone_number")
        first_name = attendee_data.get("first_name")
        last_name = attendee_data.get("last_name")
        id_number = attendee_data.get("id_number")
        residence = attendee_data.get("residence")
        uid = attendee_data.get("uid")
        invite = attendee_data.get("invite")
        if not any([phone_number, first_name, last_name, id_number, uid]):
            return True

        if not any([phone_number, all([first_name, last_name])]):
            return False
        added_for = ATTENDANCE_MAP[str(invite.added_for)].lower()

        if not invite.received:
            invite.received = True
            invite.save()
        try:
            user = get_user_by_phone_number_or_uid(
                phone_number, first_name, last_name, residence, id_number=id_number, uid=uid
            )
        except PhoneValidationError:
            return False
        if uid:
            attendee = Attendee.objects.get(uid=uid)
            if not attendee.user:
                attendee.user = user
            elif user != attendee.user:
                logger.warning(f"User mismatch: {attendee.user} vs {user}")
        else:
            attendee = Attendee(user=user, invite=invite)
        if added_for == "kids":
            attendee.attends_as = AttendsAs.KIDS
        user.phone_number = phone_number

        user.save()
        attendee.attendance = {
            "wedding_ceremony": attendee_data.get("service") == "on",
            "reception": attendee_data.get("reception") == "on",
            "evening_party": attendee_data.get("evening_party") == "on",
        }
        attendee.save()
        return True


class Login(View):
    template_name = get_template_to_render('login.html')
    base_template = get_template_to_render('blank.html')

    def get(self, request, *args, **kwargs):
        complete = setup_complete()
        if not complete:
            return redirect('setup')
        data = {}
        if request.user.is_authenticated:
            return redirect('dashboard')
        content = {'blank_template': self.base_template, 'data': data}
        return render(request, self.template_name, content)

    def post(self, request, *args, **kwargs):
        email = request.POST.get("email")
        data = {}
        if email:
            try:
                user = User.objects.get(email=email)
            except Exception:
                data["error"] = True
            else:
                current_uri = request.build_absolute_uri('')
                token = get_query_string(user)
                link = f"{current_uri}{token}"
                html = f"Click <a target='_blank' href='{link}''>here</a> to log in."
                sender = Attendee.objects.filter(attends_as=AttendsAs.COUPLE)
                resp = None
                if sender:
                    resp = send_email(
                        [user.email], "Login Link", link, sender[0].user.email, html=html
                    )
                if resp and resp.ok:
                    data["success"] = True
                else:
                    data["error"] = True

        content = {'blank_template': self.base_template, 'data': data}
        return render(request, self.template_name, content)


class Setup(View):
    template_name = get_template_to_render('setup.html')
    base_template = get_template_to_render('blank.html')

    def _check_existing_data(self):
        couple = Attendee.objects.filter(attends_as=AttendsAs.COUPLE)
        if not couple:
            return
        data = {
            'a_first_name': couple[0].user.first_name,
            'a_last_name': couple[0].user.last_name,
            'a_email': couple[0].user.email,
        }
        if len(couple) > 1:
            data['b_first_name'] = couple[1].user.first_name
            data['b_last_name'] = couple[1].user.last_name
            data['b_email'] = couple[1].user.email
        self._update_settings_data(data)

    def _get_context_data(self):
        settings, _ = Settings.objects.get_or_create(sitewide=True)
        data = settings.data or {}
        return data

    def _create_invites(self, users):
        if not users:
            return
        for user in users:
            invite, _ = Invite.objects.get_or_create(user=user)
            invite.rsvp = 'yes'
            invite.save()
            attendee = Attendee.objects.filter(user=user)
            if attendee:
                attendee = attendee[0]
            else:
                attendee = Attendee(user=user)
            attendee.invite = invite
            attendee.attends_as = AttendsAs.COUPLE
            attendee.save()

    def _create_users(self, data):
        users = []
        a_email = data.get('a_email')
        if a_email:
            user_a, _ = User.objects.get_or_create(email=a_email)
            user_a.first_name = data.get('a_first_name') or user_a.first_name
            user_a.last_name = data.get('a_last_name') or user_a.last_name
            user_a.save()
            users.append(user_a)

        b_email = data.get('b_email')
        if b_email:
            user_b, _ = User.objects.get_or_create(email=b_email)
            user_b.first_name = data.get('b_first_name') or user_b.first_name
            user_b.last_name = data.get('b_last_name') or user_b.last_name
            user_b.save()
            users.append(user_b)
        return users

    def _update_settings_data(self, updates):
        settings, _ = Settings.objects.get_or_create(sitewide=True)
        data = settings.data or {}
        data.update(updates)
        settings.data = data
        settings.save()
        return data

    def get(self, request, *args, **kwargs):
        complete = setup_complete()
        if complete:
            return redirect('dashboard')
        self._check_existing_data()
        data = self._get_context_data()
        content = {'blank_template': self.base_template, 'data': data}
        return render(request, self.template_name, content)

    def post(self, request, *args, **kwargs):
        complete = setup_complete()
        if complete:
            return redirect('dashboard')
        fields = [
            'b_first_name',
            'b_last_name',
            'b_email',
            'b_parents',
            'a_first_name',
            'a_last_name',
            'a_email',
            'a_parents',
            'date',
            'venue',
            'reception',
            'gift',
            'time',
        ]
        submitted_data = {each: request.POST.get(each, '') for each in fields}
        data = self._update_settings_data(submitted_data)
        users = self._create_users(data)
        self._create_invites(users)
        content = {'blank_template': self.base_template, 'data': data}
        return render(request, self.template_name, content)


class RedirectView(View):
    def get(self, request, *args, **kwargs):
        return redirect('static/img/favicon.ico')
