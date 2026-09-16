# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

import calendar
import datetime
import json
import re
import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, nowdate


# ---------------- HELPERS & SECURITY GUARDS ----------------
def _resolve_employee_link(val):
	if not val:
		return None
	val = str(val).strip()
	if not val or val in ["-- No Manager --", "None"]:
		return None
	if frappe.db.exists("Employee", val):
		return val
	matched = frappe.db.get_value("Employee", {"full_name": val}, "name")
	if matched:
		return matched
	matched_ns = frappe.db.get_value("Employee", {"naming_series": val}, "name")
	if matched_ns:
		return matched_ns
	return None


def _resolve_department_link(val):
	if not val:
		return None
	val = str(val).strip()
	if not val:
		return None
	if frappe.db.exists("Department", val):
		return val
	matched = frappe.db.get_value("Department", {"department_name": val}, "name")
	if matched:
		return matched
	return None


def _resolve_leave_type_link(val):
	if not val:
		return None
	val = str(val).strip()
	if not val:
		return None
	if frappe.db.exists("Leave Type", val):
		return val
	matched = frappe.db.get_value("Leave Type", {"leave_type_name": val}, "name")
	if matched:
		return matched
	try:
		records = frappe.get_all("Leave Type", fields=["name", "leave_type_name"])
		for r in records:
			if r.get("leave_type_name") and r["leave_type_name"].strip().lower() == val.lower():
				return r["name"]
			if r.get("name") and r["name"].strip().lower() == val.lower():
				return r["name"]
	except Exception:
		pass
	return val


def _normalize_phone(val):
	if not val:
		return ""
	val = str(val).strip()
	if not val:
		return ""
	if not val.startswith("+"):
		digits = "".join(ch for ch in val if ch.isdigit())
		if len(digits) == 10:
			return f"+91{digits}"
		elif digits:
			return f"+{digits}"
	return val


def _normalize_employee_id(val):
	if not val:
		return None
	val = str(val).strip()
	m = re.match(r"^EMP-(\d+)$", val, re.IGNORECASE)
	if m:
		num_str = m.group(1)
		if len(num_str) > 5 and num_str.endswith("00001"):
			num_str = num_str[:-5]
		try:
			num = int(num_str)
			return f"EMP-{num:03d}"
		except ValueError:
			return val
	return val


def _get_next_employee_id():
	existing = frappe.get_all("Employee", fields=["name"])
	max_num = 0
	for e in existing:
		m = re.match(r"^EMP-(\d+)$", e.name or "", re.IGNORECASE)
		if m:
			n_str = m.group(1)
			if len(n_str) > 5 and n_str.endswith("00001"):
				n_str = n_str[:-5]
			try:
				num = int(n_str)
				if num < 10000 and num > max_num:
					max_num = num
			except ValueError:
				pass
	return f"EMP-{max_num + 1:03d}"


def _get_user_app_role(user=None):
	if not user:
		user = frappe.session.user
	if user in ["Guest", ""]:
		return "Guest"

	roles = frappe.get_roles(user)
	if user == "Administrator" or "System Manager" in roles or "Super Admin" in roles or "Administrator" in roles:
		return "Administrator"
	elif any(r in roles for r in ["HR Manager", "HR User", "HR", "HR Executive", "Admin / HR Manager"]):
		return "HR"
	elif "Employee" in roles or _get_linked_employee(user) or any(r in roles for r in ["Team Lead", "Department Manager", "Manager", "Leave Approver"]):
		return "Employee"
	return "Employee"


def _is_hr_employee(emp_name):
	if not emp_name:
		return False
	emp = frappe.db.get_value("Employee", emp_name, ["user_id", "email", "designation"], as_dict=True)
	if not emp:
		return False
	if emp.get("designation") and any(h in emp["designation"].upper() for h in ["HR", "HUMAN RESOURCE"]):
		return True
	user = emp.get("user_id") or emp.get("email")
	if user and frappe.db.exists("User", user):
		roles = frappe.get_roles(user)
		if any(r in roles for r in ["HR Manager", "HR User", "HR", "Admin / HR Manager", "HR Executive"]):
			return True
	return False


def _get_linked_employee(user=None):
	if not user:
		user = frappe.session.user
	if user in ["Guest", ""]:
		return None

	emp_name = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not emp_name:
		emp_name = frappe.db.get_value("Employee", {"email": user}, "name")
	if not emp_name and user in ["Administrator", "admin@ems.com"]:
		emp_name = frappe.db.get_value("Employee", {"user_id": "admin@ems.com"}, "name")
		if not emp_name:
			emp_name = frappe.db.get_value("Employee", "EMP-001", "name")

	if emp_name:
		return frappe.get_doc("Employee", emp_name).as_dict()
	return None


def _check_authenticated():
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Authentication required to access this resource"), frappe.AuthenticationError)
	return user


def _check_admin_or_hr():
	user = _check_authenticated()
	role = _get_user_app_role(user)
	if role not in ["Administrator", "HR"]:
		frappe.throw(_("Access Denied: Administrator or HR role required"), frappe.PermissionError)
	return user, role


def _check_admin_only():
	user = _check_authenticated()
	role = _get_user_app_role(user)
	if role != "Administrator":
		frappe.throw(_("Access Denied: Administrator role required"), frappe.PermissionError)
	return user, role


def _create_in_app_notification(for_user, title, message, doc_type=None, doc_name=None):
	"""Creates an in-app Notification Log record for the specified user."""
	if not for_user or for_user == "Guest":
		return None
	try:
		if not frappe.db.exists("User", for_user):
			return None
		notif = frappe.get_doc({
			"doctype": "Notification Log",
			"subject": title,
			"email_content": message,
			"for_user": for_user,
			"type": "Alert",
			"document_type": doc_type or "Employee",
			"document_name": doc_name or for_user,
			"read": 0,
		})
		notif.insert(ignore_permissions=True)
		frappe.db.commit()
		return notif.name
	except Exception as e:
		frappe.logger().error(f"Failed to create in-app notification for {for_user}: {e}")
		return None


def _get_user_for_employee(employee_id):
	"""Resolves the associated User ID or email for an Employee."""
	if not employee_id:
		return None
	user_id = frappe.db.get_value("Employee", employee_id, "user_id")
	if not user_id:
		user_id = frappe.db.get_value("Employee", employee_id, "email")
	return user_id


def _get_employee_shift_type(employee, attendance_date):
	"""Finds the active Shift Type for an employee on a specific date."""
	d = getdate(attendance_date)
	assignment = frappe.get_all(
		"Shift Assignment",
		filters={
			"employee": employee,
			"status": "Active",
			"start_date": ["<=", d],
		},
		fields=["shift_type", "end_date"],
		order_by="start_date desc",
		limit=1,
	)
	if assignment:
		if not assignment[0].get("end_date") or getdate(assignment[0]["end_date"]) >= d:
			return assignment[0]["shift_type"]
	default_shift = frappe.db.get_value("Shift Type", {"enable_auto_attendance": 1}, "name")
	return default_shift or "Day Shift"


def _calculate_employee_leave_balance(employee, leave_type, exclude_application=None):
	"""
	Calculates annual entitlement, consumed days, pending days, and remaining balance
	for an employee and leave type in the current calendar year.
	"""
	lt_name = _resolve_leave_type_link(leave_type) or leave_type
	emp_id = _resolve_employee_link(employee) or employee

	max_days = flt(frappe.db.get_value("Leave Type", lt_name, "max_days_per_year") or 0)
	display_name = frappe.db.get_value("Leave Type", lt_name, "leave_type_name") or lt_name

	current_year = getdate(nowdate()).year
	start_of_year = f"{current_year}-01-01"
	end_of_year = f"{current_year}-12-31"

	# Fetch leaves in this year
	query_filters = [
		["Leave Application", "employee", "=", emp_id],
		["Leave Application", "leave_type", "=", lt_name],
		["Leave Application", "from_date", ">=", start_of_year],
		["Leave Application", "from_date", "<=", end_of_year],
		["Leave Application", "status", "in", ["Approved", "Pending"]],
	]
	if exclude_application:
		query_filters.append(["Leave Application", "name", "!=", exclude_application])

	leaves = frappe.get_all(
		"Leave Application",
		filters=query_filters,
		fields=["name", "status", "total_days"],
	)

	consumed = sum(flt(l.total_days) for l in leaves if l.status == "Approved")
	pending = sum(flt(l.total_days) for l in leaves if l.status == "Pending")

	remaining = max(0.0, round(max_days - consumed - pending, 2))
	available = max(0.0, round(max_days - consumed, 2))

	return {
		"employee": emp_id,
		"leave_type": lt_name,
		"leave_type_name": display_name,
		"max_days_per_year": max_days,
		"consumed": consumed,
		"pending": pending,
		"remaining_balance": remaining,
		"available_balance": available,
	}


def _validate_leave_overlap(employee, from_date, to_date, exclude_application=None):
	"""Checks whether an existing Pending or Approved leave overlaps the requested date range."""
	f_date = getdate(from_date)
	t_date = getdate(to_date)

	if t_date < f_date:
		frappe.throw(_("To Date cannot be earlier than From Date."))

	query = """
		SELECT name, leave_type, from_date, to_date, status
		FROM `tabLeave Application`
		WHERE employee = %(employee)s
		  AND status IN ('Pending', 'Approved')
		  AND from_date <= %(to_date)s
		  AND to_date >= %(from_date)s
	"""
	params = {
		"employee": employee,
		"from_date": str(f_date),
		"to_date": str(t_date),
	}
	if exclude_application:
		query += " AND name != %(exclude_name)s"
		params["exclude_name"] = exclude_application

	overlapping = frappe.db.sql(query, params, as_dict=True)
	if overlapping:
		frappe.throw(
			_("A leave application already exists for the selected date range ({0} to {1}).").format(
				overlapping[0].from_date, overlapping[0].to_date
			)
		)


def _sync_leave_to_attendance(doc):
	"""
	Synchronizes approved leave range to attendance records immediately within an atomic transaction.
	Respects Holiday and Weekly Off priority rules.
	"""
	from employee_management_system.employee_management_system.shift_attendance import (
		is_company_holiday,
		is_weekly_off_for_shift,
		upsert_attendance_record,
	)

	start_d = getdate(doc.from_date)
	end_d = getdate(doc.to_date)
	curr_d = start_d
	emp = doc.employee
	lt = doc.leave_type

	while curr_d <= end_d:
		shift_name = _get_employee_shift_type(emp, curr_d)
		is_holiday, holiday_name = is_company_holiday(curr_d)
		is_weekly_off = is_weekly_off_for_shift(shift_name, curr_d)

		if is_holiday:
			att_status = "Holiday"
			remarks = f"Approved Leave ({lt}) [Holiday: {holiday_name}]"
		elif is_weekly_off:
			att_status = "Weekly Off"
			remarks = f"Approved Leave ({lt}) [Weekly Off: {curr_d.strftime('%A')}]"
		else:
			att_status = "On Leave"
			remarks = f"Approved Leave: {lt} ({doc.name})"

		upsert_attendance_record(
			employee=emp,
			attendance_date=curr_d,
			status=att_status,
			shift=shift_name,
			leave_application=doc.name,
			leave_type=lt,
			remarks=remarks,
			force_status=True,
		)
		curr_d += datetime.timedelta(days=1)


def _revert_leave_attendance(doc):
	"""
	Reverts attendance records linked to a cancelled or rejected leave application.
	Recalculates each affected date to its true underlying status.
	"""
	from employee_management_system.employee_management_system.shift_attendance import (
		process_attendance_for_employee_shift,
	)

	att_records = frappe.get_all(
		"Attendance",
		filters={"leave_application": doc.name},
		fields=["name", "attendance_date", "employee", "shift"],
	)

	for att in att_records:
		att_date = att["attendance_date"]
		shift_name = att.get("shift") or _get_employee_shift_type(doc.employee, att_date)

		# Clear linked leave on the record first
		frappe.db.set_value(
			"Attendance",
			att["name"],
			{"leave_application": None, "leave_type": None},
			update_modified=False,
		)

		# Recalculate true attendance status for this date
		process_attendance_for_employee_shift(
			employee=doc.employee,
			shift_type_name=shift_name,
			attendance_date=att_date,
			force_status=True,
		)


# ---------------- AUTHENTICATION & USER ----------------
@frappe.whitelist(allow_guest=True)
def get_current_user():
	user = frappe.session.user
	if not user or user == "Guest":
		return {
			"user": "Guest",
			"full_name": "Guest",
			"role": "Guest",
			"roles": ["Guest"],
			"employee": None,
			"is_logged_in": False,
		}

	roles = frappe.get_roles(user)
	app_role = _get_user_app_role(user)
	linked_emp = _get_linked_employee(user)
	full_name = frappe.utils.get_fullname(user) or user

	if linked_emp and linked_emp.get("full_name"):
		full_name = linked_emp.get("full_name")

	return {
		"user": user,
		"full_name": full_name,
		"role": app_role,
		"roles": roles,
		"employee": linked_emp,
		"is_logged_in": True,
	}


