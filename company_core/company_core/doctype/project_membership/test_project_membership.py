# Copyright (c) 2026, Sanabad Sustainable Energy (SSE) and Contributors
# See license.txt

# import frappe
from frappe.tests import IntegrationTestCase


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]



class IntegrationTestProjectMembership(IntegrationTestCase):
	"""
	Integration tests for ProjectMembership.
	Use this class for testing interactions between multiple components.
	"""

	pass
