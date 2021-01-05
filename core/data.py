# -*- coding: utf-8 -*-
import csv
import io

from django.http import FileResponse, HttpResponse
from django.shortcuts import redirect
from django.views import View
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
from reportlab.platypus.tables import TableStyle

from core.utils import is_admin

from .views import get_and_serialize_attendees, get_and_serialize_guests

DATA_TYPES = ["invites", "attendees"]
PDF = "pdf"

DEFAULT_TABLE_STYLE = TableStyle(
    [
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ["LEFTPADDING", [0, 0], [-1, -1], 0],
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, 0), "LEFT"),
        ("LINEBELOW", (0, 0), (-1, -1), 1, colors.lightgrey),
    ]
)

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="centered", alignment=TA_CENTER, fontSize=8))
styles.add(ParagraphStyle(name="myheading", fontSize=8, spaceBefore=4, parent=styles['Heading5']))
styles.add(ParagraphStyle(name="mytitle", fontSize=12, parent=styles['Title']))


def get_invites_data(host, admin=False):
    guests, count = get_and_serialize_guests(
        host, default_value="-", order_by="name", mask=not admin, country_code=False
    )
    headers = ["Name", "Phone No.", "Attending", "Invites", "Confirmed", "Kids"]
    headers = [Paragraph(each, styles["myheading"]) for each in headers]
    data = [headers]
    for num, each in enumerate(guests):
        data.append(
            [
                f"{each['first_name']} {each['last_name']}",
                each["phone_number"],
                Paragraph(each["rsvp"], styles["centered"]),
                str(each["parties"]),
                str(each["rsvp_count"]),
                str(each["kids_allowed"]),
            ]
        )
    return data


def get_attendees_data(host, ext=None, admin=False, ids=False):
    attendees, couple, _ = get_and_serialize_attendees(
        order_by="name",
        active_only=True,
        confirmed=True,
        default_value="-",
        mask=not admin,
        country_code=False,
    )
    headers = ["Name", "Table", "Phone No.", "Residence", "ID No.", "Invite", "Temp Reading"]
    if ext == PDF:
        headers = [Paragraph(each, styles["myheading"]) for each in headers]
    data = [headers]
    for num, each in enumerate(attendees + couple):
        data.append(
            [
                f"{each['first_name']} {each['last_name']}",
                each["table"],
                each["phone_number"],
                each["residence"],
                each["id_number"] if ids else each["id_number_disp"],
                each["invite"],
                "",
            ]
        )
    return data


def create_csv(data, heading, filename):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename={filename}'
    writer = csv.writer(response)
    writer.writerows(data)

    return response


def create_pdf(data, heading, filename):
    pdf = io.BytesIO()

    doc = SimpleDocTemplate(pdf, pagesize=A4)
    elements = [Paragraph(f"{heading} - {len(data) - 1}", styles["mytitle"])]

    table = Table(data)
    table.setStyle(DEFAULT_TABLE_STYLE)

    elements.append(table)
    elements.append(Spacer(1, 0.2 * cm))

    doc.build(elements)
    pdf.seek(0)

    return FileResponse(pdf, as_attachment=True, filename=filename)


class PrintView(View):
    def get(self, request, *args, **kwargs):
        user = self.request.user
        admin = is_admin(user)
        data_type = self.request.GET.get("data")
        ids = self.request.GET.get("ids")
        ext = self.request.GET.get("ext", PDF)
        if ext == PDF:
            func = create_pdf
        elif ext == "csv":
            func = create_csv
        if data_type not in DATA_TYPES:
            return redirect("/")
        host = request.get_host()
        if data_type == "invites":
            data = get_invites_data(host, admin=admin)
            heading = "Invite List"
            filename = f"invites.{ext}"
        elif data_type == "attendees":
            data = get_attendees_data(host, ext=ext, admin=admin, ids=ids)
            heading = "Confirmed Attendees List"
            filename = f"Guest List.{ext}"
            if ids:
                filename = f"Guest List + IDs.{ext}"

        resp = func(data, heading, filename)

        return resp