# ---------------- EMPLOYEES ----------------
@frappe.whitelist()
def get_employees():
	if not frappe.db.exists("DocType", "Employee"):
		return []

	user = frappe.session.user
	if not user or user == "Guest":
		return []

	app_role = _get_user_app_role(user)
	linked_emp = _get_linked_employee(user)

	candidate_fields = [
		"name",
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
		"naming_series",
	]

	valid_fields = ["name"]
	for field in candidate_fields:
		if field != "name":
			try:
				if frappe.db.has_column("Employee", field):
					valid_fields.append(field)
			except Exception:
				pass

	# If regular employee, return self + colleagues in same department + manager + direct reports
	if app_role == "Employee":
		if not linked_emp:
			return []
		emp_name = linked_emp.get("name")
		records = frappe.get_all(
			"Employee",
			fields=valid_fields,
			filters=[["Employee", "name", "in", [emp_name]]],
			order_by="modified desc",
		)
		existing_names = {r["name"] for r in records}

		dept = linked_emp.get("department")
		if dept:
			dept_records = frappe.get_all(
				"Employee",
				fields=valid_fields,
				filters={"department": dept},
				order_by="modified desc",
			)
			for dr in dept_records:
				if dr["name"] not in existing_names:
					records.append(dr)
					existing_names.add(dr["name"])

		mgr = linked_emp.get("reporting_manager")
		if mgr:
			mgr_records = frappe.get_all(
				"Employee",
				fields=valid_fields,
				filters=[["Employee", "name", "in", [mgr]]],
			)
			for mr in mgr_records:
				if mr["name"] not in existing_names:
					records.append(mr)
					existing_names.add(mr["name"])

		direct_records = frappe.get_all(
			"Employee",
			fields=valid_fields,
			filters=[["Employee", "reporting_manager", "in", [emp_name]]],
		)
		for dr in direct_records:
			if dr["name"] not in existing_names:
				records.append(dr)
				existing_names.add(dr["name"])
	else:
		records = frappe.get_all(
			"Employee",
			fields=valid_fields,
			order_by="modified desc",
		)

	for r in records:
		if "naming_series" not in r or not r.get("naming_series"):
			r["naming_series"] = r.get("name")
		if "full_name" not in r or not r.get("full_name"):
			r["full_name"] = r.get("name")

	return records


@frappe.whitelist()
def create_employee(data):
	_check_admin_or_hr()

	if isinstance(data, str):
		data = frappe.parse_json(data)
	if "reporting_manager" in data:
		data["reporting_manager"] = _resolve_employee_link(data.get("reporting_manager"))
	if "department" in data:
		data["department"] = _resolve_department_link(data.get("department"))
	if "phone" in data:
		data["phone"] = _normalize_phone(data.get("phone"))
	if "email" in data and data.get("email"):
		data["email"] = str(data["email"]).strip()
		if frappe.db.exists("User", data["email"]):
			data["user_id"] = data["email"]
		else:
			data.pop("user_id", None)

	emp_id = _normalize_employee_id(data.get("naming_series") or data.get("name"))
	if not emp_id or frappe.db.exists("Employee", emp_id):
		emp_id = _get_next_employee_id()

	data["name"] = emp_id

	try:
		meta = frappe.get_meta("Employee")
		if meta.has_field("naming_series"):
			data["naming_series"] = emp_id
		else:
			data.pop("naming_series", None)
	except Exception:
		data.pop("naming_series", None)

	doc = frappe.get_doc({"doctype": "Employee", **data})
	doc.name = emp_id
	doc.flags.name_set = True
	try:
		if hasattr(doc, "naming_series"):
			doc.naming_series = emp_id
	except Exception:
		pass

	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	doc.reload()

	res = doc.as_dict()
	if "naming_series" not in res or not res.get("naming_series"):
		res["naming_series"] = res.get("name")
	return res


@frappe.whitelist()
def update_employee(name, data):
	_check_admin_or_hr()

	if isinstance(data, str):
		data = frappe.parse_json(data)
	if "reporting_manager" in data:
		data["reporting_manager"] = _resolve_employee_link(data.get("reporting_manager"))
	if "department" in data:
		data["department"] = _resolve_department_link(data.get("department"))
	if "phone" in data:
		data["phone"] = _normalize_phone(data.get("phone"))

	try:
		meta = frappe.get_meta("Employee")
		if not meta.has_field("naming_series"):
			data.pop("naming_series", None)
	except Exception:
		data.pop("naming_series", None)

	doc = frappe.get_doc("Employee", name)
	doc.update(data)
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	res = doc.as_dict()
	if "naming_series" not in res or not res.get("naming_series"):
		res["naming_series"] = res.get("name")
	return res


@frappe.whitelist()
def delete_employee(name):
	user, role = _check_admin_or_hr()

	if not name:
		frappe.throw(_("Employee identifier is required."))

	target = _resolve_employee_link(name) or name
	if not frappe.db.exists("Employee", target):
		frappe.throw(_("Employee not found."))

	# Protect System Administrator from deletion
	emp_doc = frappe.get_doc("Employee", target)
	linked_user = (emp_doc.user_id or emp_doc.email or "").strip().lower()
	if target == "EMP-001" or linked_user in ["administrator", "admin@ems.com"]:
		frappe.throw(_("System Administrator record cannot be deleted."), frappe.PermissionError)

	# Protect current user from deleting their own employee record
	linked_emp = _get_linked_employee(user)
	if linked_emp and (linked_emp.get("name") == target or linked_emp.get("naming_series") == target):
		frappe.throw(_("You cannot delete your own employee record."), frappe.PermissionError)

	frappe.delete_doc("Employee", target, ignore_permissions=True, force=True)
	frappe.db.commit()
	return True


# ---------------- DEPARTMENTS ----------------
@frappe.whitelist()
def get_departments():
	if not frappe.db.exists("DocType", "Department"):
		return []

	user = frappe.session.user
	if not user or user == "Guest":
		return []

	records = frappe.get_all(
		"Department",
		fields=["name", "department_name", "department_head", "parent_department", "cost_center"],
		order_by="modified desc",
	)
	for r in records:
		if not r.get("department_name"):
			r["department_name"] = r.get("name")
		if r.get("department_head"):
			head_id = r.get("department_head")
			emp_name = frappe.db.get_value("Employee", head_id, "full_name")
			if not emp_name:
				emp_name = frappe.db.get_value("Employee", {"naming_series": head_id}, "full_name")
			r["department_head_name"] = emp_name or head_id
		else:
			r["department_head_name"] = ""
	return records


@frappe.whitelist()
def create_department(data=None, **kwargs):
	_check_admin_or_hr()

	if isinstance(data, str):
		try:
			data = frappe.parse_json(data)
		except Exception:
			pass
	if not data or not isinstance(data, dict):
		data = kwargs.copy()
		if "data" in data and isinstance(data["data"], dict):
			data = data["data"]

	dept_name = str(data.get("department_name") or data.get("name") or "").strip()
	if not dept_name:
		frappe.throw(_("Department Name is required."))

	if "parent_department" in data:
		data["parent_department"] = _resolve_department_link(data.get("parent_department"))
	if "department_head" in data:
		data["department_head"] = _resolve_employee_link(data.get("department_head"))

	existing = None
	if frappe.db.exists("Department", dept_name):
		existing = dept_name
	else:
		existing = frappe.db.get_value("Department", {"department_name": dept_name}, "name")

	if existing:
		return update_department(existing, data)

	data["department_name"] = dept_name
	data["name"] = dept_name

	doc = frappe.get_doc({"doctype": "Department", **data})
	doc.name = dept_name
	doc.department_name = dept_name
	doc.flags.name_set = True
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	res = doc.as_dict()
	if res.get("department_head"):
		emp_name = frappe.db.get_value("Employee", res.get("department_head"), "full_name")
		res["department_head_name"] = emp_name or res.get("department_head")
	return res


@frappe.whitelist()
def update_department(name=None, data=None, **kwargs):
	_check_admin_or_hr()

	if isinstance(data, str):
		try:
			data = frappe.parse_json(data)
		except Exception:
			pass

	if not data or not isinstance(data, dict):
		data = kwargs.copy()
		if "data" in data and isinstance(data["data"], dict):
			data = data["data"]

	if not name:
		name = (
			data.get("original_name")
			or data.get("name")
			or data.get("department_name")
			or frappe.form_dict.get("name")
		)

	if "parent_department" in data:
		data["parent_department"] = _resolve_department_link(data.get("parent_department"))

	target = name
	if target and not frappe.db.exists("Department", target):
		target = frappe.db.get_value("Department", {"department_name": target}, "name") or target

	if not target or not frappe.db.exists("Department", target):
		return create_department(data)

	new_dept_name = str(data.get("department_name") or data.get("name") or "").strip()

	if new_dept_name and new_dept_name != target:
		try:
			frappe.rename_doc("Department", target, new_dept_name, force=True, ignore_permissions=True)
			target = new_dept_name
		except Exception:
			frappe.db.sql("""
				UPDATE `tabDepartment`
				SET `name` = %(new)s, `department_name` = %(new)s
				WHERE `name` = %(old)s
			""", {"new": new_dept_name, "old": target})
			frappe.db.sql("""
				UPDATE `tabEmployee`
				SET `department` = %(new)s
				WHERE `department` = %(old)s
			""", {"new": new_dept_name, "old": target})
			frappe.db.sql("""
				UPDATE `tabDepartment`
				SET `parent_department` = %(new)s
				WHERE `parent_department` = %(old)s
			""", {"new": new_dept_name, "old": target})
			frappe.db.commit()
			target = new_dept_name

	doc = frappe.get_doc("Department", target)
	doc.department_name = target
	if "department_head" in data:
		doc.department_head = _resolve_employee_link(data.get("department_head"))
	if "parent_department" in data:
		doc.parent_department = data.get("parent_department")
	if "cost_center" in data:
		doc.cost_center = data.get("cost_center") or ""

	doc.save(ignore_permissions=True)
	frappe.db.sql("""
		UPDATE `tabDepartment`
		SET `department_name` = `name`
		WHERE `name` = %(target)s AND (`department_name` IS NULL OR `department_name` != `name`)
	""", {"target": target})
	frappe.db.commit()

	res = doc.as_dict()
	if res.get("department_head"):
		emp_name = frappe.db.get_value("Employee", res.get("department_head"), "full_name")
		res["department_head_name"] = emp_name or res.get("department_head")
	return res


@frappe.whitelist()
def delete_department(name=None, **kwargs):
	_check_admin_only()

	target = name or kwargs.get("name") or frappe.form_dict.get("name")
	if not target:
		return True

	if not frappe.db.exists("Department", target):
		target = frappe.db.get_value("Department", {"department_name": target}, "name") or target

	try:
		frappe.delete_doc("Department", target, ignore_permissions=True, force=True)
	except Exception:
		frappe.db.sql("DELETE FROM `tabDepartment` WHERE `name` = %(target)s OR `department_name` = %(target)s", {"target": target})
		frappe.db.sql("UPDATE `tabEmployee` SET `department` = NULL WHERE `department` = %(target)s", {"target": target})
		frappe.db.sql("UPDATE `tabDepartment` SET `parent_department` = NULL WHERE `parent_department` = %(target)s", {"target": target})

	frappe.db.commit()
	return True


# ---------------- LEAVE APPLICATION ----------------
@frappe.whitelist()
def get_leave_applications():
	if not frappe.db.exists("DocType", "Leave Application"):
		return []

	user = frappe.session.user
	if not user or user == "Guest":
		return []

	app_role = _get_user_app_role(user)
	linked_emp = _get_linked_employee(user)

	filters = {}
	if app_role == "Employee":
		if not linked_emp:
			return []
		emp_name = linked_emp.get("name")
		# Filter to applications where employee is either the applicant or the approver
		filters = [
			["Leave Application", "employee", "=", emp_name]
		]
		records = frappe.get_all(
			"Leave Application",
			fields=[
				"name",
				"employee",
				"leave_type",
				"from_date",
				"to_date",
				"total_days",
				"reason",
				"status",
				"approver",
			],
			filters=[["Leave Application", "employee", "=", emp_name]],
			order_by="modified desc",
		)
		# Also get leaves where user is designated approver
		approver_records = frappe.get_all(
			"Leave Application",
			fields=[
				"name",
				"employee",
				"leave_type",
				"from_date",
				"to_date",
				"total_days",
				"reason",
				"status",
				"approver",
			],
			filters=[["Leave Application", "approver", "=", emp_name]],
			order_by="modified desc",
		)
		existing_names = {r["name"] for r in records}
		for ar in approver_records:
			if ar["name"] not in existing_names:
				records.append(ar)
	else:
		records = frappe.get_all(
			"Leave Application",
			fields=[
				"name",
				"employee",
				"leave_type",
				"from_date",
				"to_date",
				"total_days",
				"reason",
				"status",
				"approver",
			],
			order_by="modified desc",
		)

	for r in records:
		if r.get("employee"):
			emp_name = frappe.db.get_value("Employee", r.get("employee"), "full_name")
			r["employee_name"] = emp_name or r.get("employee")
		else:
			r["employee_name"] = "N/A"

		if r.get("leave_type"):
			lt_name = frappe.db.get_value("Leave Type", r.get("leave_type"), "leave_type_name")
			if lt_name:
				r["leave_type"] = lt_name

		if r.get("approver"):
			app_name = frappe.db.get_value("Employee", r.get("approver"), "full_name")
			r["approver_name"] = app_name or r.get("approver")
		else:
			r["approver_name"] = "Pending Review"

	return records


@frappe.whitelist()
def get_leave_balance(employee=None, leave_type=None):
	"""
	Returns leave balance details (quota, consumed, pending, remaining)
	for an employee and leave type (or all leave types).
	"""
	user = _check_authenticated()
	app_role = _get_user_app_role(user)
	linked_emp = _get_linked_employee(user)

	emp_id = None
	if app_role == "Employee":
		if not linked_emp:
			return {}
		emp_id = linked_emp.get("name")
	else:
		emp_id = _resolve_employee_link(employee) or employee or (linked_emp.get("name") if linked_emp else None)

	if not emp_id:
		frappe.throw(_("Employee ID is required"))

	if leave_type:
		lt = _resolve_leave_type_link(leave_type) or leave_type
		return _calculate_employee_leave_balance(emp_id, lt)

	# Return for all active leave types
	all_types = frappe.get_all("Leave Type", fields=["name", "leave_type_name", "max_days_per_year"])
	balances = []
	for lt in all_types:
		b = _calculate_employee_leave_balance(emp_id, lt.name)
		balances.append(b)
	return balances


