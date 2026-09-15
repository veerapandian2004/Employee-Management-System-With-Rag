# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import (
	flt,
	get_datetime,
	now_datetime,
	nowdate,
	time_diff_in_seconds,
)

from employee_management_system.employee_management_system.attendance.gps_validation import (
	validate_coordinates,
	validate_gps_accuracy,
	validate_office_radius,
)


def get_authenticated_employee(user=None):
	"""
	Identifies and validates the Employee record linked to the logged-in user.
	Never trusts an employee ID supplied by the frontend client.
	"""
	if not user:
		user = frappe.session.user

	if not user or user == "Guest":
		frappe.throw(
			_("Please log in to record attendance."),
			frappe.AuthenticationError,
		)

	# Match employee by user_id or email
	emp = frappe.db.get_value(
		"Employee",
		{"user_id": user},
		["name", "full_name", "status", "office_location", "email"],
		as_dict=True,
	)

	if not emp and "@" in user:
		emp = frappe.db.get_value(
			"Employee",
			{"email": user},
			["name", "full_name", "status", "office_location", "email"],
			as_dict=True,
		)

	# Administrators are exempt from attendance clock-in / clock-out tracking
	if user == "Administrator":
		frappe.throw(
			_("Administrators do not clock in or clock out. Your role is to monitor attendance for HR and Employees."),
			frappe.PermissionError,
		)

	if not emp:
		frappe.throw(
			_("No Employee record is linked to your user account ({user}). Please contact HR.").format(
				user=user
			),
			title=_("Employee Not Found"),
		)

	if emp.status != "Active":
		frappe.throw(
			_(
				f"Only active employees can record attendance. "
				f"Your employee profile ({emp.name}) has status '{emp.status}'."
			),
			title=_("Inactive Employee"),
		)

	return emp


def get_assigned_office(employee_doc):
	"""
	Resolves the authorized Office Location document for the given employee.
	Falls back to the default active office if not explicitly assigned.
	"""
	office_name = employee_doc.get("office_location") if isinstance(employee_doc, dict) else getattr(employee_doc, "office_location", None)

	if office_name and frappe.db.exists("Office Location", office_name):
		office = frappe.get_doc("Office Location", office_name)
		if office.is_active:
			return office

	# Fallback: Find the first active office
	active_offices = frappe.get_all(
		"Office Location",
		filters={"is_active": 1},
		fields=["name", "office_name", "latitude", "longitude", "allowed_radius", "max_accuracy"],
		order_by="creation asc",
		limit=1,
	)

	if active_offices:
		return frappe.get_doc("Office Location", active_offices[0].name)

	frappe.throw(
		_("No active Office Location is configured in the system. Please contact HR or System Administrator."),
		title=_("Office Location Missing"),
	)


def get_latest_checkin(employee_id):
	"""
	Retrieves the most recent Employee Checkin record for this employee.
	"""
	checkins = frappe.get_all(
		"Employee Checkin",
		filters={"employee": employee_id},
		fields=[
			"name",
			"employee",
			"time",
			"log_type",
			"shift",
			"shift_start",
			"shift_end",
			"attendance_source",
			"latitude",
			"longitude",
			"accuracy",
			"distance_from_office",
			"office_location",
			"is_auto_clock_out",
			"clock_out_reason",
		],
		order_by="time desc, creation desc",
		limit=1,
	)
	return checkins[0] if checkins else None


def validate_checkin_sequence(employee_id, requested_type):
	"""
	Enforces strict IN -> OUT -> IN -> OUT sequence.
	Rejects:
	- IN -> IN (Already clocked in)
	- OUT -> OUT (Already clocked out)
	- OUT without prior valid IN
	"""
	latest = get_latest_checkin(employee_id)

	req = (requested_type or "IN").strip().upper()

	if req == "IN":
		if latest and latest.get("log_type") == "IN":
			frappe.throw(
				_(
					f"You are already clocked in (since {latest.get('time')}). "
					f"Please clock out before clocking in again."
				),
				title=_("Already Clocked In"),
			)
	elif req == "OUT":
		if not latest or latest.get("log_type") != "IN":
			frappe.throw(
				_("Cannot clock OUT without an active clock IN session. Please clock in first."),
				title=_("Not Clocked In"),
			)

	return True


