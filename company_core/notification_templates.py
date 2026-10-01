from __future__ import annotations

import re
from html import escape, unescape
from urllib.parse import quote

import frappe
from frappe.utils import cint, get_url


SMS_MAX_UNICODE_CHARS = 134

EVENT_CODES = (
    "DEADLINE_T7",
    "DEADLINE_T3",
    "DEADLINE_T1",
    "DEADLINE_DUE",
    "DEADLINE_OVERDUE",
    "MEETING_REMINDER",
    "MEETING_SUMMARY_PUBLISHED",
    "MEETING_ACTION_ASSIGNED",
    "PROGRESS_REPORT_REVISION_REQUESTED",
)

AVAILABLE_VARIABLES = (
    "recipient_name, project_name, item_type, item_title, deadline, "
    "remaining_days, overdue_days, status, assigned_to, priority, "
    "meeting_datetime, meeting_title, meeting_summary, decisions, "
    "action_items, action_items_html, report_period, manager_comment, "
    "action_url, short_item_title, short_project_name"
)

DEFAULT_TEMPLATES = {
    "DEADLINE_T7": {
        "template_name": "Deadline Reminder — T-7",
        "enable_in_app": 1,
        "enable_email": 1,
        "enable_sms": 0,
        "in_app_subject": "یادآوری: ۷ روز تا موعد «{{ item_title }}»",
        "email_subject": "[Grovity] یادآوری موعد | {{ item_title }} | {{ project_name }}",
        "email_body": """
            <p>سلام {{ recipient_name }}،</p>
            <p>این پیام یادآوری می‌کند که موعد «<strong>{{ item_title }}</strong>»
            در پروژه «{{ project_name }}» نزدیک است.</p>
            <p>
              نوع مورد: {{ item_type }}<br>
              موعد: {{ deadline }}<br>
              زمان باقی‌مانده: ۷ روز<br>
              وضعیت فعلی: {{ status }}
            </p>
            <p>لطفاً وضعیت اجرا را بررسی کرده و در صورت نیاز، پیشرفت یا موانع موجود
            را در Grovity به‌روزرسانی کنید.</p>
            <p><a href="{{ action_url }}">مشاهده در Grovity</a></p>
        """,
        "sms_body": "Grovity | ۷ روز تا موعد «{{ short_item_title }}» در {{ short_project_name }}. موعد: {{ deadline }}",
    },
    "DEADLINE_T3": {
        "template_name": "Deadline Reminder — T-3",
        "enable_in_app": 1,
        "enable_email": 1,
        "enable_sms": 0,
        "in_app_subject": "۳ روز تا موعد «{{ item_title }}»",
        "email_subject": "[Grovity] ۳ روز تا موعد | {{ item_title }}",
        "email_body": """
            <p>سلام {{ recipient_name }}،</p>
            <p>تا موعد «<strong>{{ item_title }}</strong>» در پروژه
            «{{ project_name }}» ۳ روز باقی مانده است.</p>
            <p>موعد: {{ deadline }}<br>وضعیت: {{ status }}</p>
            <p>لطفاً در صورت تکمیل کار، وضعیت آن را ثبت کنید. اگر مانع یا تأخیری
            وجود دارد، علت آن را در Grovity به‌روزرسانی کنید.</p>
            <p><a href="{{ action_url }}">مشاهده در Grovity</a></p>
        """,
        "sms_body": "Grovity | ۳ روز تا موعد «{{ short_item_title }}» در {{ short_project_name }}. موعد: {{ deadline }}",
    },
    "DEADLINE_T1": {
        "template_name": "Deadline Reminder — T-1",
        "enable_in_app": 1,
        "enable_email": 1,
        "enable_sms": 1,
        "in_app_subject": "یادآوری مهم: فردا موعد «{{ item_title }}» است",
        "email_subject": "[Grovity] یادآوری مهم: فردا موعد {{ item_title }} است",
        "email_body": """
            <p>سلام {{ recipient_name }}،</p>
            <p>موعد «<strong>{{ item_title }}</strong>» در پروژه
            «{{ project_name }}» فرداست.</p>
            <p>
              موعد: {{ deadline }}<br>
              مسئول: {{ assigned_to }}<br>
              وضعیت فعلی: {{ status }}
            </p>
            <p>لطفاً وضعیت نهایی کار را بررسی کنید و در صورت وجود مانع یا احتمال
            تأخیر، آن را در سامانه ثبت کنید.</p>
            <p><a href="{{ action_url }}">مشاهده در Grovity</a></p>
        """,
        "sms_body": "Grovity | فردا موعد «{{ short_item_title }}» در {{ short_project_name }} است. لطفاً وضعیت را بررسی کنید.",
    },
    "DEADLINE_DUE": {
        "template_name": "Deadline Reminder — Due Date",
        "enable_in_app": 1,
        "enable_email": 1,
        "enable_sms": 1,
        "in_app_subject": "امروز موعد «{{ item_title }}» است",
        "email_subject": "[Grovity] موعد امروز | {{ item_title }} | {{ project_name }}",
        "email_body": """
            <p>سلام {{ recipient_name }}،</p>
            <p>امروز موعد «<strong>{{ item_title }}</strong>» در پروژه
            «{{ project_name }}» است.</p>
            <p>وضعیت فعلی: {{ status }}<br>موعد: {{ deadline }}</p>
            <p>اگر مورد تکمیل شده است، وضعیت آن را در Grovity ثبت کنید. در غیر
            این صورت، وضعیت پیشرفت و علت احتمالی تأخیر را به‌روزرسانی کنید.</p>
            <p><a href="{{ action_url }}">مشاهده در Grovity</a></p>
        """,
        "sms_body": "Grovity | امروز موعد «{{ short_item_title }}» در {{ short_project_name }} است. وضعیت را ثبت کنید.",
    },
    "DEADLINE_OVERDUE": {
        "template_name": "Deadline Reminder — Overdue",
        "enable_in_app": 1,
        "enable_email": 1,
        "enable_sms": 1,
        "in_app_subject": "عبور از موعد: «{{ item_title }}»",
        "email_subject": "[Grovity] عبور از موعد | {{ item_title }} | {{ project_name }}",
        "email_body": """
            <p>سلام {{ recipient_name }}،</p>
            <p>موعد ثبت‌شده برای «<strong>{{ item_title }}</strong>» در پروژه
            «{{ project_name }}» گذشته است.</p>
            <p>
              موعد: {{ deadline }}<br>
              میزان تأخیر: {{ overdue_days }} روز<br>
              وضعیت فعلی: {{ status }}<br>
              مسئول: {{ assigned_to }}
            </p>
            <p>لطفاً وضعیت فعلی، درصد پیشرفت، علت تأخیر یا برنامه ادامه کار را
            در Grovity به‌روزرسانی کنید.</p>
            <p><a href="{{ action_url }}">مشاهده در Grovity</a></p>
        """,
        "sms_body": "Grovity | «{{ short_item_title }}» در {{ short_project_name }}، {{ overdue_days }} روز از موعد گذشته است. وضعیت را به‌روزرسانی کنید.",
    },
    "MEETING_REMINDER": {
        "template_name": "Meeting Reminder",
        "enable_in_app": 1,
        "enable_email": 1,
        "enable_sms": 0,
        "in_app_subject": "یادآوری جلسه پروژه «{{ project_name }}»",
        "email_subject": "[Grovity] یادآوری جلسه | {{ project_name }} | {{ meeting_datetime }}",
        "email_body": """
            <p>سلام {{ recipient_name }}،</p>
            <p>جلسه پروژه «<strong>{{ project_name }}</strong>» در زمان زیر برگزار می‌شود:</p>
            <p>
              زمان: {{ meeting_datetime }}<br>
              موضوع: {{ meeting_title }}
            </p>
            <p><a href="{{ action_url }}">مشاهده جلسه در Grovity</a></p>
        """,
        "sms_body": "Grovity | جلسه {{ short_project_name }} | {{ meeting_datetime }}",
    },
    "MEETING_SUMMARY_PUBLISHED": {
        "template_name": "Meeting Summary Published",
        "enable_in_app": 1,
        "enable_email": 1,
        "enable_sms": 0,
        "in_app_subject": "خلاصه جلسه پروژه «{{ project_name }}» منتشر شد",
        "email_subject": "[Grovity] خلاصه جلسه | {{ project_name }} | {{ meeting_datetime }}",
        "email_body": """
            <p>سلام {{ recipient_name }}،</p>
            <p>خلاصه جلسه پروژه «<strong>{{ project_name }}</strong>» که در
            {{ meeting_datetime }} برگزار شد، توسط مدیر پروژه منتشر شده است.</p>
            <h3>موضوع جلسه</h3>
            <p>{{ meeting_title }}</p>
            <h3>خلاصه جلسه</h3>
            <div>{{ meeting_summary | safe }}</div>
            <h3>تصمیمات جلسه</h3>
            <div>{{ decisions | safe }}</div>
            <h3>اقدامات تعیین‌شده</h3>
            <div>{{ action_items_html | safe }}</div>
            <p><a href="{{ action_url }}">مشاهده جزئیات جلسه در Grovity</a></p>
        """,
        "sms_body": "Grovity | خلاصه جلسه «{{ short_project_name }}» منتشر شد. تصمیمات و اقدامات را در سامانه ببینید.",
    },
    "MEETING_ACTION_ASSIGNED": {
        "template_name": "Meeting Action Assigned",
        "enable_in_app": 1,
        "enable_email": 1,
        "enable_sms": 1,
        "in_app_subject": "اقدام جدید برای شما: «{{ item_title }}»",
        "email_subject": "[Grovity] اقدام جدید برای شما | {{ project_name }}",
        "email_body": """
            <p>سلام {{ recipient_name }}،</p>
            <p>یک اقدام جدید در پروژه «<strong>{{ project_name }}</strong>»
            به شما واگذار شده است.</p>
            <p>
              اقدام: {{ item_title }}<br>
              موعد: {{ deadline }}<br>
              اولویت: {{ priority }}
            </p>
            <p><a href="{{ action_url }}">مشاهده اقدام در Grovity</a></p>
        """,
        "sms_body": "Grovity | اقدام جدید: «{{ short_item_title }}» | {{ short_project_name }} | موعد {{ deadline }}",
    },
    "PROGRESS_REPORT_REVISION_REQUESTED": {
        "template_name": "Progress Report Revision Requested",
        "enable_in_app": 1,
        "enable_email": 1,
        "enable_sms": 0,
        "in_app_subject": "گزارش پیشرفت پروژه «{{ project_name }}» نیازمند اصلاح است",
        "email_subject": "[Grovity] گزارش پیشرفت نیازمند اصلاح است | {{ project_name }}",
        "email_body": """
            <p>سلام {{ recipient_name }}،</p>
            <p>گزارش پیشرفت ثبت‌شده برای پروژه «<strong>{{ project_name }}</strong>»
            نیازمند اصلاح است.</p>
            <p>دوره گزارش: {{ report_period }}</p>
            <h3>نظر مدیر پروژه</h3>
            <p>{{ manager_comment }}</p>
            <p>لطفاً گزارش را اصلاح کرده و مجدداً ارسال کنید.</p>
            <p><a href="{{ action_url }}">مشاهده گزارش در Grovity</a></p>
        """,
        "sms_body": "Grovity | گزارش پیشرفت {{ short_project_name }} نیازمند اصلاح است. نظر مدیر را در سامانه بررسی کنید.",
    },
}