@frappe.whitelist()
def create_leave_application(data):
	user = _check_authenticated()
	app_role = _get_user_app_role(user)
	linked_emp = _get_linked_employee(user)

	if isinstance(data, str):
		data = frappe.parse_json(data)

	if app_role == "Employee":
		if not linked_emp:
			frappe.throw(_("No employee record linked to your user account."), frappe.PermissionError)
		data["employee"] = linked_emp.get("name")
		data["status"] = "Pending"
		if not data.get("approver") and linked_emp.get("reporting_manager"):
			data["approver"] = linked_emp.get("reporting_manager")
	elif app_role == "HR":
		target_emp = data.get("employee")
		resolved_emp = _resolve_employee_link(target_emp) if target_emp else None
		hr_name = linked_emp.get("name") if linked_emp else None
		hr_series = linked_emp.get("naming_series") if linked_emp else None

		if not target_emp or target_emp in [hr_name, hr_series] or resolved_emp in [hr_name, hr_series]:
			data["employee"] = hr_name
			data["status"] = "Pending"
			admin_emp = frappe.db.get_value("Employee", {"user_id": "Administrator"}, "name")
			if not admin_emp:
				admin_emp = frappe.db.get_value("Employee", {"email": "admin@ems.com"}, "name") or "EMP-001"
			data["approver"] = admin_emp
		else:
			data["employee"] = resolved_emp or target_emp
			if "approver" in data:
				data["approver"] = _resolve_employee_link(data.get("approver"))
	else:
		if "employee" in data:
			data["employee"] = _resolve_employee_link(data.get("employee")) or data.get("employee")
		if "approver" in data:
			data["approver"] = _resolve_employee_link(data.get("approver"))

		if app_role == "Administrator":
			target_emp = data.get("employee")
			if not target_emp:
				frappe.throw(_("Employee is required."))

			admin_emp_name = linked_emp.get("name") if linked_emp else None
			admin_emp_series = linked_emp.get("naming_series") if linked_emp else None

			is_own_leave = False
			if admin_emp_name and (target_emp == admin_emp_name or target_emp == admin_emp_series):
				is_own_leave = True
			elif target_emp == "EMP-001":
				is_own_leave = True
			else:
				emp_user = frappe.db.get_value("Employee", target_emp, "user_id")
				emp_email = frappe.db.get_value("Employee", target_emp, "email")
				if (emp_user and (emp_user == user or emp_user in ["Administrator", "admin@ems.com"])) or \
				   (emp_email and (emp_email == user or emp_email in ["admin@ems.com"])):
					is_own_leave = True

			if is_own_leave:
				frappe.throw(_("Administrators do not apply for leave. Your role is to monitor and review leave requests for employees and HR."), frappe.PermissionError)

	if "leave_type" in data:
		data["leave_type"] = _resolve_leave_type_link(data.get("leave_type")) or data.get("leave_type")

	if not data.get("from_date") or not data.get("to_date"):
		frappe.throw(_("From Date and To Date are required."))

	if not data.get("employee"):
		frappe.throw(_("Employee is required."))

	# 1. Overlapping Leave Validation
	_validate_leave_overlap(data["employee"], data["from_date"], data["to_date"])

	# 2. Leave Balance Validation
	if not data.get("total_days") and data.get("from_date") and data.get("to_date"):
		data["total_days"] = (getdate(data["to_date"]) - getdate(data["from_date"])).days + 1
	req_days = flt(data.get("total_days") or 1)
	bal = _calculate_employee_leave_balance(data["employee"], data["leave_type"])
	if req_days > bal["remaining_balance"]:
		frappe.throw(
			_("You have only {0} {1} days remaining. You cannot apply for {2} days.").format(
				bal["remaining_balance"], bal["leave_type_name"], req_days
			)
		)

	if "status" not in data or not data["status"]:
		data["status"] = "Pending"

	doc = frappe.get_doc({"doctype": "Leave Application", **data})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	res = doc.as_dict()
	if res.get("employee"):
		res["employee_name"] = frappe.db.get_value("Employee", res.get("employee"), "full_name") or res.get("employee")
	if res.get("leave_type"):
		lt_name = frappe.db.get_value("Leave Type", res.get("leave_type"), "leave_type_name")
		if lt_name:
			res["leave_type"] = lt_name
	return res


@frappe.whitelist()
def update_leave_status(name, status):
	user = _check_authenticated()
	app_role = _get_user_app_role(user)
	linked_emp = _get_linked_employee(user)

	if not frappe.db.exists("Leave Application", name):
		frappe.throw(_("Leave Application not found"))

	doc = frappe.get_doc("Leave Application", name)
	old_status = doc.status

	if app_role != "Administrator":
		if not linked_emp:
			frappe.throw(_("Not permitted to change leave status"), frappe.PermissionError)
		emp_name = linked_emp.get("name")
		emp_series = linked_emp.get("naming_series")
		emp_email = linked_emp.get("email")

		# 1. Any non-Administrator user (including HR Manager) CANNOT approve or reject their own leave application
		if doc.employee in [emp_name, emp_series] or (emp_email and doc.employee == emp_email):
			frappe.throw(
				_("You cannot approve or reject your own leave application. HR leave requests must be approved by the Administrator."),
				frappe.PermissionError,
			)

		# 2. Leave applications for HR staff MUST be approved by the Administrator
		if _is_hr_employee(doc.employee):
			frappe.throw(
				_("Leave applications for HR staff must be approved by the Administrator."),
				frappe.PermissionError,
			)

		# 3. For regular employees (not HR role), verify designated approver
		if app_role != "HR" and doc.approver != emp_name:
			frappe.throw(_("Not authorized to approve or reject this leave application"), frappe.PermissionError)

	if status == "Approved":
		# Validate remaining balance upon approval (excluding this application)
		bal = _calculate_employee_leave_balance(doc.employee, doc.leave_type, exclude_application=doc.name)
		if flt(doc.total_days) > bal["available_balance"]:
			frappe.throw(
				_("Cannot approve: Requested days ({0}) exceed remaining leave balance ({1}).").format(
					doc.total_days, bal["available_balance"]
				)
			)

		doc.status = "Approved"
		if linked_emp and not doc.approver:
			doc.approver = linked_emp.get("name")
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		# Immediate Attendance Auto Sync in transaction
		_sync_leave_to_attendance(doc)

		# Send In-App Notification
		emp_user = _get_user_for_employee(doc.employee)
		_create_in_app_notification(
			for_user=emp_user,
			title="Leave Application Approved",
			message=f"Your {doc.leave_type} application from {doc.from_date} to {doc.to_date} has been approved.",
			doc_type="Leave Application",
			doc_name=doc.name,
		)

	elif status == "Rejected":
		doc.status = "Rejected"
		if linked_emp and not doc.approver:
			doc.approver = linked_emp.get("name")
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		if old_status == "Approved":
			_revert_leave_attendance(doc)

		# Send In-App Notification
		emp_user = _get_user_for_employee(doc.employee)
		_create_in_app_notification(
			for_user=emp_user,
			title="Leave Application Rejected",
			message=f"Your {doc.leave_type} application from {doc.from_date} to {doc.to_date} has been rejected.",
			doc_type="Leave Application",
			doc_name=doc.name,
		)

	elif status == "Cancelled":
		return cancel_leave_application(name)
	else:
		doc.status = status
		doc.save(ignore_permissions=True)
		frappe.db.commit()

	res = doc.as_dict()
	res["employee_name"] = frappe.db.get_value("Employee", doc.employee, "full_name") or doc.employee
	return res


@frappe.whitelist()
def cancel_leave_application(name, reason=None):
	"""
	Leave Cancellation workflow:
	1. Employees can cancel Pending leave, or Approved leave before start date.
	2. HR/Admin can cancel anytime.
	3. Updates status to 'Cancelled'.
	4. Reverses all related attendance records back to their true underlying status.
	"""
	user = _check_authenticated()
	app_role = _get_user_app_role(user)
	linked_emp = _get_linked_employee(user)

	if not frappe.db.exists("Leave Application", name):
		frappe.throw(_("Leave Application not found"))

	doc = frappe.get_doc("Leave Application", name)

	if doc.status == "Cancelled":
		return doc.as_dict()

	today = getdate(nowdate())
	from_d = getdate(doc.from_date)

	if app_role == "Employee":
		if not linked_emp or doc.employee != linked_emp.get("name"):
			frappe.throw(_("Permission Denied: Cannot cancel another employee's leave"), frappe.PermissionError)
		if doc.status == "Rejected":
			frappe.throw(_("Cannot cancel a rejected leave application"))
		if doc.status == "Approved" and from_d <= today:
			frappe.throw(_("Cannot cancel approved leave that has already commenced or passed. Please contact HR."))

	old_status = doc.status
	doc.status = "Cancelled"
	doc.cancellation_reason = reason or "Cancelled by user"
	doc.cancelled_by = user
	doc.cancelled_at = now_datetime()
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	# Revert attendance if it was approved
	if old_status == "Approved":
		_revert_leave_attendance(doc)

	# Send in-app notification
	emp_user = _get_user_for_employee(doc.employee)
	_create_in_app_notification(
		for_user=emp_user,
		title="Leave Application Cancelled",
		message=f"Leave application {doc.name} ({doc.leave_type}) has been cancelled.",
		doc_type="Leave Application",
		doc_name=doc.name,
	)

	res = doc.as_dict()
	res["employee_name"] = frappe.db.get_value("Employee", doc.employee, "full_name") or doc.employee
	return res


@frappe.whitelist()
def update_leave_application(name, data):
	user = _check_authenticated()
	app_role = _get_user_app_role(user)
	linked_emp = _get_linked_employee(user)

	if not frappe.db.exists("Leave Application", name):
		frappe.throw(_("Leave Application not found"))

	doc = frappe.get_doc("Leave Application", name)

	if app_role == "Employee":
		if not linked_emp or doc.employee != linked_emp.get("name"):
			frappe.throw(_("Permission Denied: Cannot modify another employee's leave"), frappe.PermissionError)
		if doc.status != "Pending":
			frappe.throw(_("Cannot modify leave application once processed"), frappe.PermissionError)

	if isinstance(data, str):
		data = frappe.parse_json(data)

	if app_role == "Employee":
		data["employee"] = doc.employee
		data["status"] = "Pending"
	else:
		if "employee" in data:
			data["employee"] = _resolve_employee_link(data.get("employee")) or data.get("employee")
		if "approver" in data:
			data["approver"] = _resolve_employee_link(data.get("approver"))

	if "leave_type" in data:
		data["leave_type"] = _resolve_leave_type_link(data.get("leave_type")) or data.get("leave_type")

	from_d = data.get("from_date") or doc.from_date
	to_d = data.get("to_date") or doc.to_date
	emp_id = data.get("employee") or doc.employee
	lt_id = data.get("leave_type") or doc.leave_type

	# Validate overlap and balance
	_validate_leave_overlap(emp_id, from_d, to_d, exclude_application=doc.name)

	req_days = flt(data.get("total_days") or doc.total_days)
	bal = _calculate_employee_leave_balance(emp_id, lt_id, exclude_application=doc.name)
	if req_days > bal["remaining_balance"]:
		frappe.throw(
			_("You have only {0} {1} days remaining. You cannot apply for {2} days.").format(
				bal["remaining_balance"], bal["leave_type_name"], req_days
			)
		)

	doc.update(data)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def delete_leave_application(name):
	user = _check_authenticated()
	app_role = _get_user_app_role(user)
	linked_emp = _get_linked_employee(user)

	if not frappe.db.exists("Leave Application", name):
		return True

	doc = frappe.get_doc("Leave Application", name)

	if app_role == "Employee":
		if not linked_emp or doc.employee != linked_emp.get("name"):
			frappe.throw(_("Permission Denied: Cannot delete another employee's leave"), frappe.PermissionError)
		if doc.status not in ["Pending", "Cancelled"]:
			frappe.throw(_("Cannot delete leave application once it has been approved. Use Cancel instead."), frappe.PermissionError)

	if doc.status == "Approved":
		_revert_leave_attendance(doc)

	frappe.delete_doc("Leave Application", name, ignore_permissions=True, force=True)
	frappe.db.commit()
	return True


# ---------------- LEAVE TYPE ----------------
@frappe.whitelist()
def get_leave_types():
	if not frappe.db.exists("DocType", "Leave Type"):
		return []
	user = frappe.session.user
	if not user or user == "Guest":
		return []

	return frappe.get_all(
		"Leave Type",
		fields=["name", "leave_type_name", "max_days_per_year", "carry_forward"],
		order_by="modified desc",
	)


@frappe.whitelist()
def create_leave_type(data):
	_check_admin_or_hr()

	if isinstance(data, str):
		data = frappe.parse_json(data)

	name = data.get("leave_type_name")
	if not name:
		frappe.throw(_("Leave Type Name is required."))

	if frappe.db.exists("Leave Type", name):
		doc = frappe.get_doc("Leave Type", name)
		doc.update(data)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc({"doctype": "Leave Type", **data})
		doc.insert(ignore_permissions=True)

	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def update_leave_type(name, data):
	_check_admin_or_hr()

	if isinstance(data, str):
		data = frappe.parse_json(data)
	target = name or data.get("name") or data.get("leave_type_name")
	doc = frappe.get_doc("Leave Type", target)
	doc.update(data)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def delete_leave_type(name):
	_check_admin_or_hr()
	frappe.delete_doc("Leave Type", name, ignore_permissions=True, force=True)
	frappe.db.commit()
	return True