def record_gps_checkin(log_type, latitude, longitude, accuracy, user=None):
	"""
	Orchestrates the secure GPS check-in / check-out process:
	1. Authenticates employee from session user
	2. Validates GPS coordinates & accuracy
	3. Validates office location & Haversine distance
	4. Validates IN/OUT sequence & duplicate prevention
	5. Creates Employee Checkin record with server timestamp
	6. Triggers shift auto-attendance recalculation
	"""
	emp = get_authenticated_employee(user=user)
	emp_id = emp.name

	log_type = (log_type or "IN").strip().upper()
	if log_type not in ("IN", "OUT"):
		log_type = "IN"

	# Validate coordinates
	lat, lon = validate_coordinates(latitude, longitude)

	# Resolve office: check assigned office, or match any active authorized office where employee is within radius
	from employee_management_system.employee_management_system.attendance.gps_validation import (
		haversine_distance,
	)

	office = None
	try:
		assigned_office = get_assigned_office(emp)
		dist = haversine_distance(lat, lon, assigned_office.latitude, assigned_office.longitude)
		rad = flt(assigned_office.allowed_radius) if assigned_office.allowed_radius else 150.0
		if dist <= rad:
			office = assigned_office
	except Exception:
		pass

	if not office:
		active_offices = frappe.get_all(
			"Office Location",
			filters={"is_active": 1},
			fields=["name", "office_name", "latitude", "longitude", "allowed_radius", "max_accuracy"],
		)
		for off_row in active_offices:
			d = haversine_distance(lat, lon, off_row.latitude, off_row.longitude)
			r = flt(off_row.allowed_radius) if off_row.allowed_radius else 150.0
			if d <= r:
				office = frappe.get_doc("Office Location", off_row.name)
				break

	if not office:
		office = get_assigned_office(emp)

	# Validate GPS accuracy against office policy
	acc = validate_gps_accuracy(accuracy, max_accuracy=office.max_accuracy)

	# Validate distance within allowed office radius
	distance = validate_office_radius(
		emp_lat=lat,
		emp_lon=lon,
		office_lat=office.latitude,
		office_lon=office.longitude,
		allowed_radius=office.allowed_radius,
		office_name=office.office_name,
	)

	# Validate sequence
	validate_checkin_sequence(emp_id, log_type)

	# Server-side timestamp
	t = now_datetime()

	# Resolve active shift
	from employee_management_system.employee_management_system.shift_attendance import (
		get_active_shift_assignments,
		get_shift_window,
		process_attendance_for_employee_shift,
	)

	active_shifts = get_active_shift_assignments(t.date(), employee=emp_id)
	shift_name = active_shifts[0]["shift_type"] if active_shifts else None
	shift_start = None
	shift_end = None
	if shift_name and frappe.db.exists("Shift Type", shift_name):
		sdoc = frappe.get_doc("Shift Type", shift_name)
		s_start, s_end, _, _, _ = get_shift_window(sdoc, t.date())
		shift_start = s_start
		shift_end = s_end

	# Insert Checkin record
	checkin_doc = frappe.get_doc({
		"doctype": "Employee Checkin",
		"employee": emp_id,
		"employee_name": emp.full_name,
		"time": t,
		"log_type": log_type,
		"shift": shift_name,
		"shift_start": shift_start,
		"shift_end": shift_end,
		"device_id": "GPS Web Clock",
		"attendance_source": "GPS Web Clock",
		"latitude": lat,
		"longitude": lon,
		"accuracy": acc,
		"distance_from_office": distance,
		"office_location": office.name,
	})
	checkin_doc.insert(ignore_permissions=True)
	frappe.db.commit()

	# Trigger auto attendance recalculation
	attendance_result = None
	if shift_name:
		try:
			attendance_result = process_attendance_for_employee_shift(
				employee=emp_id,
				shift_type_name=shift_name,
				attendance_date=t.date(),
			)
			frappe.db.commit()
		except Exception as e:
			frappe.logger().error(f"Auto attendance recalculation error for {emp_id}: {e}")

	return {
		"checkin": checkin_doc.as_dict(),
		"office": {
			"name": office.name,
			"office_name": office.office_name,
			"allowed_radius": office.allowed_radius,
		},
		"distance": distance,
		"attendance": attendance_result,
	}