def _plain(value):
    value = unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    return " ".join(value.split())


def _short(value, limit):
    text = _plain(value)
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 1)].rstrip() + "…"


def _sms_safe(value):
    text = _plain(value)
    if len(text) <= SMS_MAX_UNICODE_CHARS:
        return text
    return text[: SMS_MAX_UNICODE_CHARS - 1].rstrip() + "…"


def _desk_url(doctype, name):
    if not doctype or not name:
        return get_url() or ""
    slug = re.sub(r"[^a-z0-9]+", "-", doctype.lower()).strip("-")
    base = (get_url() or "").rstrip("/")
    return f"{base}/app/{slug}/{quote(str(name), safe='')}"


def _template_fields():
    return [
        "name",
        "event_code",
        "template_name",
        "enabled",
        "enable_in_app",
        "enable_email",
        "enable_sms",
        "in_app_subject",
        "email_subject",
        "email_body",
        "sms_body",
    ]


def ensure_default_templates(event_codes=None):
    if not frappe.db.exists("DocType", "Grovity Notification Template"):
        return {"created": 0, "existing": 0}

    requested = sorted(set(event_codes or EVENT_CODES))
    existing_codes = set(
        frappe.get_all(
            "Grovity Notification Template",
            filters={"event_code": ["in", requested]},
            pluck="event_code",
            limit=0,
        )
    )
    created = 0

    for event_code in requested:
        if event_code in existing_codes:
            continue
        values = DEFAULT_TEMPLATES[event_code]
        frappe.get_doc({
            "doctype": "Grovity Notification Template",
            "event_code": event_code,
            "template_name": values["template_name"],
            "enabled": 1,
            "enable_in_app": values["enable_in_app"],
            "enable_email": values["enable_email"],
            "enable_sms": values["enable_sms"],
            "in_app_subject": values["in_app_subject"].strip(),
            "email_subject": values["email_subject"].strip(),
            "email_body": values["email_body"].strip(),
            "sms_body": values["sms_body"].strip(),
            "available_variables": AVAILABLE_VARIABLES,
        }).insert(ignore_permissions=True)
        created += 1

    return {"created": created, "existing": len(existing_codes)}