# ---------------- SALARY SLIP ----------------
@frappe.whitelist()
def get_salary_slips():
	if not frappe.db.exists("DocType", "Salary Slip"):
		return []

	user = frappe.session.user
	if not user or user == "Guest":
		return []

	app_role = _get_user_app_role(user)
	linked_emp = _get_linked_employee(user)

	filters = {}
	if app_role == "Employee":
		if not linked_emp:
			return []
		filters["employee"] = linked_emp.get("name")

	records = frappe.get_all(
		"Salary Slip",
		fields=[
			"name",
			"employee",
			"salary_month",
			"basic_pay",
			"hra",
			"gross_pay",
			"absent_days",
			"unpaid_leave_days",
			"lop_days",
			"lop_deduction",
			"leave_deduction",
			"net_pay",
			"select",
			"email_status",
			"email_sent_at",
		],
		filters=filters,
		order_by="modified desc",
	)

	for r in records:
		if r.get("employee"):
			emp_name = frappe.db.get_value("Employee", r.get("employee"), "full_name")
			r["employee_name"] = emp_name or r.get("employee")
		else:
			r["employee_name"] = "N/A"

		# Load child table rows
		try:
			allowances = frappe.get_all(
				"Salary Slip Allowance",
				filters={"parent": r.name},
				fields=["allowance_name", "amount"],
			)
			r["allowances"] = allowances or []
		except Exception:
			r["allowances"] = []

		try:
			deductions = frappe.get_all(
				"Salary Slip Deduction",
				filters={"parent": r.name},
				fields=["deduction_name", "amount"],
			)
			r["deductions"] = deductions or []
		except Exception:
			r["deductions"] = []

	return records


@frappe.whitelist()
def calculate_lop_for_employee_month(employee, salary_month):
	"""
	Automatically calculates unpaid leave days, absent days, and LOP deduction
	for an employee during a given salary month (YYYY-MM).
	Formula:
	Daily Salary = Basic Salary / Total Payable Days
	LOP Deduction = Daily Salary * LOP Days
	"""
	emp_id = _resolve_employee_link(employee) or employee
	month_str = str(salary_month).strip()
	parts = month_str.split("-")
	if len(parts) != 2:
		# Fallback to current year-month if invalid
		today = getdate(nowdate())
		year, month = today.year, today.month
	else:
		year, month = int(parts[0]), int(parts[1])

	_, days_in_month = calendar.monthrange(year, month)
	start_date = f"{year:04d}-{month:02d}-01"
	end_date = f"{year:04d}-{month:02d}-{days_in_month:02d}"

	# Fetch all attendance records in month
	records = frappe.get_all(
		"Attendance",
		filters={
			"employee": emp_id,
			"attendance_date": ["between", [start_date, end_date]],
		},
		fields=["name", "attendance_date", "status", "leave_type", "working_hours"],
	)

	absent_days = 0.0
	unpaid_leave_days = 0.0

	unpaid_type_names = {"loss of pay", "leave without pay", "unpaid leave", "lop", "lwp"}
	try:
		db_unpaid_types = frappe.get_all(
			"Leave Type",
			filters={"max_days_per_year": 0},
			fields=["name", "leave_type_name"],
		)
		for ut in db_unpaid_types:
			if ut.get("name"):
				unpaid_type_names.add(ut["name"].lower())
			if ut.get("leave_type_name"):
				unpaid_type_names.add(ut["leave_type_name"].lower())
	except Exception:
		pass

	for r in records:
		st = r.get("status")
		if st == "Absent":
			absent_days += 1.0
		elif st == "Half Day":
			absent_days += 0.5
		elif st == "On Leave":
			lt = (r.get("leave_type") or "").strip().lower()
			if lt in unpaid_type_names or any(w in lt for w in ["unpaid", "without pay", "loss of pay", "lop"]):
				unpaid_leave_days += 1.0

	lop_days = absent_days + unpaid_leave_days

	emp_basic = flt(frappe.db.get_value("Employee", emp_id, "basic_salary") or 0.0)
	if emp_basic > 150000:
		monthly_basic = round(emp_basic / 12.0, 2)
	else:
		monthly_basic = emp_basic

	daily_salary = round(monthly_basic / float(days_in_month), 2) if days_in_month > 0 else 0.0
	lop_deduction = round(daily_salary * lop_days, 2)

	return {
		"employee": emp_id,
		"salary_month": salary_month,
		"days_in_month": days_in_month,
		"total_payable_days": days_in_month,
		"absent_days": absent_days,
		"unpaid_leave_days": unpaid_leave_days,
		"lop_days": lop_days,
		"monthly_basic": monthly_basic,
		"daily_salary": daily_salary,
		"lop_deduction": lop_deduction,
	}


@frappe.whitelist()
def create_salary_slip(data):
	_check_admin_or_hr()

	if isinstance(data, str):
		data = frappe.parse_json(data)

	allowances_data = data.pop("allowances", [])
	deductions_data = data.pop("deductions", [])

	if "employee" in data:
		data["employee"] = _resolve_employee_link(data.get("employee")) or data.get("employee")

	# Enforce Idempotency: Prevent duplicate salary slips for same Employee + Month
	existing = frappe.db.get_value(
		"Salary Slip",
		{"employee": data["employee"], "salary_month": data["salary_month"]},
		"name",
	)
	if existing:
		frappe.throw(
			_("A Salary Slip ({0}) already exists for {1} in {2}. Use update or regenerate instead.").format(
				existing, data["employee"], data["salary_month"]
			)
		)

	# Auto calculate LOP if absent_days or lop_deduction not explicitly passed
	if "absent_days" not in data or "lop_deduction" not in data:
		lop_calc = calculate_lop_for_employee_month(data["employee"], data["salary_month"])
		data["absent_days"] = data.get("absent_days", lop_calc["absent_days"])
		data["unpaid_leave_days"] = data.get("unpaid_leave_days", lop_calc["unpaid_leave_days"])
		data["lop_days"] = data.get("lop_days", lop_calc["lop_days"])
		data["lop_deduction"] = flt(data.get("lop_deduction", lop_calc["lop_deduction"]))
		data["leave_deduction"] = flt(data.get("leave_deduction", data["lop_deduction"]))
	else:
		data["lop_deduction"] = flt(data.get("lop_deduction", 0))
		data["leave_deduction"] = flt(data.get("leave_deduction", data["lop_deduction"]))

	if "email_status" not in data:
		data["email_status"] = "Pending"

	doc = frappe.get_doc({"doctype": "Salary Slip", **data})

	for a in allowances_data:
		if a.get("allowance_name"):
			doc.append("allowances", {
				"allowance_name": a.get("allowance_name"),
				"amount": flt(a.get("amount")),
			})

	for d in deductions_data:
		if d.get("deduction_name"):
			doc.append("deductions", {
				"deduction_name": d.get("deduction_name"),
				"amount": flt(d.get("amount")),
			})

	sum_allowances = sum(flt(a.amount) for a in (doc.allowances or []))
	sum_deductions = sum(flt(d.amount) for d in (doc.deductions or []))
	doc.gross_pay = flt(doc.basic_pay) + flt(doc.hra) + sum_allowances
	doc.net_pay = max(0.0, round(doc.gross_pay - sum_deductions - flt(doc.leave_deduction), 2))

	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	res = doc.as_dict()
	res["employee_name"] = frappe.db.get_value("Employee", res.get("employee"), "full_name") or res.get("employee")
	return res


@frappe.whitelist()
def update_salary_slip(name, data):
	_check_admin_or_hr()

	if isinstance(data, str):
		data = frappe.parse_json(data)

	doc = frappe.get_doc("Salary Slip", name)

	allowances_data = data.pop("allowances", None)
	deductions_data = data.pop("deductions", None)

	if "employee" in data:
		data["employee"] = _resolve_employee_link(data.get("employee")) or data.get("employee")

	doc.update(data)

	if allowances_data is not None:
		doc.set("allowances", [])
		for a in allowances_data:
			if a.get("allowance_name"):
				doc.append("allowances", {
					"allowance_name": a.get("allowance_name"),
					"amount": flt(a.get("amount")),
				})

	if deductions_data is not None:
		doc.set("deductions", [])
		for d in deductions_data:
			if d.get("deduction_name"):
				doc.append("deductions", {
					"deduction_name": d.get("deduction_name"),
					"amount": flt(d.get("amount")),
				})

	sum_allowances = sum(flt(a.amount) for a in (doc.allowances or []))
	sum_deductions = sum(flt(d.amount) for d in (doc.deductions or []))
	doc.gross_pay = flt(doc.basic_pay) + flt(doc.hra) + sum_allowances
	doc.net_pay = max(0.0, round(doc.gross_pay - sum_deductions - flt(doc.leave_deduction or doc.lop_deduction), 2))

	doc.save(ignore_permissions=True)
	frappe.db.commit()

	res = doc.as_dict()
	res["employee_name"] = frappe.db.get_value("Employee", res.get("employee"), "full_name") or res.get("employee")
	return res


@frappe.whitelist()
def delete_salary_slip(name):
	_check_admin_or_hr()
	frappe.delete_doc("Salary Slip", name, ignore_permissions=True, force=True)
	frappe.db.commit()
	return True


def _generate_salary_slip_html(doc, emp):
	"""Builds the responsive HTML template for a Salary Slip PDF."""
	allowances_list = doc.get("allowances") or []
	deductions_list = doc.get("deductions") or []

	allowances_rows = "".join(
		f"<tr><td style='padding:8px;border-bottom:1px solid #e2e8f0;'>{a.allowance_name}</td>"
		f"<td style='padding:8px;border-bottom:1px solid #e2e8f0;text-align:right;'>${flt(a.amount):,.2f}</td></tr>"
		for a in allowances_list
	)

	deductions_rows = "".join(
		f"<tr><td style='padding:8px;border-bottom:1px solid #e2e8f0;'>{d.deduction_name}</td>"
		f"<td style='padding:8px;border-bottom:1px solid #e2e8f0;text-align:right;'>${flt(d.amount):,.2f}</td></tr>"
		for d in deductions_list
	)

	lop_amt = flt(doc.lop_deduction or doc.leave_deduction)
	if lop_amt > 0:
		deductions_rows += (
			f"<tr><td style='padding:8px;border-bottom:1px solid #e2e8f0;color:#e11d48;font-weight:600;'>"
			f"Loss of Pay (LOP) ({flt(doc.lop_days)} days)</td>"
			f"<td style='padding:8px;border-bottom:1px solid #e2e8f0;text-align:right;color:#e11d48;font-weight:600;'>${lop_amt:,.2f}</td></tr>"
		)

	return f"""
	<!DOCTYPE html>
	<html>
	<head>
		<meta charset="utf-8">
		<title>Salary Slip - {doc.name}</title>
		<style>
			body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #1e293b; margin: 0; padding: 24px; font-size: 13px; line-height: 1.5; }}
			.header {{ border-bottom: 2px solid #4f46e5; padding-bottom: 16px; margin-bottom: 20px; }}
			.company-name {{ font-size: 22px; font-weight: bold; color: #4f46e5; letter-spacing: -0.5px; }}
			.slip-title {{ font-size: 16px; font-weight: 600; color: #0f172a; margin-top: 4px; }}
			.info-grid {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; background: #f8fafc; border-radius: 8px; }}
			.info-grid td {{ padding: 8px 12px; font-size: 12px; }}
			.label {{ font-weight: bold; color: #64748b; width: 22%; }}
			.val {{ color: #0f172a; font-weight: 500; }}
			.tables-container {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
			.table-box {{ width: 48%; vertical-align: top; }}
			.fin-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
			.fin-table th {{ background: #f1f5f9; padding: 8px; text-align: left; font-weight: bold; color: #475569; border-bottom: 2px solid #cbd5e1; }}
			.total-row td {{ font-weight: bold; padding: 10px 8px; border-top: 2px solid #cbd5e1; }}
			.net-pay-banner {{ background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 16px; text-align: center; margin-top: 20px; }}
			.net-pay-amount {{ font-size: 24px; font-weight: 800; color: #1d4ed8; margin: 6px 0; }}
			.footer {{ margin-top: 30px; border-top: 1px solid #e2e8f0; padding-top: 12px; font-size: 11px; color: #94a3b8; text-align: center; }}
		</style>
	</head>
	<body>
		<div class="header">
			<table style="width: 100%;">
				<tr>
					<td>
						<div class="company-name">Techunison Software Solutions</div>
						<div class="slip-title">Monthly Paystub / Salary Statement</div>
					</td>
					<td style="text-align: right;">
						<div style="font-size: 12px; color: #64748b;">Pay Period: <strong>{doc.salary_month}</strong></div>
						<div style="font-size: 12px; color: #64748b;">Document ID: <strong>{doc.name}</strong></div>
						<div style="font-size: 11px; color: #94a3b8;">Issued: {now_datetime().strftime('%d %b %Y')}</div>
					</td>
				</tr>
			</table>
		</div>

		<table class="info-grid">
			<tr>
				<td class="label">Employee Name:</td>
				<td class="val">{emp.full_name}</td>
				<td class="label">Employee ID:</td>
				<td class="val">{emp.name}</td>
			</tr>
			<tr>
				<td class="label">Department:</td>
				<td class="val">{emp.department or 'General'}</td>
				<td class="label">Designation:</td>
				<td class="val">{emp.designation or 'Associate'}</td>
			</tr>
			<tr>
				<td class="label">Date of Joining:</td>
				<td class="val">{emp.date_of_joining or 'N/A'}</td>
				<td class="label">Status:</td>
				<td class="val"><strong>{doc.select or 'Draft'}</strong></td>
			</tr>
			<tr>
				<td class="label">Absent Days:</td>
				<td class="val">{flt(doc.absent_days)}</td>
				<td class="label">LOP Days:</td>
				<td class="val" style="color: {'#e11d48' if flt(doc.lop_days) > 0 else '#0f172a'}; font-weight: bold;">{flt(doc.lop_days)}</td>
			</tr>
		</table>

		<table class="tables-container">
			<tr>
				<td class="table-box" style="padding-right: 12px;">
					<table class="fin-table">
						<thead>
							<tr>
								<th>Earnings & Allowances</th>
								<th style="text-align: right;">Amount</th>
							</tr>
						</thead>
						<tbody>
							<tr>
								<td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">Basic Pay</td>
								<td style="padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: right;">${flt(doc.basic_pay):,.2f}</td>
							</tr>
							<tr>
								<td style="padding: 8px; border-bottom: 1px solid #e2e8f0;">House Rent Allowance (HRA)</td>
								<td style="padding: 8px; border-bottom: 1px solid #e2e8f0; text-align: right;">${flt(doc.hra):,.2f}</td>
							</tr>
							{allowances_rows}
							<tr class="total-row">
								<td>Gross Earnings:</td>
								<td style="text-align: right; color: #16a34a;">${flt(doc.gross_pay):,.2f}</td>
							</tr>
						</tbody>
					</table>
				</td>
				<td class="table-box" style="padding-left: 12px;">
					<table class="fin-table">
						<thead>
							<tr>
								<th>Deductions</th>
								<th style="text-align: right;">Amount</th>
							</tr>
						</thead>
						<tbody>
							{deductions_rows or "<tr><td colspan='2' style='padding:8px;color:#94a3b8;'>No standard deductions</td></tr>"}
							<tr class="total-row">
								<td>Total Deductions:</td>
								<td style="text-align: right; color: #dc2626;">${(flt(doc.gross_pay) - flt(doc.net_pay)):,.2f}</td>
							</tr>
						</tbody>
					</table>
				</td>
			</tr>
		</table>

		<div class="net-pay-banner">
			<div style="font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; color: #475569;">Net Take-Home Pay</div>
			<div class="net-pay-amount">${flt(doc.net_pay):,.2f}</div>
			<div style="font-size: 11px; color: #64748b;">Direct Bank Transfer / Disbursed via Corporate Account</div>
		</div>

		<div class="footer">
			Confidential document for {emp.full_name}. Techunison Software Solutions.
		</div>
	</body>
	</html>
	"""


