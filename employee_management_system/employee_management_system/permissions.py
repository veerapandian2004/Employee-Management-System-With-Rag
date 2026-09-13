# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

import frappe


def _is_admin_or_hr(user):
	if not user or user == "Guest":
		return False
	if user == "Administrator":
		return True
	roles = frappe.get_roles(user)
	admin_hr_roles = {"System Manager", "Super Admin", "HR Manager", "Admin / HR Manager"}
	return bool(admin_hr_roles.intersection(roles))


def get_employee_query_conditions(user=None):
	"""
	Permission query conditions for Employee DocType.
	Super Admin, HR Manager, System Manager see all records.
	Employees only see themselves and direct reports.
	"""
	if not user:
		user = frappe.session.user

	if _is_admin_or_hr(user):
		return ""

	emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not emp:
		emp = frappe.db.get_value("Employee", {"email": user}, "name")

	if emp:
		return f"`tabEmployee`.name = {frappe.db.escape(emp)} or `tabEmployee`.reporting_manager = {frappe.db.escape(emp)}"

	return "1=0"


def get_salary_slip_query_conditions(user=None):
	"""
	Permission query conditions for Salary Slip DocType.
	"""
	if not user:
		user = frappe.session.user

	if _is_admin_or_hr(user) or "Finance" in frappe.get_roles(user):
		return ""

	emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not emp:
		emp = frappe.db.get_value("Employee", {"email": user}, "name")

	if emp:
		return f"`tabSalary Slip`.employee = {frappe.db.escape(emp)}"

	return "1=0"


def get_leave_application_query_conditions(user=None):
	"""
	Permission query conditions for Leave Application DocType.
	"""
	if not user:
		user = frappe.session.user

	if _is_admin_or_hr(user):
		return ""

	emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not emp:
		emp = frappe.db.get_value("Employee", {"email": user}, "name")

	if emp:
		return f"(`tabLeave Application`.employee = {frappe.db.escape(emp)} or `tabLeave Application`.approver = {frappe.db.escape(emp)})"

	return "1=0"


def has_employee_permission(doc, ptype="read", user=None):
	"""
	Check document level permission for Employee.
	Only Admin and HR can create, update, or delete employee records.
	Employees can only read their own record and direct reports.
	"""
	if not user:
		user = frappe.session.user

	if _is_admin_or_hr(user):
		return True

	emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not emp:
		emp = frappe.db.get_value("Employee", {"email": user}, "name")

	if emp and (doc.name == emp or doc.reporting_manager == emp):
		return ptype == "read"

	return False


def has_salary_slip_permission(doc, ptype="read", user=None):
	"""
	Check document level permission for Salary Slip.
	Employees can only read their own salary slips.
	"""
	if not user:
		user = frappe.session.user

	if _is_admin_or_hr(user) or "Finance" in frappe.get_roles(user):
		return True

	emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not emp:
		emp = frappe.db.get_value("Employee", {"email": user}, "name")

	if emp and doc.employee == emp:
		return ptype == "read"

	return False


def has_leave_application_permission(doc, ptype="read", user=None):
	"""
	Check document level permission for Leave Application.
	Employees can view own leaves or leaves they must approve.
	Can only cancel (write/delete) own leaves if status is Pending.
	"""
	if not user:
		user = frappe.session.user

	if _is_admin_or_hr(user):
		return True

	emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not emp:
		emp = frappe.db.get_value("Employee", {"email": user}, "name")

	if emp:
		if doc.employee == emp:
			if ptype in ("read", "create"):
				return True
			if ptype in ("write", "delete") and getattr(doc, "status", None) == "Pending":
				return True
		elif doc.approver == emp:
			if ptype in ("read", "write"):
				return True

	return False