def load_templates(event_codes):
    codes = sorted({code for code in event_codes if code})
    if not codes:
        return {}

    rows = frappe.get_all(
        "Grovity Notification Template",
        filters={"event_code": ["in", codes]},
        fields=_template_fields(),
        limit=0,
    )
    found = {row.event_code for row in rows}
    missing = [code for code in codes if code not in found]

    if missing:
        ensure_default_templates(missing)
        rows = frappe.get_all(
            "Grovity Notification Template",
            filters={"event_code": ["in", codes]},
            fields=_template_fields(),
            limit=0,
        )

    return {row.event_code: row for row in rows}


def _render(template_text, context):
    return frappe.render_template(template_text or "", context)


def _email_wrapper(body):
    return f"""
    <div dir="rtl" style="direction:rtl;text-align:right;font-family:Tahoma,Arial,sans-serif;
         line-height:1.9;color:#1f2937;max-width:760px;margin:0 auto">
      <div style="border:1px solid #e5e7eb;border-radius:12px;overflow:hidden">
        <div style="padding:16px 22px;background:#111827;color:#fff;font-size:18px">
          Grovity
        </div>
        <div style="padding:22px">{body}</div>
        <div style="padding:12px 22px;border-top:1px solid #e5e7eb;color:#6b7280;font-size:12px">
          سامانه مدیریت پروژه Grovity
        </div>
      </div>
    </div>
    """.strip()