@frappe.whitelist()
def download_salary_slip_pdf(name):
	"""
	Generates and downloads an employee's salary slip as a PDF document.
	"""
	_check_authenticated()
	user = frappe.session.user
	app_role = _get_user_app_role(user)
	linked_emp = _get_linked_employee(user)

	if not frappe.db.exists("Salary Slip", name):
		frappe.throw(_("Salary Slip not found"))

	doc = frappe.get_doc("Salary Slip", name)

	if app_role == "Employee":
		if not linked_emp or doc.employee != linked_emp.get("name"):
			frappe.throw(_("Permission Denied: Cannot access another employee's salary slip"), frappe.PermissionError)

	emp = frappe.get_doc("Employee", doc.employee)
	from frappe.utils.pdf import get_pdf

	html = _generate_salary_slip_html(doc, emp)
	pdf_content = get_pdf(html)

	frappe.response['filename'] = f"Salary_Slip_{doc.employee}_{doc.salary_month}.pdf"
	frappe.response['filecontent'] = pdf_content
	frappe.response['type'] = 'pdf'


@frappe.whitelist()
def send_salary_slip_email(name):
	"""
	Emails the salary slip PDF to the employee.
	Tracks email delivery status in email_status ('Pending', 'Sent', 'Failed').
	"""
	_check_admin_or_hr()
	if not frappe.db.exists("Salary Slip", name):
		frappe.throw(_("Salary Slip not found"))

	doc = frappe.get_doc("Salary Slip", name)
	emp = frappe.get_doc("Employee", doc.employee)
	recipient_email = emp.email or (frappe.db.get_value("User", emp.user_id, "email") if emp.user_id else None)

	if not recipient_email:
		doc.email_status = "Failed"
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		frappe.throw(_("Employee has no valid email address configured."))

	try:
		from frappe.utils.pdf import get_pdf
		html = _generate_salary_slip_html(doc, emp)
		pdf_bytes = get_pdf(html)

		frappe.sendmail(
			recipients=[recipient_email],
			subject=f"Your Salary Slip for {doc.salary_month} - Techunison",
			message=f"""
			<p>Dear {emp.full_name},</p>
			<p>Please find attached your official salary statement for <strong>{doc.salary_month}</strong>.</p>
			<p><strong>Gross Earnings:</strong> ${flt(doc.gross_pay):,.2f}<br>
			<strong>Net Pay:</strong> ${flt(doc.net_pay):,.2f}</p>
			<p>For any payroll inquiries, please contact Human Resources.</p>
			<p>Best regards,<br>Techunison HR & Payroll Operations</p>
			""",
			attachments=[{
				"fname": f"Salary_Slip_{doc.salary_month}.pdf",
				"fcontent": pdf_bytes,
			}],
			now=True,
		)

		doc.email_status = "Sent"
		doc.email_sent_at = now_datetime()
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		_create_in_app_notification(
			for_user=_get_user_for_employee(emp.name),
			title="Salary Slip Emailed",
			message=f"Your salary slip for {doc.salary_month} has been sent to {recipient_email}.",
			doc_type="Salary Slip",
			doc_name=doc.name,
		)

		return {
			"message": f"Salary slip successfully emailed to {recipient_email}",
			"email_status": "Sent",
			"email_sent_at": str(doc.email_sent_at),
		}

	except Exception as e:
		doc.email_status = "Failed"
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		frappe.throw(_("Failed to email salary slip: {0}").format(str(e)))


@frappe.whitelist()
def send_batch_salary_slip_emails(salary_month=None, department=None, retry_failed_only=False):
	"""
	Sends salary slip emails in batch for a given month and optional department.
	Allows retrying failed emails.
	"""
	_check_admin_or_hr()
	if isinstance(retry_failed_only, str):
		retry_failed_only = retry_failed_only.lower() in ["true", "1", "yes"]

	filters = {}
	if salary_month:
		filters["salary_month"] = salary_month
	if retry_failed_only:
		filters["email_status"] = "Failed"

	slips = frappe.get_all("Salary Slip", filters=filters, fields=["name", "employee"])

	sent_count = 0
	failed_count = 0

	for s in slips:
		if department and department != "All Departments":
			emp_dept = frappe.db.get_value("Employee", s["employee"], "department")
			if emp_dept != department:
				continue
		try:
			send_salary_slip_email(s["name"])
			sent_count += 1
		except Exception:
			failed_count += 1

	return {
		"message": f"Batch email dispatch completed: {sent_count} sent, {failed_count} failed.",
		"sent_count": sent_count,
		"failed_count": failed_count,
	}


@frappe.whitelist()
def generate_batch_payroll(salary_month, department=None, designation=None, location=None, employee=None, regenerate=False):
	"""
	Generates salary slips in batch for all active employees matching filters.
	- Automatically calculates absent days, unpaid leave days, and LOP deduction.
	- Strictly idempotent: skips existing salary slips unless regenerate=True.
	- Tracks batch status and financial summary in a Payroll document.
	- Emits an in-app notification upon completion.
	"""
	_check_admin_or_hr()
	if isinstance(regenerate, str):
		regenerate = regenerate.lower() in ["true", "1", "yes"]

	month_str = str(salary_month).strip()
	parts = month_str.split("-")
	if len(parts) != 2:
		frappe.throw(_("Invalid salary month format. Expected YYYY-MM."))
	year, month = int(parts[0]), int(parts[1])
	_, days_in_month = calendar.monthrange(year, month)
	start_date = f"{year:04d}-{month:02d}-01"
	end_date = f"{year:04d}-{month:02d}-{days_in_month:02d}"

	filters = {"status": "Active"}
	if employee:
		resolved_emp = _resolve_employee_link(employee) or employee
		filters["name"] = resolved_emp
	if department and department not in ("All Departments", "All"):
		filters["department"] = department
	if designation and designation not in ("All Designations", "All"):
		filters["designation"] = designation

	employees = frappe.get_all(
		"Employee",
		filters=filters,
		fields=["name", "full_name", "department", "designation", "basic_salary", "user_id"],
	)

	payroll_title = f"Payroll {month_str}" + (f" - {department}" if department and department != "All Departments" else "")
	payroll_doc = frappe.get_doc({
		"doctype": "Payroll",
		"payroll_title": payroll_title,
		"salary_month": month_str,
		"start_date": start_date,
		"end_date": end_date,
		"department": department or "All",
		"designation": designation or "All",
		"total_employees": len(employees),
		"successful_slips": 0,
		"failed_slips": 0,
		"total_amount": 0.0,
		"status": "Processing",
	})
	payroll_doc.insert(ignore_permissions=True)
	frappe.db.commit()

	processed = 0
	skipped = 0
	failed = 0
	total_net = 0.0
	failures = []

	for emp in employees:
		emp_id = emp.name
		existing_slip = frappe.db.get_value(
			"Salary Slip",
			{"employee": emp_id, "salary_month": month_str},
			["name", "net_pay"],
			as_dict=True,
		)
		if existing_slip and not regenerate:
			skipped += 1
			total_net += flt(existing_slip.net_pay)
			continue

		try:
			lop_data = calculate_lop_for_employee_month(emp_id, month_str)
			basic_pay = lop_data["monthly_basic"]
			hra = round(basic_pay * 0.4, 2)
			lop_deduction = lop_data["lop_deduction"]
			gross = basic_pay + hra
			net = max(0.0, round(gross - lop_deduction, 2))

			if existing_slip and regenerate:
				sdoc = frappe.get_doc("Salary Slip", existing_slip.name)
				sdoc.basic_pay = basic_pay
				sdoc.hra = hra
				sdoc.absent_days = lop_data["absent_days"]
				sdoc.unpaid_leave_days = lop_data["unpaid_leave_days"]
				sdoc.lop_days = lop_data["lop_days"]
				sdoc.lop_deduction = lop_deduction
				sdoc.leave_deduction = lop_deduction
				sdoc.gross_pay = gross
				sdoc.net_pay = net
				sdoc.save(ignore_permissions=True)
			else:
				sdoc = frappe.get_doc({
					"doctype": "Salary Slip",
					"employee": emp_id,
					"salary_month": month_str,
					"basic_pay": basic_pay,
					"hra": hra,
					"gross_pay": gross,
					"net_pay": net,
					"absent_days": lop_data["absent_days"],
					"unpaid_leave_days": lop_data["unpaid_leave_days"],
					"lop_days": lop_data["lop_days"],
					"lop_deduction": lop_deduction,
					"leave_deduction": lop_deduction,
					"select": "Draft",
					"email_status": "Pending",
				})
				sdoc.insert(ignore_permissions=True)

			processed += 1
			total_net += net
		except Exception as e:
			failed += 1
			failures.append(f"{emp_id} ({emp.full_name}): {str(e)}")

	frappe.db.commit()

	payroll_doc.successful_slips = processed + skipped
	payroll_doc.failed_slips = failed
	payroll_doc.total_amount = round(total_net, 2)
	payroll_doc.status = "Completed" if failed == 0 else ("Completed with Errors" if processed > 0 else "Failed")
	if failures:
		payroll_doc.failure_details = "\n".join(failures)
	payroll_doc.save(ignore_permissions=True)
	frappe.db.commit()

	_create_in_app_notification(
		for_user=frappe.session.user,
		title=f"Batch Payroll: {month_str}",
		message=f"Payroll generated for {processed} employees ({skipped} skipped, {failed} failed). Total: ${total_net:,.2f}",
		doc_type="Payroll",
		doc_name=payroll_doc.name,
	)

	return {
		"payroll_id": payroll_doc.name,
		"salary_month": month_str,
		"total_employees": len(employees),
		"processed_slips": processed,
		"skipped_slips": skipped,
		"failed_slips": failed,
		"total_amount": round(total_net, 2),
		"status": payroll_doc.status,
	}


@frappe.whitelist()
def get_payroll_runs():
	"""Returns history of batch payroll processing runs."""
	_check_admin_or_hr()
	if not frappe.db.exists("DocType", "Payroll"):
		return []
	return frappe.get_all(
		"Payroll",
		fields=["name", "payroll_title", "salary_month", "start_date", "end_date", "department", "designation", "total_employees", "successful_slips", "failed_slips", "total_amount", "status", "creation"],
		order_by="creation desc",
		limit=50,
	)


# ---------------- HR DOCUMENTS ----------------
@frappe.whitelist()
def get_hr_documents():
	if not frappe.db.exists("DocType", "HR Document"):
		return []

	user = frappe.session.user
	if not user or user == "Guest":
		return []

	app_role = _get_user_app_role(user)

	if app_role == "Employee":
		records = frappe.get_all(
			"HR Document",
			fields=["name", "title", "category", "access_role", "file", "content", "modified"],
			filters=[["HR Document", "access_role", "in", ["All", "Employee", "General"]]],
			order_by="modified desc",
		)
	else:
		records = frappe.get_all(
			"HR Document",
			fields=["name", "title", "category", "access_role", "file", "content", "modified"],
			order_by="modified desc",
		)

	return records


@frappe.whitelist()
def create_hr_document(data):
	_check_admin_or_hr()

	if isinstance(data, str):
		data = frappe.parse_json(data)

	if not data.get("title"):
		frappe.throw(_("Title is required"))

	doc = frappe.get_doc({"doctype": "HR Document", **data})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def update_hr_document(name, data):
	_check_admin_or_hr()

	if isinstance(data, str):
		data = frappe.parse_json(data)

	doc = frappe.get_doc("HR Document", name)
	doc.update(data)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def delete_hr_document(name):
	_check_admin_or_hr()
	frappe.delete_doc("HR Document", name, ignore_permissions=True, force=True)
	frappe.db.commit()
	return True


