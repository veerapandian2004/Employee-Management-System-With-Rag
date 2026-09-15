# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

"""
AUTOMATIC CLOCK-OUT SERVICE
============================
Enforces automated clock-out policies based on:
1. Location-based Geofence Monitoring (Reason: 'Left Office Location')
2. Scheduled Shift Completion (Reason: 'Shift Completed')

Key Behaviors:
- Left Office Location: Triggered immediately when employee leaves permitted geofence during working hours.
- Shift Completed: Triggered when employee is still clocked in past scheduled shift end; clocked out at exact shift end time.
- Priority and Tracking: Saves exact date, time, and reason in both tabAttendance and tabEmployee Checkin.
- Multi-Channel Notifications: Alerts both the employee and administrators via Notification Log & realtime socket.
"""

import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import frappe
from frappe import _
from frappe.utils import (
	cint,
	flt,
	get_datetime,
	getdate,
	now_datetime,
	nowdate,
)

from employee_management_system.employee_management_system.attendance.gps_validation import (
	haversine_distance,
	validate_coordinates,
	validate_gps_accuracy,
)
from employee_management_system.employee_management_system.attendance.checkin_service import (
	get_assigned_office,
	get_latest_checkin,
)

REASON_LEFT_OFFICE = "Left Office Location"
REASON_SHIFT_COMPLETED = "Shift Completed"
REASON_AUTO_CLOCK_OUT = "Auto Clock-Out"
VALID_REASONS = {REASON_LEFT_OFFICE, REASON_SHIFT_COMPLETED, REASON_AUTO_CLOCK_OUT}