def get_employee_attendance_status(employee_id=None, user=None):
	"""
	Returns the real-time attendance status for the employee:
	- Current state: 'Not Clocked In', 'Working', 'Clocked Out'
	- Last Clock IN time & Clock OUT time today
	- Live working duration in seconds
	- Today's shift information
	- Assigned office details
	"""
	if not user:
		user = frappe.session.user

	if user == "Administrator" and not employee_id:
		return {
			"is_administrator": True,
			"exempt": True,
			"is_clocked_in": False,
			"current_status": "Exempt",
			"message": "Administrators do not clock in or clock out. Your role is to monitor attendance for HR and Employees.",
		}

	if not employee_id:
		emp = get_authenticated_employee(user=user)
		emp_id = emp.name
	else:
		emp_id = employee_id
		emp = frappe.db.get_value(
			"Employee",
			emp_id,
			["name", "full_name", "status", "office_location"],
			as_dict=True,
		)

	if not emp:
		return {
			"is_clocked_in": False,
			"current_status": "Not Clocked In",
			"message": "Employee not found",
		}

	office = None
	try:
		office_doc = get_assigned_office(emp)
		office = {
			"name": office_doc.name,
			"office_name": office_doc.office_name,
			"allowed_radius": office_doc.allowed_radius,
			"max_accuracy": office_doc.max_accuracy,
		}
	except Exception:
		pass

	# Active Shift
	from employee_management_system.employee_management_system.shift_attendance import (
		get_active_shift_assignments,
	)

	today_date = nowdate()
	active_shifts = get_active_shift_assignments(today_date, employee=emp_id)
	today_shift = None
	if active_shifts:
		shift_name = active_shifts[0]["shift_type"]
		if frappe.db.exists("Shift Type", shift_name):
			s = frappe.get_doc("Shift Type", shift_name)
			today_shift = {
				"name": s.name,
				"shift_name": s.shift_name,
				"start_time": str(s.start_time)[:8] if s.start_time else None,
				"end_time": str(s.end_time)[:8] if s.end_time else None,
				"late_entry_grace_period": s.late_entry_grace_period,
				"early_exit_grace_period": s.early_exit_grace_period,
			}

	# Check-in logs today
	today_start = f"{today_date} 00:00:00"
	checkins_today = frappe.get_all(
		"Employee Checkin",
		filters={"employee": emp_id, "time": [">=", today_start]},
		fields=["name", "time", "log_type", "attendance_source", "distance_from_office"],
		order_by="time asc",
	)

	latest = get_latest_checkin(emp_id)
	is_clocked_in = bool(latest and latest.get("log_type") == "IN")

	# Evaluate shift completion auto clock-out if shift has elapsed
	if is_clocked_in and today_shift:
		try:
			from employee_management_system.employee_management_system.attendance.auto_clock_out_service import (
				check_shift_completion_auto_clock_out,
			)
			auto_outs = check_shift_completion_auto_clock_out(today_date, employee_id=emp_id)
			if auto_outs:
				latest = get_latest_checkin(emp_id)
				is_clocked_in = bool(latest and latest.get("log_type") == "IN")
		except Exception as e:
			frappe.logger().error(f"Error evaluating shift completion in status check: {e}")

	clock_in_time = None
	clock_out_time = None
	working_seconds = 0

	# Get attendance record for today if exists
	today_att = frappe.db.get_value(
		"Attendance",
		{"employee": emp_id, "attendance_date": today_date},
		["name", "status", "working_hours", "late_entry", "early_exit", "auto_clocked_out", "clock_out_reason", "auto_clock_out_time", "office_location", "remarks"],
		as_dict=True,
	)

	if is_clocked_in:
		current_status = "Working"
		clock_in_time = str(latest.get("time"))
		# While working, the active session has not clocked out.
		# Never carry over a previous session's clock-out time or auto clock-out state.
		clock_out_time = None
		auto_clocked_out = False
		clock_out_reason = None
		auto_clock_out_time = None
		if today_att:
			today_att["out_time"] = None
			today_att["auto_clocked_out"] = 0
			today_att["clock_out_reason"] = None
			today_att["auto_clock_out_time"] = None
			today_att["early_exit"] = 0

		# Calculate seconds since active IN
		in_dt = get_datetime(latest.get("time"))
		working_seconds = max(0, int(time_diff_in_seconds(now_datetime(), in_dt)))
	else:
		# Employee is NOT currently clocked in
		# Find the most recent OUT punch today or from latest checkin
		if latest and latest.get("log_type") == "OUT":
			clock_out_time = str(latest.get("time"))
		elif checkins_today:
			for chk in reversed(checkins_today):
				if chk.log_type == "OUT":
					clock_out_time = str(chk.time)
					break

		if clock_out_time:
			current_status = "Clocked Out"
		else:
			current_status = "Not Clocked In"

		# Find clock in for today's session
		for chk in checkins_today:
			if chk.log_type == "IN":
				clock_in_time = str(chk.time)
				break
		if not clock_in_time and latest and latest.get("log_type") == "IN":
			clock_in_time = str(latest.get("time"))

		# Only mark auto_clocked_out if the session ended via auto clock-out
		is_latest_auto_out = bool(latest and latest.get("log_type") == "OUT" and latest.get("is_auto_clock_out"))
		auto_clocked_out = is_latest_auto_out or bool(today_att and today_att.get("auto_clocked_out") and today_att.get("out_time"))
		clock_out_reason = (latest.get("clock_out_reason") if is_latest_auto_out else None) or (today_att.get("clock_out_reason") if auto_clocked_out and today_att else None)
		auto_clock_out_time = (str(latest.get("time")) if is_latest_auto_out else None) or (str(today_att.get("auto_clock_out_time")) if auto_clocked_out and today_att and today_att.get("auto_clock_out_time") else None)

	return {
		"employee": emp_id,
		"employee_name": emp.get("full_name") or emp_id,
		"is_clocked_in": is_clocked_in,
		"current_status": current_status,
		"last_log_type": latest.get("log_type") if latest else None,
		"clock_in_time": clock_in_time or (str(latest.get("time")) if is_clocked_in else None),
		"clock_out_time": clock_out_time,
		"working_duration_seconds": working_seconds,
		"office": office,
		"today_shift": today_shift,
		"today_attendance": today_att,
		"auto_clocked_out": auto_clocked_out,
		"clock_out_reason": clock_out_reason,
		"auto_clock_out_time": auto_clock_out_time,
	}