# ---------------- ATTENDANCE & SHIFT AUTOMATION ----------------
@frappe.whitelist()
def get_attendance(employee=None, from_date=None, to_date=None):
	"""
	Retrieves Attendance records with employee-scoping for Employee role,
	and optional date/employee filtering for Admin/HR.
	Formats check_in and check_out for React UI compatibility.
	"""
	if not frappe.db.exists("DocType", "Attendance"):
		return []

	user = _check_authenticated()
	app_role = _get_user_app_role(user)
	linked_emp = _get_linked_employee(user)

	filters = {}
	if app_role == "Employee":
		if not linked_emp:
			return []
		filters["employee"] = linked_emp.get("name")
	elif employee:
		filters["employee"] = employee

	if from_date and to_date:
		filters["attendance_date"] = ["between", [from_date, to_date]]
	elif from_date:
		filters["attendance_date"] = [">=", from_date]
	elif to_date:
		filters["attendance_date"] = ["<=", to_date]

	try:
		records = frappe.get_all(
			"Attendance",
			fields=[
				"name",
				"employee",
				"employee_name",
				"attendance_date",
				"status",
				"shift",
				"office_location",
				"in_time",
				"out_time",
				"working_hours",
				"late_entry",
				"early_exit",
				"auto_clocked_out",
				"clock_out_reason",
				"auto_clock_out_time",
				"leave_type",
				"leave_application",
				"remarks",
				"creation",
				"modified",
			],
			filters=filters,
			order_by="attendance_date desc, modified desc",
		)
		# Enrich records with formatted check_in / check_out strings for UI
		from frappe.utils import get_datetime
		for r in records:
			if r.get("in_time"):
				t_in = get_datetime(r["in_time"])
				r["check_in"] = t_in.strftime("%I:%M %p")
			else:
				r["check_in"] = "-"
			if r.get("out_time"):
				t_out = get_datetime(r["out_time"])
				r["check_out"] = t_out.strftime("%I:%M %p")
			else:
				r["check_out"] = "-"
		return records
	except Exception:
		return []


@frappe.whitelist()
def create_attendance(data=None):
	_check_admin_or_hr()

	if isinstance(data, str):
		data = frappe.parse_json(data)
	if not data or not frappe.db.exists("DocType", "Attendance"):
		return None
	try:
		doc = frappe.get_doc({"doctype": "Attendance", **data})
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return doc.as_dict()
	except Exception as e:
		frappe.throw(_("Error creating attendance: {0}").format(str(e)))


@frappe.whitelist()
def update_attendance(name, data=None):
	_check_admin_or_hr()
	if isinstance(data, str):
		data = frappe.parse_json(data)
	if not name or not data:
		return None
	try:
		doc = frappe.get_doc("Attendance", name)
		doc.update(data)
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		return doc.as_dict()
	except Exception as e:
		frappe.throw(_("Error updating attendance: {0}").format(str(e)))


@frappe.whitelist()
def delete_attendance(name):
	_check_admin_or_hr()
	if not name:
		return False
	try:
		frappe.delete_doc("Attendance", name, ignore_permissions=True)
		frappe.db.commit()
		return True
	except Exception:
		return False


@frappe.whitelist()
def employee_checkin(employee=None, timestamp=None, log_type="IN", device_id=None):
	"""
	Records an employee check-in or check-out event.
	Automatically resolves employee from session user for Employee role.
	"""
	user = _check_authenticated()
	app_role = _get_user_app_role(user)
	linked_emp = _get_linked_employee(user)

	if app_role == "Administrator" and not employee:
		frappe.throw(frappe._("Administrators do not clock in or clock out. Your role is to monitor attendance for HR and Employees."), frappe.PermissionError)

	if app_role == "Employee" or not employee:
		if not linked_emp:
			frappe.throw(frappe._("No Employee record linked to your user account."))
		emp_id = linked_emp.get("name")
	else:
		emp_id = employee

	log_type = (log_type or "IN").strip().upper()
	if log_type not in ("IN", "OUT"):
		log_type = "IN"

	from frappe.utils import get_datetime
	t = get_datetime(timestamp) if timestamp else now_datetime()
	emp_name = frappe.db.get_value("Employee", emp_id, "full_name") or emp_id

	# Sequence validation
	from employee_management_system.employee_management_system.attendance.checkin_service import (
		validate_checkin_sequence,
	)
	validate_checkin_sequence(emp_id, log_type)

	# Resolve office location
	office_location = frappe.db.get_value("Employee", emp_id, "office_location")
	if not office_location:
		active_offices = frappe.get_all("Office Location", filters={"is_active": 1}, limit=1)
		if active_offices:
			office_location = active_offices[0].name

	# Attempt to resolve current active shift
	from employee_management_system.employee_management_system.shift_attendance import (
		get_active_shift_assignments,
		get_shift_window,
		process_attendance_for_employee_shift,
		resolve_employee_shift_type,
	)

	shift_name = resolve_employee_shift_type(emp_id, t.date())
	shift_start = None
	shift_end = None
	if shift_name and frappe.db.exists("Shift Type", shift_name):
		sdoc = frappe.get_doc("Shift Type", shift_name)
		s_start, s_end, *rest = get_shift_window(sdoc, t.date())
		shift_start = s_start
		shift_end = s_end

	checkin_doc = frappe.get_doc({
		"doctype": "Employee Checkin",
		"employee": emp_id,
		"employee_name": emp_name,
		"time": t,
		"log_type": log_type,
		"shift": shift_name,
		"shift_start": shift_start,
		"shift_end": shift_end,
		"device_id": device_id or "Web App",
		"attendance_source": "Web App",
		"office_location": office_location,
	})
	checkin_doc.insert(ignore_permissions=True)
	frappe.db.commit()

	if shift_name:
		try:
			process_attendance_for_employee_shift(
				employee=emp_id,
				shift_type_name=shift_name,
				attendance_date=t.date(),
			)
			frappe.db.commit()
		except Exception as e:
			frappe.logger().error(f"Error recalculating attendance in employee_checkin for {emp_id}: {e}")

	return checkin_doc.as_dict()


@frappe.whitelist()
def employee_checkout(employee=None, timestamp=None, device_id=None):
	"""Convenience wrapper for employee OUT check-in."""
	return employee_checkin(employee=employee, timestamp=timestamp, log_type="OUT", device_id=device_id)


@frappe.whitelist()
def clock_in(latitude=None, longitude=None, accuracy=None):
	"""
	Secure GPS Clock IN endpoint for the authenticated employee.
	Requires latitude, longitude, and accuracy.
	Validates GPS coordinates, accuracy threshold, and office radius on server.
	Identifies employee strictly via frappe.session.user.
	Prevents duplicate Clock IN.
	"""
	user = _check_authenticated()
	if user == "Administrator" or _get_user_app_role(user) == "Administrator":
		frappe.throw(
			_("Administrators do not clock in or clock out. Your role is to monitor attendance for HR and Employees."),
			frappe.PermissionError,
		)
	from employee_management_system.employee_management_system.attendance.checkin_service import record_gps_checkin
	return record_gps_checkin(
		log_type="IN",
		latitude=latitude,
		longitude=longitude,
		accuracy=accuracy,
	)


@frappe.whitelist()
def clock_out(latitude=None, longitude=None, accuracy=None):
	"""
	Secure GPS Clock OUT endpoint for the authenticated employee.
	Requires latitude, longitude, and accuracy.
	Validates GPS coordinates, accuracy threshold, and office radius on server.
	Identifies employee strictly via frappe.session.user.
	Prevents Clock OUT without an active Clock IN.
	"""
	user = _check_authenticated()
	if user == "Administrator" or _get_user_app_role(user) == "Administrator":
		frappe.throw(
			_("Administrators do not clock in or clock out. Your role is to monitor attendance for HR and Employees."),
			frappe.PermissionError,
		)
	from employee_management_system.employee_management_system.attendance.checkin_service import record_gps_checkin
	return record_gps_checkin(
		log_type="OUT",
		latitude=latitude,
		longitude=longitude,
		accuracy=accuracy,
	)


@frappe.whitelist()
def ping_location(latitude=None, longitude=None, accuracy=None):
	"""
	Location-based automatic clock-out heartbeat endpoint.
	Receives GPS coordinates from the employee client while clocked in.
	If employee has moved outside permitted office geofence during work hours,
	automatically clocks them out with reason 'Left Office Location' and sends notifications.
	"""
	user = _check_authenticated()
	if user == "Administrator" or _get_user_app_role(user) == "Administrator":
		return {"exempt": True}
	from employee_management_system.employee_management_system.attendance.checkin_service import (
		get_authenticated_employee,
	)
	from employee_management_system.employee_management_system.attendance.auto_clock_out_service import (
		check_location_auto_clock_out,
		check_shift_completion_auto_clock_out,
	)

	emp = get_authenticated_employee()

	# Check shift completion auto clock-out first
	shift_outs = check_shift_completion_auto_clock_out(employee_id=emp.name)
	if shift_outs:
		return {
			"action": "auto_clocked_out",
			"auto_clocked_out": True,
			"reason": "Shift Completed",
			"clock_out_time": str(shift_outs[0].get("clock_out_time")),
			"details": shift_outs[0],
			"message": "Scheduled shift completed. You have been automatically clocked out.",
		}

	return check_location_auto_clock_out(
		employee_id=emp.name,
		latitude=latitude,
		longitude=longitude,
		accuracy=accuracy,
	)


@frappe.whitelist()
def trigger_shift_completion_clockout():
	"""
	Admin / HR on-demand trigger to run shift completion automatic clock-out.
	Clocks out any currently clocked-in employees whose scheduled shift has completed.
	"""
	_check_admin_or_hr()
	from employee_management_system.employee_management_system.attendance.auto_clock_out_service import (
		check_shift_completion_auto_clock_out,
	)

	results = check_shift_completion_auto_clock_out()
	return {
		"message": f"Processed shift completion auto clock-out for {len(results)} employees.",
		"count": len(results),
		"results": results,
	}


@frappe.whitelist()
def get_auto_clockout_logs(employee=None, from_date=None, to_date=None):
	"""
	Retrieves audit history of automatic clock-outs.
	Role-scoped: Employees see self; Admin/HR see all.
	"""
	user = _check_authenticated()
	app_role = _get_user_app_role(user)
	linked_emp = _get_linked_employee(user)

	filters = {"is_auto_clock_out": 1, "log_type": "OUT"}
	if app_role == "Employee":
		if not linked_emp:
			return []
		filters["employee"] = linked_emp.get("name")
	elif employee:
		filters["employee"] = employee

	if from_date and to_date:
		filters["time"] = ["between", [f"{from_date} 00:00:00", f"{to_date} 23:59:59"]]
	elif from_date:
		filters["time"] = [">=", f"{from_date} 00:00:00"]
	elif to_date:
		filters["time"] = ["<=", f"{to_date} 23:59:59"]

	return frappe.get_all(
		"Employee Checkin",
		filters=filters,
		fields=[
			"name",
			"employee",
			"employee_name",
			"time",
			"clock_out_reason",
			"distance_from_office",
			"office_location",
			"attendance",
		],
		order_by="time desc",
	)


@frappe.whitelist()
def get_my_attendance_status():
	"""
	Returns the real-time clocking status for the authenticated employee.
	Includes whether currently clocked in, working duration, assigned office, and today's shift.
	"""
	user = _check_authenticated()
	if user == "Administrator" or _get_user_app_role(user) == "Administrator":
		return {
			"is_administrator": True,
			"exempt": True,
			"is_clocked_in": False,
			"current_status": "Exempt",
			"message": "Administrators do not clock in or clock out. Your role is to monitor attendance for HR and Employees.",
		}
	from employee_management_system.employee_management_system.attendance.checkin_service import (
		get_employee_attendance_status,
		get_authenticated_employee,
	)
	emp = get_authenticated_employee()
	return get_employee_attendance_status(employee_id=emp.name)


@frappe.whitelist()
def get_my_attendance(from_date=None, to_date=None):
	"""
	Returns attendance records for the authenticated employee within an optional date range.
	"""
	_check_authenticated()
	from employee_management_system.employee_management_system.attendance.checkin_service import get_authenticated_employee
	emp = get_authenticated_employee()
	return get_attendance(employee=emp.name, from_date=from_date, to_date=to_date)


@frappe.whitelist()
def get_office_locations():
	"""
	Returns all active configured Office Locations.
	"""
	_check_authenticated()
	if not frappe.db.exists("DocType", "Office Location"):
		return []
	return frappe.get_all(
		"Office Location",
		filters={"is_active": 1},
		fields=["name", "office_name", "latitude", "longitude", "allowed_radius", "max_accuracy", "address"],
		order_by="office_name asc",
	)


@frappe.whitelist()
def recalculate_attendance(attendance_date=None, shift_type=None, employee=None):
	"""
	Manual trigger endpoint for Admin / HR to calculate or recalculate attendance
	for a specific date, shift type, or employee.
	"""
	_check_admin_or_hr()
	from frappe.utils import nowdate
	from employee_management_system.employee_management_system.attendance.auto_clock_out_service import (
		check_shift_completion_auto_clock_out,
	)
	from employee_management_system.employee_management_system.shift_attendance import (
		process_auto_attendance_for_date,
	)

	target = attendance_date or nowdate()
	try:
		check_shift_completion_auto_clock_out(target_date=target, employee_id=employee)
	except Exception as e:
		frappe.logger().error(f"Error checking shift completion during recalculate_attendance: {e}")

	results = process_auto_attendance_for_date(
		target_date=target,
		shift_type_name=shift_type,
		employee=employee,
	)
	return {
		"message": f"Successfully processed attendance for {len(results)} assignments on {target}",
		"count": len(results),
		"results": results,
	}


@frappe.whitelist()
def get_shift_types():
	"""Returns all configured Shift Types."""
	_check_authenticated()
	if not frappe.db.exists("DocType", "Shift Type"):
		return []
	return frappe.get_all("Shift Type", fields=["*"], order_by="shift_name asc")


@frappe.whitelist()
def get_shift_assignments(employee=None):
	"""Returns Shift Assignments with role-based scoping."""
	user = _check_authenticated()
	app_role = _get_user_app_role(user)
	linked_emp = _get_linked_employee(user)

	filters = {}
	if app_role == "Employee":
		if not linked_emp:
			return []
		filters["employee"] = linked_emp.get("name")
	elif employee:
		filters["employee"] = employee

	if not frappe.db.exists("DocType", "Shift Assignment"):
		return []

	return frappe.get_all("Shift Assignment", fields=["*"], filters=filters, order_by="start_date desc")


