app_name = "event_ticket"
app_title = "Event Ticket"
app_publisher = "Aadhil"
app_description = "This app allows to management events"
app_email = "aadhilpm@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Website Route Rules
# -------------------
website_route_rules = [
	{"from_route": "/event/<event_code>", "to_route": "event"},
]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "event_ticket",
# 		"logo": "/assets/event_ticket/logo.png",
# 		"title": "Event Ticket",
# 		"route": "/event_ticket",
# 		"has_permission": "event_ticket.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/event_ticket/css/event_ticket.css"
# app_include_js = "/assets/event_ticket/js/event_ticket.js"

# include js, css files in header of web template
# web_include_css = "/assets/event_ticket/css/event_ticket.css"
# web_include_js = "/assets/event_ticket/js/event_ticket.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "event_ticket/public/scss/website"

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
# app_include_icons = "event_ticket/public/icons.svg"

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
# 	"methods": "event_ticket.utils.jinja_methods",
# 	"filters": "event_ticket.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "event_ticket.install.before_install"
# after_install = "event_ticket.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "event_ticket.uninstall.before_uninstall"
# after_uninstall = "event_ticket.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "event_ticket.utils.before_app_install"
# after_app_install = "event_ticket.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "event_ticket.utils.before_app_uninstall"
# after_app_uninstall = "event_ticket.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "event_ticket.notifications.get_notification_config"

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
# 		"event_ticket.tasks.all"
# 	],
# 	"daily": [
# 		"event_ticket.tasks.daily"
# 	],
# 	"hourly": [
# 		"event_ticket.tasks.hourly"
# 	],
# 	"weekly": [
# 		"event_ticket.tasks.weekly"
# 	],
# 	"monthly": [
# 		"event_ticket.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "event_ticket.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "event_ticket.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "event_ticket.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "event_ticket.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["event_ticket.utils.before_request"]
# after_request = ["event_ticket.utils.after_request"]

# Job Events
# ----------
# before_job = ["event_ticket.utils.before_job"]
# after_job = ["event_ticket.utils.after_job"]

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
# 	"event_ticket.auth.validate"
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
