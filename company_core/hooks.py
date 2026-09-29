app_name = "company_core"
app_title = "Company Core"
app_publisher = "Sanabad Sustainable Energy (SSE)"
app_description = "Project-centric company operating system"
app_email = "SanabadEnergy@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "company_core",
# 		"logo": "/assets/company_core/logo.png",
# 		"title": "Company Core",
# 		"route": "/company_core",
# 		"has_permission": "company_core.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/company_core/css/company_core.css"
# app_include_js = "/assets/company_core/js/company_core.js"

# include js, css files in header of web template
# web_include_css = "/assets/company_core/css/company_core.css"
# web_include_js = "/assets/company_core/js/company_core.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "company_core/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "company_core/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "company_core.utils.jinja_methods",
# 	"filters": "company_core.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "company_core.install.before_install"
# after_install = "company_core.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "company_core.uninstall.before_uninstall"
# after_uninstall = "company_core.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "company_core.utils.before_app_install"
# after_app_install = "company_core.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "company_core.utils.before_app_uninstall"
# after_app_uninstall = "company_core.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "company_core.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "company_core.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["company_core.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"company_core.tasks.all"
# 	],
# 	"daily": [
# 		"company_core.tasks.daily"
# 	],
# 	"hourly": [
# 		"company_core.tasks.hourly"
# 	],
# 	"weekly": [
# 		"company_core.tasks.weekly"
# 	],
# 	"monthly": [
# 		"company_core.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "company_core.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "company_core.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "company_core.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "company_core.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["company_core.utils.before_request"]
# after_request = ["company_core.utils.after_request"]

# Job Events
# ----------
# before_job = ["company_core.utils.before_job"]
# after_job = ["company_core.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"company_core.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

permission_query_conditions = {
    "Project": "company_core.permissions.get_project_permission_query_conditions",
    "Project Membership": "company_core.permissions.get_project_membership_permission_query_conditions",
}


has_permission = {
    "Project": "company_core.permissions.has_project_permission",
    "Project Membership": "company_core.permissions.has_project_membership_permission",
}


# === GROVITY PHASE 2B STATUS HISTORY ===

permission_query_conditions = globals().get(
    "permission_query_conditions",
    {},
)

permission_query_conditions.update(
    {
        "Project": (
            "company_core.permissions."
            "get_project_permission_query_conditions"
        ),
        "Project Membership": (
            "company_core.permissions."
            "get_project_membership_permission_query_conditions"
        ),
        "Project Status History": (
            "company_core.permissions."
            "get_project_status_history_permission_query_conditions"
        ),
    }
)


has_permission = globals().get(
    "has_permission",
    {},
)

has_permission.update(
    {
        "Project": (
            "company_core.permissions."
            "has_project_permission"
        ),
        "Project Membership": (
            "company_core.permissions."
            "has_project_membership_permission"
        ),
        "Project Status History": (
            "company_core.permissions."
            "has_project_status_history_permission"
        ),
    }
)


doc_events = globals().get(
    "doc_events",
    {},
)

doc_events.setdefault(
    "Project",
    {},
)

doc_events["Project"].update(
    {
        "before_save": (
            "company_core.project_events."
            "validate_project_status_change"
        ),
        "on_update": (
            "company_core.project_events."
            "record_project_status_change"
        ),
    }
)


# === GROVITY PHASE 2C SUSPENSION EVENT ===

permission_query_conditions = globals().get(
    "permission_query_conditions",
    {},
)

permission_query_conditions.update(
    {
        "Suspension Event": (
            "company_core.permissions."
            "get_suspension_event_permission_query_conditions"
        ),
    }
)


has_permission = globals().get(
    "has_permission",
    {},
)

has_permission.update(
    {
        "Suspension Event": (
            "company_core.permissions."
            "has_suspension_event_permission"
        ),
    }
)

# === GROVITY PHASE 2D TASK CORE ===

permission_query_conditions = globals().get(
    "permission_query_conditions",
    {},
)
permission_query_conditions.update(
    {
        "Task": (
            "company_core.permissions."
            "get_task_permission_query_conditions"
        ),
    }
)

has_permission = globals().get(
    "has_permission",
    {},
)
has_permission.update(
    {
        "Task": (
            "company_core.permissions."
            "has_task_permission"
        ),
    }
)

doc_events = globals().get(
    "doc_events",
    {},
)
doc_events.setdefault(
    "Task",
    {},
)
doc_events["Task"].update(
    {
        "validate": (
            "company_core.task_events."
            "validate_task_extensions"
        ),
    }
)