@frappe.whitelist()
def create_shift_type(data):
	"""Creates a new Shift Type."""
	_check_admin_or_hr()
	if isinstance(data, str):
		data = frappe.parse_json(data)

	if not data.get("shift_name"):
		frappe.throw(_("Shift Name is required"))

	doc = frappe.get_doc({"doctype": "Shift Type", **data})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def update_shift_type(name, data):
	"""Updates an existing Shift Type."""
	_check_admin_or_hr()
	if isinstance(data, str):
		data = frappe.parse_json(data)

	doc = frappe.get_doc("Shift Type", name)
	doc.update(data)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def delete_shift_type(name):
	"""Deletes a Shift Type if not actively assigned."""
	_check_admin_or_hr()
	active_assign = frappe.db.exists("Shift Assignment", {"shift_type": name, "status": "Active"})
	if active_assign:
		frappe.throw(_("Cannot delete Shift Type because active assignments exist for it."))

	frappe.delete_doc("Shift Type", name, ignore_permissions=True, force=True)
	frappe.db.commit()
	return {"success": True}


@frappe.whitelist()
def create_shift_assignment(data):
	"""Assigns an employee to a Shift Type."""
	_check_admin_or_hr()
	if isinstance(data, str):
		data = frappe.parse_json(data)

	if not data.get("employee") or not data.get("shift_type") or not data.get("start_date"):
		frappe.throw(_("Employee, Shift Type, and Start Date are required."))

	data["employee"] = _resolve_employee_link(data["employee"]) or data["employee"]
	doc = frappe.get_doc({"doctype": "Shift Assignment", **data})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	emp_name = frappe.db.get_value("Employee", doc.employee, "full_name") or doc.employee
	_create_in_app_notification(
		for_user=_get_user_for_employee(doc.employee),
		title="New Shift Assigned",
		message=f"You have been assigned to shift '{doc.shift_type}' starting {doc.start_date}.",
		doc_type="Shift Assignment",
		doc_name=doc.name,
	)

	res = doc.as_dict()
	res["employee_name"] = emp_name
	return res


@frappe.whitelist()
def update_shift_assignment(name, data):
	"""Updates a Shift Assignment."""
	_check_admin_or_hr()
	if isinstance(data, str):
		data = frappe.parse_json(data)

	doc = frappe.get_doc("Shift Assignment", name)
	if "employee" in data:
		data["employee"] = _resolve_employee_link(data["employee"]) or data["employee"]
	doc.update(data)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def delete_shift_assignment(name):
	"""Deletes a Shift Assignment."""
	_check_admin_or_hr()
	frappe.delete_doc("Shift Assignment", name, ignore_permissions=True, force=True)
	frappe.db.commit()
	return {"success": True}


@frappe.whitelist()
def get_holidays(year=None):
	"""Returns company holidays, optionally filtered by year."""
	_check_authenticated()
	if not frappe.db.exists("DocType", "Holiday"):
		return []

	filters = {}
	if year:
		filters["holiday_date"] = ["between", [f"{year}-01-01", f"{year}-12-31"]]

	return frappe.get_all(
		"Holiday",
		fields=["name", "holiday_name", "holiday_date", "description"],
		filters=filters,
		order_by="holiday_date asc",
	)


@frappe.whitelist()
def create_holiday(data):
	"""Creates a new Company Holiday."""
	_check_admin_or_hr()
	if isinstance(data, str):
		data = frappe.parse_json(data)

	if not data.get("holiday_name") or not data.get("holiday_date"):
		frappe.throw(_("Holiday Name and Holiday Date are required"))

	doc = frappe.get_doc({"doctype": "Holiday", **data})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def delete_holiday(name):
	"""Deletes a company holiday."""
	_check_admin_or_hr()
	frappe.delete_doc("Holiday", name, ignore_permissions=True, force=True)
	frappe.db.commit()
	return {"success": True}


@frappe.whitelist()
def get_employee_checkins(employee=None, from_date=None, to_date=None):
	"""Returns raw Employee Checkin logs with role-based scoping."""
	user = _check_authenticated()
	app_role = _get_user_app_role(user)
	linked_emp = _get_linked_employee(user)

	filters = {}
	if app_role == "Employee":
		if not linked_emp:
			return []
		filters["employee"] = linked_emp.get("name")
	elif employee:
		filters["employee"] = employee

	if from_date and to_date:
		filters["time"] = ["between", [f"{from_date} 00:00:00", f"{to_date} 23:59:59"]]
	elif from_date:
		filters["time"] = [">=", f"{from_date} 00:00:00"]
	elif to_date:
		filters["time"] = ["<=", f"{to_date} 23:59:59"]

	if not frappe.db.exists("DocType", "Employee Checkin"):
		return []

	return frappe.get_all("Employee Checkin", fields=["*"], filters=filters, order_by="time desc", limit=100)



# ---------------- PAYROLL ----------------
@frappe.whitelist()
def get_payrolls():
	if not frappe.db.exists("DocType", "Payroll"):
		return []

	user = frappe.session.user
	if not user or user == "Guest":
		return []

	try:
		records = frappe.get_all("Payroll", fields=["*"], order_by="modified desc")
		return records
	except Exception:
		return []


@frappe.whitelist()
def create_payroll(data=None):
	_check_admin_or_hr()

	if isinstance(data, str):
		data = frappe.parse_json(data)
	if not data or not frappe.db.exists("DocType", "Payroll"):
		return None
	try:
		doc = frappe.get_doc({"doctype": "Payroll", **data})
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		return doc.as_dict()
	except Exception:
		return None


# ---------------- CHAT ASSISTANT MODULE ----------------
@frappe.whitelist()
def get_chat_history(conversation_id=None):
	"""
	Retrieves chat messages from tabChat Message conforming to updated schema:
	- name, user, role, conversation_id, message_type, user_message, assistant_message,
	  generated_sql, query_status, created_at
	"""
	if not frappe.db.exists("DocType", "Chat Message"):
		return []

	user = frappe.session.user
	if not user or user == "Guest":
		return []

	filters = {"user": user}
	if conversation_id:
		filters["conversation_id"] = conversation_id

	return frappe.get_all(
		"Chat Message",
		fields=[
			"name",
			"user",
			"role",
			"conversation_id",
			"message_type",
			"user_message",
			"assistant_message",
			"generated_sql",
			"query_status",
			"created_at",
			"message",
			"response",
			"timestamp",
			"sources",
		],
		filters=filters,
		order_by="creation asc",
		limit=100,
	)


@frappe.whitelist()
def save_chat_message(
	message_type="user",
	user_message=None,
	assistant_message=None,
	conversation_id=None,
	generated_sql=None,
	query_status="success",
):
	"""
	Persists individual chat message entries to tabChat Message:
	Recommended message_type values: user, assistant, sql, error, clarification.
	"""
	user = _check_authenticated()
	role = _get_user_app_role(user)
	from employee_management_system.employee_management_system.orchestrator import save_chat_message_record

	doc = save_chat_message_record(
		user=user,
		role=role,
		conversation_id=conversation_id,
		message_type=message_type,
		user_message=user_message,
		assistant_message=assistant_message,
		generated_sql=generated_sql,
		query_status=query_status,
	)
	return doc.as_dict() if doc else None



def _generate_sql_for_question(message, user, role, linked_emp):
	"""
	SQL Generator wrapper delegating to the specialized SQL Generator in orchestrator.py.
	"""
	from employee_management_system.employee_management_system.orchestrator import generate_sql_for_question
	return generate_sql_for_question(message=message, user=user, role=role, linked_emp=linked_emp)


def _format_markdown_sql_response(sql_query):
	clean_sql = sql_query.strip()
	response_blocks = [f"```sql\n{clean_sql}\n```"]

	# Execute query safely and format clean markdown table
	exec_sql = clean_sql.rstrip(";")
	if exec_sql.upper().startswith("SELECT"):
		try:
			rows = frappe.db.sql(exec_sql, as_dict=True)
			if rows:
				headers = list(rows[0].keys())
				hdr_line = "| " + " | ".join(headers) + " |"
				sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
				data_lines = []
				for r in rows[:15]:
					vals = []
					for h in headers:
						v = r.get(h)
						if v is None:
							vals.append("-")
						elif isinstance(v, (int, float)):
							if any(k in h for k in ["salary", "pay", "gross", "net", "disbursed"]):
								vals.append(f"${v:,.2f}" if isinstance(v, float) else f"${v:,}")
							else:
								vals.append(str(v))
						else:
							vals.append(str(v).replace("|", "\\|").replace("\n", " "))
					data_lines.append("| " + " | ".join(vals) + " |")

				table_md = hdr_line + "\n" + sep_line + "\n" + "\n".join(data_lines)
				if len(rows) > 15:
					table_md += f"\n\n*Displaying first 15 of {len(rows)} rows.*"
				response_blocks.append(table_md)
			else:
				response_blocks.append("*0 rows returned.*")
		except Exception as e:
			frappe.log_error(title="Chat SQL Execution Warning", message=str(e))

	return "\n\n".join(response_blocks)


@frappe.whitelist()
def get_intent_router_prompt():
	"""
	Returns the formal System Prompt and specification contract for the EMS AI Chatbot Intent Router.
	"""
	_check_authenticated()
	from employee_management_system.employee_management_system.intent_router import (
		INTENT_ROUTER_SYSTEM_PROMPT,
		VALID_INTENTS,
	)
	return {
		"system_prompt": INTENT_ROUTER_SYSTEM_PROMPT,
		"intents": list(sorted(VALID_INTENTS)),
	}


@frappe.whitelist()
def route_chat_intent(message=None, conversation_context=None, conversation_id=None, llm_response=None):
	"""
	Classifies an incoming user message into one of the 5 intent types:
	- greeting
	- database_query
	- follow_up
	- clarification
	- unsupported

	Adheres strictly to the Intent Router specification:
	- Does NOT execute SQL
	- Does NOT enforce permissions
	- Returns strict JSON
	- Never returns SQL
	"""
	user = _check_authenticated()

	from employee_management_system.employee_management_system.intent_router import (
		route_intent,
		get_conversation_context,
		RouterValidationError,
	)

	# If explicit conversation_context is not provided, fetch recent turns from Chat Message DocType bounded to 5 messages
	if conversation_context is None and user and user != "Guest":
		conversation_context = get_conversation_context(user=user, conversation_id=conversation_id, limit=5)
	elif isinstance(conversation_context, str):
		conversation_context = frappe.parse_json(conversation_context)

	raw_llm = llm_response or frappe.form_dict.get("llm_response")

	try:
		return route_intent(message or "", conversation_context=conversation_context, llm_response=raw_llm)
	except RouterValidationError as e:
		frappe.throw(_(e.message), exc=frappe.ValidationError)


@frappe.whitelist()
def get_sql_generator_prompt():
	"""
	Returns the specialized SQL Generator System Prompt, allowed tables, and rich schema metadata.
	Dedicated solely to translating verified database inquiries into MariaDB SELECT queries.
	"""
	_check_authenticated()
	from employee_management_system.employee_management_system.sql_guard import (
		SQL_GENERATOR_SYSTEM_PROMPT,
		ALLOWED_TABLES,
		SCHEMA_METADATA,
	)
	return {
		"system_prompt": SQL_GENERATOR_SYSTEM_PROMPT,
		"allowed_tables": list(ALLOWED_TABLES.keys()),
		"schema_metadata": SCHEMA_METADATA,
	}


@frappe.whitelist()
def get_schema_metadata():
	"""
	Returns detailed metadata for tables, rows, and columns for LLM schema grounding and semantic retrieval.
	"""
	_check_authenticated()
	from employee_management_system.employee_management_system.sql_guard import (
		SCHEMA_METADATA,
	)
	return SCHEMA_METADATA


@frappe.whitelist()
def get_llm_system_prompt():
	"""Alias for get_sql_generator_prompt for backward compatibility."""
	return get_sql_generator_prompt()


@frappe.whitelist()
def validate_and_execute_llm_sql(llm_response=None, llm_json=None):
	"""
	Exposes the 10-stage programmatic SQL validation & RBAC pipeline.
	Pipeline:
	LLM JSON -> Parse JSON -> Check status == sql -> Validate SQL Parser / AST
	         -> Validate SELECT-only -> Validate tables -> Validate columns
	         -> Enforce RBAC -> Add server-side LIMIT -> Execute MariaDB
	"""
	user = _check_authenticated()
	role = _get_user_app_role(user)
	linked_emp = _get_linked_employee(user)

	raw_payload = llm_response if llm_response is not None else llm_json
	if not raw_payload:
		raw_payload = frappe.form_dict.get("llm_response") or frappe.form_dict.get("llm_json") or frappe.request.data

	if not raw_payload:
		frappe.throw(_("Missing LLM payload (llm_response or llm_json required)"))

	from employee_management_system.employee_management_system.sql_guard import (
		process_llm_pipeline,
		SQLValidationError,
	)

	try:
		return process_llm_pipeline(raw_payload, user=user, role=role, linked_emp=linked_emp)
	except SQLValidationError as e:
		frappe.throw(_(e.message), exc=frappe.PermissionError if e.status_code == 403 else frappe.ValidationError)


@frappe.whitelist()
def get_result_formatter_prompt():
	"""
	Returns the EMS AI Assistant Result Formatter prompt and rules.
	"""
	_check_authenticated()
	from employee_management_system.employee_management_system.result_formatter import RESULT_FORMATTER_SYSTEM_PROMPT
	return {
		"system_prompt": RESULT_FORMATTER_SYSTEM_PROMPT,
	}


