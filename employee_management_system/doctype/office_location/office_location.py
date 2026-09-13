# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class OfficeLocation(Document):
	def validate(self):
		if self.latitude is not None and not (-90.0 <= float(self.latitude) <= 90.0):
			frappe.throw(_("Latitude must be between -90 and 90 degrees."))
		if self.longitude is not None and not (-180.0 <= float(self.longitude) <= 180.0):
			frappe.throw(_("Longitude must be between -180 and 180 degrees."))
		if self.allowed_radius is not None and float(self.allowed_radius) <= 0:
			frappe.throw(_("Allowed radius must be greater than 0 meters."))
		if self.max_accuracy is not None and float(self.max_accuracy) <= 0:
			frappe.throw(_("Maximum GPS accuracy must be greater than 0 meters."))
