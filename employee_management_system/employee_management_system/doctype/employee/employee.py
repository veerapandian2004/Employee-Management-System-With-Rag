# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_address, flt, getdate, today


class Employee(Document):
	def validate(self):
		self.clean_fields()
		self.validate_email()
		self.validate_salary()
		if self.email and frappe.db.exists("User", self.email.strip()):
			self.user_id = self.email.strip()

	def validate_email(self):
		if not self.email:
			frappe.throw(_("Email is required to create an employee and generate user credentials."))
		self.email = self.email.strip()
		validate_email_address(self.email, throw=True)

	def validate_salary(self):
		if flt(self.basic_salary) < 0:
			frappe.throw(_("Basic Salary cannot be negative."))

	def clean_fields(self):
		if self.full_name:
			self.full_name = self.full_name.strip()
		if self.designation:
			self.designation = self.designation.strip()

	def after_insert(self):
		self.sync_user_account()

	def on_update(self):
		if self.email and (not self.user_id or not frappe.db.exists("User", self.email)):
			self.sync_user_account()

	def sync_user_account(self):
		"""
		Automatically creates or updates the Frappe User account for this employee.
		Login credentials:
		  Username: self.email
		  Password: self.full_name without spaces (e.g. 'John Doe' -> 'JohnDoe')
		Role: 'Employee'
		"""
		if not self.email:
			return

		email = self.email.strip()
		full_name = (self.full_name or "").strip()
		password = "".join(full_name.split())
		if not password:
			password = "password"

		# Name parts
		name_parts = full_name.split(" ", 1)
		first_name = name_parts[0] if name_parts[0] else email
		last_name = name_parts[1] if len(name_parts) > 1 else ""

		# Ensure 'Employee' role exists
		if not frappe.db.exists("Role", "Employee"):
			role_doc = frappe.get_doc({"doctype": "Role", "role_name": "Employee"})
			role_doc.insert(ignore_permissions=True)

		user_exists = frappe.db.exists("User", email)
		if not user_exists:
			user_doc = frappe.get_doc({
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"last_name": last_name,
				"enabled": 1,
				"send_welcome_email": 0,
				"user_type": "System User",
			})
			user_doc.flags.ignore_password_policy = True
			user_doc.insert(ignore_permissions=True)
		else:
			user_doc = frappe.get_doc("User", email)
			user_doc.first_name = first_name
			user_doc.last_name = last_name
			user_doc.enabled = 1
			user_doc.flags.ignore_password_policy = True
			user_doc.save(ignore_permissions=True)

		# Ensure Employee role is assigned
		if not frappe.db.exists("Has Role", {"parent": email, "role": "Employee"}):
			user_doc.add_roles("Employee")

		# Update password in Frappe auth table unless account has admin/system manager role
		admin_roles = {"System Manager", "Administrator"}
		user_roles = set(frappe.get_roles(email)) if frappe.db.exists("User", email) else set()
		if not admin_roles.intersection(user_roles) and email != "Administrator":
			from frappe.utils.password import update_password
			update_password(email, password)

		# Ensure user_id field on Employee matches email
		if self.user_id != email:
			self.user_id = email
			frappe.db.set_value("Employee", self.name, "user_id", email)

	def on_trash(self):
		# Prevent deletion if active salary slips or attendance exist
		slips = frappe.get_all("Salary Slip", filters={"employee": self.name}, limit=1)
		if slips:
			frappe.msgprint(_("Warning: Employee {0} has linked Salary Slips.").format(self.name))


@frappe.whitelist(allow_guest=True)
def get_employee_list(filters=None, fields=None):
	"""
	Whitelisted API to retrieve list of employees matching filters.
	"""
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)

	if not fields:
		fields = [
			"name",
			"naming_series",
			"full_name",
			"email",
			"phone",
			"department",
			"designation",
			"date_of_joining",
			"reporting_manager",
			"employment_type",
			"status",
			"basic_salary",
			"skills",
			"profile_image",
			"user_id",
		]

	employees = frappe.get_all(
		"Employee",
		filters=filters or {},
		fields=fields,
		order_by="modified desc",
	)
	return employees


@frappe.whitelist(allow_guest=True)
def get_employee_details(employee_id):
	"""
	Whitelisted API to fetch full profile details of a single employee.
	"""
	if not employee_id:
		frappe.throw(_("Employee ID is required."))

	if not frappe.db.exists("Employee", employee_id):
		frappe.throw(_("Employee {0} not found.").format(employee_id))

	doc = frappe.get_doc("Employee", employee_id)
	return doc.as_dict()


@frappe.whitelist(allow_guest=True)
def get_employee_summary_stats():
	"""
	Whitelisted API to compute high-level employee dashboard statistics.
	"""
	total = frappe.db.count("Employee")
	active = frappe.db.count("Employee", filters={"status": "Active"})
	on_leave = frappe.db.count("Employee", filters={"status": "On Leave"})
	inactive = frappe.db.count("Employee", filters={"status": "Inactive"})

	departments = frappe.get_all("Department", fields=["name", "department_name"])
	dept_stats = []
	for d in departments:
		count = frappe.db.count("Employee", filters={"department": d.department_name})
		dept_stats.append({
			"department": d.department_name,
			"count": count
		})

	return {
		"total_employees": total,
		"active_employees": active,
		"on_leave_employees": on_leave,
		"inactive_employees": inactive,
		"department_breakdown": dept_stats,
	}


@frappe.whitelist()
def seed_default_employees():
	"""
	Whitelisted method to seed initial employee records into MariaDB.
	"""
	sample_employees = [
		{
			"full_name": "Sarah Jenkins",
			"email": "sarah.j@company.com",
			"phone": "+1 (555) 234-5678",
			"department": "Engineering",
			"designation": "VP of Engineering",
			"date_of_joining": "2022-01-15",
			"employment_type": "Full-Time",
			"status": "Active",
			"basic_salary": 120000,
			"skills": "React, Python, Architecture, Management",
		},
		{
			"full_name": "Marcus Vance",
			"email": "marcus.v@company.com",
			"phone": "+1 (555) 876-5432",
			"department": "Human Resources",
			"designation": "HR Director",
			"date_of_joining": "2021-06-01",
			"employment_type": "Full-Time",
			"status": "Active",
			"basic_salary": 95000,
			"skills": "Talent Acquisition, Employee Relations, Payroll",
		},
		{
			"full_name": "Elena Rostova",
			"email": "elena.r@company.com",
			"phone": "+1 (555) 345-6789",
			"department": "Product & Design",
			"designation": "Lead UI/UX Designer",
			"date_of_joining": "2023-02-10",
			"employment_type": "Full-Time",
			"status": "Active",
			"basic_salary": 90000,
			"skills": "Figma, User Research, Design Systems",
		},
	]

	created = []
	for data in sample_employees:
		if not frappe.db.exists("Employee", {"email": data["email"]}):
			doc = frappe.get_doc({
				"doctype": "Employee",
				**data
			})
			doc.insert(ignore_permissions=True)
			frappe.db.commit()
			created.append(doc.name)

	return {"message": f"Successfully created {len(created)} employee records", "records": created}