@frappe.whitelist()
def format_database_result_api(user_question, database_result, conversation_context=None, llm_response=None):
	"""
	Explains authorized database query results using the Result Formatter.
	"""
	_check_authenticated()
	from employee_management_system.employee_management_system.result_formatter import format_database_result

	if isinstance(database_result, str):
		database_result = frappe.parse_json(database_result)

	if isinstance(conversation_context, str):
		conversation_context = frappe.parse_json(conversation_context)

	return {
		"explanation": format_database_result(
			user_question=user_question,
			database_result=database_result,
			conversation_context=conversation_context,
			llm_response=llm_response,
		)
	}


@frappe.whitelist()
def send_chat_message(message, conversation_context=None, conversation_id=None):
	"""
	Executes the end-to-end AI Assistant pipeline:

	Chatbot Router
	      ↓
	database_query?
	      ↓ YES
	SQL Generator Prompt / Logic
	      ↓
	SQL Guard (10-Stage AST & RBAC Validation)
	      ↓
	MariaDB
	      ↓
	Result Formatter Prompt (Second LLM Call)
	      ↓
	Final User Response (Plain Text Explanation)
	      ↓
	tabChat Message (Persistence)
	"""
	if not message or not str(message).strip():
		frappe.throw(_("Message is required"))

	user = _check_authenticated()
	role = _get_user_app_role(user)
	linked_emp = _get_linked_employee(user)

	from employee_management_system.employee_management_system.orchestrator import (
		orchestrate_chat_message,
	)

	result = orchestrate_chat_message(
		message=message,
		user=user,
		role=role,
		linked_emp=linked_emp,
		conversation_context=conversation_context,
		conversation_id=conversation_id,
	)

	# If this message belongs to a persistent Chat Session, update its timestamp & title
	if conversation_id and frappe.db.exists("Chat Session", conversation_id):
		try:
			sess = frappe.get_doc("Chat Session", conversation_id)
			sess.updated_at = now_datetime()
			# If title is default, set it to the first user question
			if sess.title.startswith("Chat ") or sess.title == "New Chat":
				clean_msg = re.sub(r'[\r\n\t]+', ' ', message).strip()
				sess.title = (clean_msg[:40] + '...') if len(clean_msg) > 40 else clean_msg
			sess.save(ignore_permissions=True)
			frappe.db.commit()
		except Exception:
			pass

	return result


@frappe.whitelist()
def get_conversation_state(conversation_id=None):
	"""
	Retrieves the separately stored structured conversation state for follow-up tracking.
	"""
	user = _check_authenticated()
	from employee_management_system.employee_management_system.orchestrator import (
		get_structured_conversation_state,
	)
	return get_structured_conversation_state(conversation_id=conversation_id, user=user)


@frappe.whitelist()
def query_knowledge_base(query=None):
	"""
	Queries unstructured corporate knowledge (policies, handbooks, guidelines)
	using dense vector embeddings and cosine similarity search.
	Never queries or retrieves SQL tabular employee records.
	"""
	if not query or not str(query).strip():
		frappe.throw(_("Query is required"))
	user = _check_authenticated()
	role = _get_user_app_role(user)

	from employee_management_system.employee_management_system.knowledge_engine import (
		answer_knowledge_question,
	)

	return answer_knowledge_question(query=str(query).strip(), user=user, role=role)


@frappe.whitelist()
def get_knowledge_documents():
	"""
	Returns the list of indexed unstructured corporate policy documents with metadata.
	"""
	user = _check_authenticated()
	role = _get_user_app_role(user)

	from employee_management_system.employee_management_system.knowledge_engine import (
		get_accessible_documents,
	)

	return get_accessible_documents(user=user, role=role)


@frappe.whitelist()
def get_qdrant_status():
	"""
	Returns health status, connection state, and point counts for the Qdrant vector database.
	"""
	user = _check_authenticated()
	from employee_management_system.employee_management_system.knowledge_engine import (
		get_qdrant_status as _get_qdrant_status,
	)

	return _get_qdrant_status()


@frappe.whitelist()
def sync_knowledge_base_to_qdrant(force_reload=False):
	"""
	Re-indexes corporate policies and HR documents into the Qdrant vector database.
	Restricted to Administrator or HR Manager roles.
	"""
	user = _check_authenticated()
	role = _get_user_app_role(user)
	if role not in ("Administrator", "HR"):
		frappe.throw(_("Only Administrators and HR Managers can synchronize knowledge vectors."), frappe.PermissionError)

	from employee_management_system.employee_management_system.knowledge_engine import (
		sync_knowledge_documents_to_qdrant,
	)

	return sync_knowledge_documents_to_qdrant(force_reload=frappe.parse_json(force_reload) if isinstance(force_reload, str) else bool(force_reload))


# ---------------- IN-APP NOTIFICATIONS ----------------
@frappe.whitelist()
def get_notifications(limit=30):
	"""Returns in-app notifications for the currently logged in user."""
	user = _check_authenticated()
	limit = int(limit) if limit else 30

	records = frappe.get_all(
		"Notification Log",
		filters={"for_user": user},
		fields=["name", "subject", "email_content", "read", "document_type", "document_name", "creation"],
		order_by="creation desc",
		limit=limit,
	)

	unread_count = frappe.db.count("Notification Log", {"for_user": user, "read": 0})

	return {
		"notifications": records,
		"unread_count": unread_count,
	}


@frappe.whitelist()
def mark_notification_read(notification_name):
	"""Marks a single notification as read."""
	user = _check_authenticated()
	if not frappe.db.exists("Notification Log", notification_name):
		return {"success": True}

	doc = frappe.get_doc("Notification Log", notification_name)
	if doc.for_user != user and _get_user_app_role(user) not in ("Administrator", "HR"):
		frappe.throw(_("Permission Denied"), frappe.PermissionError)
	doc.read = 1
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"success": True}


@frappe.whitelist()
def mark_all_notifications_read():
	"""Marks all unread notifications for current user as read."""
	user = _check_authenticated()
	frappe.db.sql(
		"""UPDATE `tabNotification Log` SET `read` = 1 WHERE `for_user` = %s AND `read` = 0""",
		(user,)
	)
	frappe.db.commit()
	return {"success": True}


@frappe.whitelist()
def clear_notifications(notification_name=None):
	"""Clears notifications for current user. If notification_name is given, deletes that single notification, otherwise clears all."""
	user = _check_authenticated()
	if notification_name and notification_name != "all":
		if frappe.db.exists("Notification Log", notification_name):
			doc = frappe.get_doc("Notification Log", notification_name)
			if doc.for_user == user or _get_user_app_role(user) in ("Administrator", "HR"):
				frappe.delete_doc("Notification Log", notification_name, ignore_permissions=True)
				frappe.db.commit()
		return {"success": True}

	frappe.db.sql(
		"""DELETE FROM `tabNotification Log` WHERE `for_user` = %s""",
		(user,)
	)
	frappe.db.commit()
	return {"success": True}


# ---------------- CHAT SESSION MANAGEMENT ----------------
@frappe.whitelist()
def get_chat_sessions():
	"""Returns all chat sessions belonging to the current user, pruning redundant empty duplicate sessions."""
	user = _check_authenticated()
	if not frappe.db.exists("DocType", "Chat Session"):
		return []

	sessions = frappe.get_all(
		"Chat Session",
		filters={"user_id": user},
		fields=["name", "title", "created_at", "updated_at", "messages"],
		order_by="updated_at desc, creation desc",
		limit=50,
	)

	kept_sessions = []
	empty_found = False
	to_delete = []

	for s in sessions:
		has_db_msgs = 0
		if frappe.db.table_exists("Chat Message") or frappe.db.exists("DocType", "Chat Message"):
			has_db_msgs = frappe.db.count("Chat Message", {"conversation_id": s.name})

		is_json_empty = True
		if s.messages:
			try:
				parsed = frappe.parse_json(s.messages)
				if isinstance(parsed, list) and len(parsed) > 0:
					is_json_empty = False
			except Exception:
				pass

		if has_db_msgs == 0 and is_json_empty:
			if not empty_found:
				empty_found = True
				kept_sessions.append(s)
			else:
				to_delete.append(s.name)
		else:
			kept_sessions.append(s)

	for sid in to_delete:
		try:
			frappe.delete_doc("Chat Session", sid, ignore_permissions=True, force=True)
		except Exception:
			pass
	if to_delete:
		frappe.db.commit()

	return kept_sessions


@frappe.whitelist()
def create_chat_session(title=None, initial_messages=None):
	"""
	Creates a new chat session for the current user.
	Strictly prevents duplicate sessions:
	- If an empty chat session already exists for this user (no messages in DB or JSON),
	  it reuses the existing empty session instead of inserting a duplicate record.
	- If a non-default title is provided, it updates the title of the reused session.
	"""
	user = _check_authenticated()
	now_time = now_datetime()
	sess_title = (title or "New Chat").strip()

	msgs = initial_messages
	if isinstance(msgs, (list, dict)):
		msgs = frappe.as_json(msgs)

	is_initially_empty = True
	if msgs:
		try:
			parsed = frappe.parse_json(msgs) if isinstance(msgs, str) else msgs
			if isinstance(parsed, list) and len(parsed) > 0:
				is_initially_empty = False
		except Exception:
			pass

	# Check for an existing empty session for this user to prevent duplicates
	if is_initially_empty:
		existing_sessions = frappe.get_all(
			"Chat Session",
			filters={"user_id": user},
			fields=["name", "title", "created_at", "updated_at", "messages"],
			order_by="updated_at desc, creation desc",
			limit=20,
		)
		for es in existing_sessions:
			has_db_msgs = 0
			if frappe.db.table_exists("Chat Message") or frappe.db.exists("DocType", "Chat Message"):
				has_db_msgs = frappe.db.count("Chat Message", {"conversation_id": es.name})

			is_json_empty = True
			if es.messages:
				try:
					parsed = frappe.parse_json(es.messages)
					if isinstance(parsed, list) and len(parsed) > 0:
						is_json_empty = False
				except Exception:
					pass

			if has_db_msgs == 0 and is_json_empty:
				# Re-use this existing empty session!
				if sess_title and sess_title != "New Chat" and es.title == "New Chat":
					frappe.db.set_value("Chat Session", es.name, "title", sess_title)
					es.title = sess_title
					frappe.db.commit()
				return es

	# Also check if an active session with the exact same non-default title already exists
	if sess_title and sess_title != "New Chat":
		existing_by_title = frappe.get_all(
			"Chat Session",
			filters={"user_id": user, "title": sess_title},
			fields=["name", "title", "created_at", "updated_at", "messages"],
			order_by="updated_at desc",
			limit=1,
		)
		if existing_by_title and is_initially_empty:
			return existing_by_title[0]

	doc = frappe.get_doc({
		"doctype": "Chat Session",
		"title": sess_title,
		"user_id": user,
		"created_at": now_time,
		"updated_at": now_time,
		"messages": msgs or "[]",
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def get_chat_session_messages(session_id):
	"""Returns message history for a specific chat session."""
	user = _check_authenticated()
	if not frappe.db.exists("Chat Session", session_id):
		frappe.throw(_("Chat session not found"))

	sess = frappe.get_doc("Chat Session", session_id)
	if sess.user_id != user and _get_user_app_role(user) != "Administrator":
		frappe.throw(_("Permission denied"), frappe.PermissionError)

	msgs = []
	if frappe.db.table_exists("Chat Message") or frappe.db.exists("DocType", "Chat Message"):
		rows = frappe.get_all(
			"Chat Message",
			filters={"conversation_id": session_id},
			fields=["name", "user_message", "assistant_message", "generated_sql", "query_status", "message_type", "created_at"],
			order_by="created_at asc, creation asc",
		)
		for r in rows:
			if r.get("user_message"):
				msgs.append({
					"id": f"{r.name}_u",
					"sender": "user",
					"text": r.user_message,
					"timestamp": str(r.created_at or ""),
				})
			if r.get("assistant_message"):
				msgs.append({
					"id": f"{r.name}_a",
					"sender": "assistant",
					"text": r.assistant_message,
					"generated_sql": r.get("generated_sql"),
					"query_status": r.get("query_status"),
					"message_type": r.get("message_type"),
					"timestamp": str(r.created_at or ""),
				})

	if not msgs and sess.messages:
		try:
			parsed = frappe.parse_json(sess.messages)
			if isinstance(parsed, list):
				msgs = parsed
		except Exception:
			pass

	return msgs


@frappe.whitelist()
def save_chat_session(session_id, messages=None, title=None):
	"""Saves message history and optionally updates title for a chat session."""
	user = _check_authenticated()
	if not frappe.db.exists("Chat Session", session_id):
		frappe.throw(_("Chat session not found"))

	doc = frappe.get_doc("Chat Session", session_id)
	if doc.user_id != user and _get_user_app_role(user) != "Administrator":
		frappe.throw(_("Permission denied"), frappe.PermissionError)

	if title:
		doc.title = title
	if messages is not None:
		doc.messages = frappe.as_json(messages) if not isinstance(messages, str) else messages
	doc.updated_at = now_datetime()
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return doc.as_dict()


@frappe.whitelist()
def delete_chat_session(session_id):
	"""Deletes a chat session and associated chat messages."""
	user = _check_authenticated()
	if not frappe.db.exists("Chat Session", session_id):
		return {"success": True}

	doc = frappe.get_doc("Chat Session", session_id)
	if doc.user_id != user and _get_user_app_role(user) != "Administrator":
		frappe.throw(_("Permission denied"), frappe.PermissionError)

	# Delete messages for this conversation_id
	if frappe.db.table_exists("Chat Message") or frappe.db.exists("DocType", "Chat Message"):
		frappe.db.sql("DELETE FROM `tabChat Message` WHERE conversation_id = %s", (session_id,))

	frappe.delete_doc("Chat Session", session_id, ignore_permissions=True, force=True)
	frappe.db.commit()
	return {"success": True}