def _context(event, user):
    supplied = dict(event.get("context") or {})
    defaults = {
        "recipient_name": "",
        "project_name": event.get("project") or "",
        "item_type": "",
        "item_title": event.get("source_name") or "",
        "deadline": "",
        "remaining_days": "",
        "overdue_days": "",
        "status": "",
        "assigned_to": "",
        "priority": "",
        "meeting_datetime": "",
        "meeting_title": "",
        "meeting_summary": "",
        "decisions": "",
        "action_items": "",
        "action_items_html": "",
        "report_period": "",
        "manager_comment": "",
        "action_url": "",
    }
    defaults.update(supplied)

    if not defaults["recipient_name"]:
        defaults["recipient_name"] = _short((user or "").split("@")[0].replace(".", " "), 50) or "همکار گرامی"

    if not defaults["action_url"]:
        defaults["action_url"] = _desk_url(event.get("source_doctype"), event.get("source_name"))

    defaults["short_item_title"] = _short(defaults.get("item_title"), 34)
    defaults["short_project_name"] = _short(defaults.get("project_name"), 28)
    return defaults


def render_delivery(event, channel, user, template=None):
    context = _context(event, user)

    if not template:
        subject = str(event.get("subject") or "[Grovity] اعلان جدید")
        message = str(event.get("message") or "یک اعلان جدید در Grovity ثبت شده است.")
        if channel == "Email":
            return subject, _email_wrapper(f"<p>{escape(message)}</p>")
        if channel == "SMS":
            return subject, _sms_safe(message)
        return subject, message

    try:
        if channel == "In-App":
            subject = _plain(_render(template.in_app_subject, context))
            return subject, subject

        if channel == "Email":
            subject = _plain(_render(template.email_subject, context))
            body = _render(template.email_body, context)
            return subject, _email_wrapper(body)

        if channel == "SMS":
            subject = _plain(_render(template.in_app_subject, context))
            message = _sms_safe(_render(template.sms_body, context))
            return subject, message

    except Exception:
        frappe.log_error(
            title=f"Grovity notification template render failed: {event.get('event_code')}",
            message=frappe.get_traceback(),
        )
        fallback = f"اعلان جدید Grovity: {context.get('item_title') or context.get('project_name') or event.get('source_name') or ''}"
        if channel == "Email":
            return "[Grovity] اعلان جدید", _email_wrapper(f"<p>{escape(fallback)}</p>")
        if channel == "SMS":
            return "[Grovity] اعلان جدید", _sms_safe(fallback)
        return fallback, fallback

    return "[Grovity] اعلان جدید", "اعلان جدید Grovity"