def is_employee_clocked_in(employee_id: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
	"""
	Determines if the employee is currently in a clocked-in state.
	Returns (is_clocked_in, latest_checkin_doc).
	"""
	latest = get_latest_checkin(employee_id)
	is_in = bool(latest and latest.get("log_type") == "IN")
	return is_in, latest


def auto_clock_out_employee(
	employee_id: str,
	reason: str,
	clock_out_datetime: Optional[datetime.datetime] = None,
	latitude: Optional[float] = None,
	longitude: Optional[float] = None,
	accuracy: Optional[float] = None,
	distance: Optional[float] = None,
) -> Dict[str, Any]:
	"""
	Executes an automatic clock-out for the given employee:
	1. Validates reason ('Left Office Location', 'Shift Completed', or 'Auto Clock-Out')
	2. Verifies employee is currently clocked in (avoids duplicate clock-outs)
	3. Determines exact clock-out timestamp (current time or shift end time)
	4. Inserts OUT Employee Checkin record recorded against the SAME office/location as clock-in
	5. Recalculates and upserts Attendance record with reason, auto flag, office location, and exact timestamp
	6. Emits notifications to both employee and administrators
	"""
	if reason not in VALID_REASONS:
		raise frappe.ValidationError(
			_("Invalid auto clock-out reason: '{0}'. Must be one of {1}").format(
				reason, list(VALID_REASONS)
			)
		)

	# Verify active check-in session
	is_clocked_in, latest_chk = is_employee_clocked_in(employee_id)
	if not is_clocked_in:
		return {
			"status": "already_clocked_out",
			"employee": employee_id,
			"message": _("Employee is not currently clocked in."),
			"auto_clocked_out": False,
		}

	# Exact timestamp determination
	if not clock_out_datetime:
		clock_out_datetime = now_datetime()
	elif isinstance(clock_out_datetime, str):
		clock_out_datetime = get_datetime(clock_out_datetime)

	# Fetch employee details
	emp = frappe.db.get_value(
		"Employee",
		employee_id,
		["name", "full_name", "user_id", "email", "office_location", "status"],
		as_dict=True,
	)
	if not emp:
		raise frappe.ValidationError(_("Employee '{0}' not found.").format(employee_id))

	emp_name = emp.get("full_name") or employee_id

	# Resolve office: Priority to the clock-in punch's office location so clock-out is recorded against the same office
	office_name = latest_chk.get("office_location") if latest_chk else None
	office_doc = None
	if office_name and frappe.db.exists("Office Location", office_name):
		office_doc = frappe.get_doc("Office Location", office_name)
	elif not office_name:
		try:
			office_doc = get_assigned_office(emp)
			office_name = office_doc.name
		except Exception:
			office_name = emp.get("office_location")

	if latitude is None:
		if latest_chk and latest_chk.get("latitude") is not None:
			latitude = latest_chk.get("latitude")
			longitude = latest_chk.get("longitude")
		elif office_doc:
			latitude = office_doc.latitude
			longitude = office_doc.longitude

	if accuracy is None and latest_chk:
		accuracy = latest_chk.get("accuracy")

	if distance is None:
		distance = latest_chk.get("distance_from_office") if latest_chk else 0.0

	# Resolve active shift
	from employee_management_system.employee_management_system.shift_attendance import (
		get_active_shift_assignments,
		get_shift_window,
		process_attendance_for_employee_shift,
	)

	att_date = clock_out_datetime.date()
	active_shifts = get_active_shift_assignments(att_date, employee=employee_id)
	shift_name = active_shifts[0]["shift_type"] if active_shifts else None
	shift_start = None
	shift_end = None

	if shift_name and frappe.db.exists("Shift Type", shift_name):
		sdoc = frappe.get_doc("Shift Type", shift_name)
		shift_start, shift_end, w_start, w_end, is_overnight = get_shift_window(sdoc, att_date)

	# 1. Insert OUT checkin log with auto clock-out metadata
	checkin_doc = frappe.get_doc({
		"doctype": "Employee Checkin",
		"employee": employee_id,
		"employee_name": emp_name,
		"time": clock_out_datetime,
		"log_type": "OUT",
		"shift": shift_name,
		"shift_start": shift_start,
		"shift_end": shift_end,
		"device_id": "EMS Auto Clock-Out Engine",
		"attendance_source": f"Auto Clock-Out ({reason})",
		"latitude": latitude,
		"longitude": longitude,
		"accuracy": accuracy,
		"distance_from_office": distance,
		"office_location": office_name,
		"is_auto_clock_out": 1,
		"clock_out_reason": reason,
	})
	checkin_doc.insert(ignore_permissions=True)
	frappe.db.commit()

	# 2. Recalculate Attendance and save exact auto clock-out record
	attendance_result = None
	remarks = f"Auto clocked out: {reason} at {clock_out_datetime.strftime('%Y-%m-%d %H:%M:%S')}"

	if shift_name:
		try:
			attendance_result = process_attendance_for_employee_shift(
				employee=employee_id,
				shift_type_name=shift_name,
				attendance_date=att_date,
			)
		except Exception as e:
			frappe.logger().error(f"Error recalculating attendance for {employee_id}: {e}")

	# Explicitly ensure auto clock-out columns on tabAttendance are recorded
	existing_att = frappe.db.get_value(
		"Attendance",
		{"employee": employee_id, "attendance_date": att_date},
		["name", "remarks"],
		as_dict=True,
	)

	att_id = None
	if existing_att:
		att_id = existing_att.name
		cur_remarks = existing_att.remarks or ""
		updated_remarks = f"{cur_remarks} | {remarks}" if cur_remarks else remarks
		frappe.db.set_value(
			"Attendance",
			att_id,
			{
				"out_time": clock_out_datetime.strftime("%Y-%m-%d %H:%M:%S"),
				"auto_clocked_out": 1,
				"clock_out_reason": reason,
				"auto_clock_out_time": clock_out_datetime.strftime("%Y-%m-%d %H:%M:%S"),
				"office_location": office_name,
				"remarks": updated_remarks,
			},
			update_modified=True,
		)
		frappe.db.commit()
	else:
		# Upsert fresh record if none existed
		from employee_management_system.employee_management_system.shift_attendance import (
			calculate_working_hours_from_checkins,
			upsert_attendance_record,
		)
		day_logs = frappe.get_all(
			"Employee Checkin",
			filters={
				"employee": employee_id,
				"time": ["between", [f"{att_date} 00:00:00", f"{att_date} 23:59:59"]],
			},
			fields=["name", "employee", "time", "log_type"],
			order_by="time asc",
		)
		calc = calculate_working_hours_from_checkins(day_logs)
		first_in = calc.get("first_in")
		total_hours = calc.get("total_working_hours", 0.0)
		log_names = calc.get("log_names", [])

		res = upsert_attendance_record(
			employee=employee_id,
			attendance_date=att_date,
			status="Present" if total_hours >= 4.0 else "Absent",
			shift=shift_name,
			in_time=first_in,
			out_time=clock_out_datetime,
			working_hours=total_hours,
			auto_clocked_out=1,
			clock_out_reason=reason,
			auto_clock_out_time=clock_out_datetime,
			office_location=office_name,
			remarks=remarks,
			checkin_names=log_names,
		)
		att_id = res.get("attendance_id")

	if att_id:
		frappe.db.set_value(
			"Attendance",
			att_id,
			{
				"auto_clocked_out": 1,
				"clock_out_reason": reason,
				"auto_clock_out_time": clock_out_datetime.strftime("%Y-%m-%d %H:%M:%S"),
				"office_location": office_name,
			},
			update_modified=False,
		)
		frappe.db.commit()

	# Link checkin doc to attendance
	if att_id:
		frappe.db.set_value("Employee Checkin", checkin_doc.name, "attendance", att_id, update_modified=False)
		frappe.db.commit()

	# 3. Dispatch notifications to Employee and Administrator
	notifications = send_auto_clock_out_notifications(
		employee_id=employee_id,
		employee_name=emp_name,
		reason=reason,
		clock_out_time=clock_out_datetime,
		attendance_id=att_id,
	)

	return {
		"status": "clocked_out",
		"auto_clocked_out": True,
		"employee": employee_id,
		"employee_name": emp_name,
		"reason": reason,
		"clock_out_time": str(clock_out_datetime),
		"attendance_date": str(att_date),
		"attendance_id": att_id,
		"checkin_id": checkin_doc.name,
		"notifications": notifications,
	}


def check_location_auto_clock_out(
	employee_id: str,
	latitude: float,
	longitude: float,
	accuracy: Optional[float] = None,
) -> Dict[str, Any]:
	"""
	Rule 1: Location-based automatic clock-out:
	If an employee leaves the assigned office location or permitted geofence area
	during their working hours, automatically clock them out.
	"""
	is_clocked_in, latest_chk = is_employee_clocked_in(employee_id)
	if not is_clocked_in:
		return {
			"action": "none",
			"auto_clocked_out": False,
			"is_clocked_in": False,
			"message": "Employee is not clocked in. Geofence check skipped.",
		}

	# Validate coordinates
	lat, lon = validate_coordinates(latitude, longitude)

	emp = frappe.db.get_value(
		"Employee",
		employee_id,
		["name", "full_name", "office_location", "status"],
		as_dict=True,
	)
	if not emp:
		return {"action": "error", "message": "Employee not found"}

	office = get_assigned_office(emp)
	acc = validate_gps_accuracy(accuracy, max_accuracy=office.max_accuracy)

	# Compute great-circle distance
	distance = haversine_distance(
		lat1=lat,
		lon1=lon,
		lat2=office.latitude,
		lon2=office.longitude,
	)

	allowed_radius = flt(office.allowed_radius) if office.allowed_radius else 150.0

	# Evaluate if employee is outside permitted geofence
	if distance > allowed_radius:
		# Employee has left office location! Clock out automatically.
		clock_out_res = auto_clock_out_employee(
			employee_id=employee_id,
			reason=REASON_LEFT_OFFICE,
			clock_out_datetime=now_datetime(),
			latitude=lat,
			longitude=lon,
			accuracy=acc,
			distance=distance,
		)
		return {
			"action": "auto_clocked_out",
			"auto_clocked_out": True,
			"reason": REASON_LEFT_OFFICE,
			"distance": distance,
			"allowed_radius": allowed_radius,
			"office_name": office.office_name,
			"clock_out_time": str(now_datetime()),
			"details": clock_out_res,
			"message": (
				f"You have left the authorized geofence for {office.office_name} "
				f"({distance:.1f}m away, limit {allowed_radius:.0f}m). "
				f"You have been automatically clocked out."
			),
		}

	return {
		"action": "verified_inside",
		"auto_clocked_out": False,
		"is_clocked_in": True,
		"distance": distance,
		"allowed_radius": allowed_radius,
		"office_name": office.office_name,
		"message": f"Inside office boundary ({distance:.1f}m of {allowed_radius:.0f}m allowed).",
	}


def check_shift_completion_auto_clock_out(
	target_date: Optional[Union[datetime.date, str]] = None,
	employee_id: Optional[str] = None,
	current_time: Optional[Union[datetime.datetime, str]] = None,
) -> List[Dict[str, Any]]:
	"""
	Rule 2: Shift completion automatic clock-out:
	If an employee is still clocked in when their scheduled shift ends,
	automatically clock them out at the shift end time recorded against the same office location.
	If the employee has already clocked out manually, no duplicate clock-out is created.
	"""
	from employee_management_system.employee_management_system.shift_attendance import (
		get_active_shift_assignments,
		get_shift_window,
	)

	now_dt = get_datetime(current_time) if current_time else now_datetime()
	current_date = getdate(target_date) if target_date else now_dt.date()
	yesterday_date = current_date - datetime.timedelta(days=1)

	# Query all active employees with latest punch == 'IN'
	filters = {"status": "Active"}
	if employee_id:
		filters["name"] = employee_id

	active_employees = frappe.get_all("Employee", filters=filters, fields=["name", "full_name"])

	results = []
	for emp in active_employees:
		eid = emp.name
		is_in, latest_chk = is_employee_clocked_in(eid)
		if not is_in or not latest_chk:
			continue

		# Resolve shift: check latest_chk first, then active shift assignments
		shift_name = latest_chk.get("shift")
		if not shift_name:
			assigned_shifts = get_active_shift_assignments(current_date, employee=eid)
			if not assigned_shifts:
				assigned_shifts = get_active_shift_assignments(yesterday_date, employee=eid)
			if assigned_shifts:
				shift_name = assigned_shifts[0]["shift_type"]

		if not shift_name or not frappe.db.exists("Shift Type", shift_name):
			continue

		sdoc = frappe.get_doc("Shift Type", shift_name)

		# Resolve shift window and scheduled shift_end
		chk_time = get_datetime(latest_chk.get("time"))
		eval_date = chk_time.date() if chk_time else current_date

		if latest_chk.get("shift_end"):
			shift_end = get_datetime(latest_chk.get("shift_end"))
		else:
			shift_start, shift_end, _, _, is_overnight = get_shift_window(sdoc, eval_date)

		# Check condition: if current time is at or past scheduled shift_end, and employee is still clocked in
		# Only auto clock out at shift_end if the active clock-in occurred before shift_end.
		# If the employee clocked in after shift_end, do not clock them out with a past shift_end timestamp.
		if now_dt >= shift_end and chk_time < shift_end:
			# Auto clock out at exact shift_end timestamp against the SAME office location
			clock_out_res = auto_clock_out_employee(
				employee_id=eid,
				reason=REASON_SHIFT_COMPLETED,
				clock_out_datetime=shift_end,
			)
			results.append(clock_out_res)

	return results


def process_shift_completion_job():
	"""
	Periodic background job hooked into Frappe scheduler (hooks.py).
	Evaluates and clocks out any employees whose shifts have ended.
	"""
	res = check_shift_completion_auto_clock_out()
	if res:
		frappe.logger().info(f"Auto Clock-Out Job processed {len(res)} employees on shift completion.")
	return {"processed": len(res), "timestamp": str(now_datetime())}


def send_auto_clock_out_notifications(
	employee_id: str,
	employee_name: str,
	reason: str,
	clock_out_time: datetime.datetime,
	attendance_id: Optional[str] = None,
) -> Dict[str, Any]:
	"""
	Rule 5: Notification:
	Optionally notify the employee and administrator when an automatic clock-out occurs.
	Creates Notification Log records and publishes real-time socket events.
	"""
	formatted_time = clock_out_time.strftime("%Y-%m-%d %I:%M:%S %p")
	subject = f"Automatic Clock-Out: {reason}"
	message = (
		f"Employee {employee_name} ({employee_id}) was automatically clocked out "
		f"at {formatted_time} due to: {reason}."
	)

	# 1. Resolve employee user
	emp_user = frappe.db.get_value("Employee", employee_id, "user_id")
	if not emp_user:
		emp_user = frappe.db.get_value("Employee", employee_id, "email")

	created_logs = []

	# In-app Notification Log for Employee
	if emp_user and emp_user != "Guest" and frappe.db.exists("User", emp_user):
		try:
			notif_emp = frappe.get_doc({
				"doctype": "Notification Log",
				"subject": subject,
				"email_content": message,
				"for_user": emp_user,
				"type": "Alert",
				"document_type": "Attendance" if attendance_id else "Employee Checkin",
				"document_name": attendance_id or employee_id,
			})
			notif_emp.insert(ignore_permissions=True)
			created_logs.append(notif_emp.name)
		except Exception as e:
			frappe.logger().error(f"Failed to create Notification Log for employee {emp_user}: {e}")

	# 2. Resolve Administrators & HR
	admin_users = frappe.get_all(
		"Has Role",
		filters={"role": ["in", ["System Manager", "Administrator", "HR"]], "parenttype": "User"},
		fields=["parent"],
		distinct=True,
	)
	admin_user_ids = {u.parent for u in admin_users if u.parent not in [emp_user, "Guest"]}
	admin_user_ids.add("Administrator")

	for a_user in admin_user_ids:
		if frappe.db.exists("User", a_user):
			try:
				notif_admin = frappe.get_doc({
					"doctype": "Notification Log",
					"subject": f"Admin Alert: {subject}",
					"email_content": message,
					"for_user": a_user,
					"type": "Alert",
					"document_type": "Attendance" if attendance_id else "Employee Checkin",
					"document_name": attendance_id or employee_id,
				})
				notif_admin.insert(ignore_permissions=True)
				created_logs.append(notif_admin.name)
			except Exception as e:
				frappe.logger().error(f"Failed to create Notification Log for admin {a_user}: {e}")

	frappe.db.commit()

	# 3. Publish real-time socket events
	try:
		realtime_payload = {
			"employee": employee_id,
			"employee_name": employee_name,
			"reason": reason,
			"clock_out_time": formatted_time,
			"attendance_id": attendance_id,
			"message": message,
		}
		if emp_user:
			frappe.publish_realtime(
				event="auto_clock_out",
				message=realtime_payload,
				user=emp_user,
			)
		frappe.publish_realtime(
			event="auto_clock_out_admin",
			message=realtime_payload,
		)
	except Exception as e:
		frappe.logger().error(f"Failed to publish realtime auto clock out event: {e}")

	return {
		"employee_notified": emp_user,
		"admins_notified": list(admin_user_ids),
		"notification_logs": created_logs,
		"message": message,
	}
