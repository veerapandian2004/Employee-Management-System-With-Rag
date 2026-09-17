# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

"""
SHIFT-BASED AUTOMATIC ATTENDANCE SERVICE
=========================================
Calculates employee daily attendance based on Shift Types, Shift Assignments,
and raw timestamped Employee Checkins (IN/OUT).

Features:
1. Normal Shifts (e.g. 09:00 - 17:00) & Overnight/Night Shifts (e.g. 22:00 - 06:00 next day)
2. Sequential chronological pairing of multiple IN/OUT check-in logs
3. Accurate working hours calculation
4. Late Entry & Early Exit grace period evaluation
5. Attendance status resolution: Present, Half Day, Absent, On Leave
6. Duplicate prevention & in-place update of existing Attendance records
7. Full Frappe ORM & MariaDB compatibility
8. Background job and scheduler tasks for automated processing
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
	time_diff_in_hours,
)


def _parse_time(val: Any) -> datetime.time:
	"""Converts timedelta, time object, or string HH:MM:SS into a datetime.time object."""
	if isinstance(val, datetime.time):
		return val
	if isinstance(val, datetime.timedelta):
		total_seconds = int(val.total_seconds())
		hours = (total_seconds // 3600) % 24
		minutes = (total_seconds % 3600) // 60
		seconds = total_seconds % 60
		return datetime.time(hours, minutes, seconds)
	if isinstance(val, str):
		parts = val.strip().split(":")
		hours = int(parts[0]) if len(parts) > 0 else 0
		minutes = int(parts[1]) if len(parts) > 1 else 0
		seconds = int(float(parts[2])) if len(parts) > 2 else 0
		return datetime.time(hours % 24, minutes % 60, seconds % 60)
	return datetime.time(0, 0, 0)


def get_active_shift_assignments(
	target_date: Union[datetime.date, str],
	employee: Optional[str] = None,
	shift_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
	"""
	Retrieves all Active Shift Assignments valid on target_date.
	Condition: status == 'Active' AND start_date <= target_date AND (end_date IS NULL OR end_date >= target_date)
	"""
	d = getdate(target_date)
	filters = {
		"status": "Active",
		"start_date": ["<=", d],
	}
	if employee:
		filters["employee"] = employee
	if shift_type:
		filters["shift_type"] = shift_type

	assignments = frappe.get_all(
		"Shift Assignment",
		fields=["name", "employee", "employee_name", "shift_type", "start_date", "end_date", "status"],
		filters=filters,
		order_by="start_date desc",
	)

	# Further filter out any assignments where end_date is set and < d
	valid_assignments = []
	for a in assignments:
		if a.get("end_date") and getdate(a["end_date"]) < d:
			continue
		valid_assignments.append(a)

	return valid_assignments


def resolve_employee_shift_type(
	employee_id: str,
	for_date: Optional[Union[datetime.date, str]] = None,
	auto_assign: bool = True,
) -> Optional[str]:
	"""
	Resolves the shift type for an employee on a given date with robust multi-level fallbacks:
	1. Direct active Shift Assignment covering for_date.
	2. Most recent active Shift Assignment for this employee.
	3. Shift logged on the employee's check-in punch.
	4. Company standard default shift ('Day Shift', 'Standard Day Shift', or first active Shift Type).
	5. If auto_assign=True and no Shift Assignment existed, dynamically creates an active
	   Shift Assignment to guarantee database referential integrity.
	"""
	if not employee_id:
		return None

	target_d = getdate(for_date) if for_date else getdate(nowdate())

	# 1. Direct active Shift Assignment covering target_d
	active = get_active_shift_assignments(target_d, employee=employee_id)
	if active:
		return active[0]["shift_type"]

	# 2. Most recent active Shift Assignment for this employee
	any_active = frappe.get_all(
		"Shift Assignment",
		filters={"employee": employee_id, "status": "Active"},
		fields=["shift_type"],
		order_by="start_date desc",
		limit=1,
	)
	if any_active and frappe.db.exists("Shift Type", any_active[0]["shift_type"]):
		return any_active[0]["shift_type"]

	# 3. Check latest checkin for this employee
	latest_chk = frappe.get_all(
		"Employee Checkin",
		filters={"employee": employee_id},
		fields=["shift"],
		order_by="time desc",
		limit=1,
	)
	if latest_chk and latest_chk[0].get("shift") and frappe.db.exists("Shift Type", latest_chk[0]["shift"]):
		return latest_chk[0]["shift"]

	# 4. Standard default Shift Type
	default_shift = None
	if frappe.db.exists("Shift Type", "Day Shift"):
		default_shift = "Day Shift"
	elif frappe.db.exists("Shift Type", "Standard Day Shift"):
		default_shift = "Standard Day Shift"
	else:
		active_types = frappe.get_all(
			"Shift Type",
			filters={"is_active": 1},
			fields=["name"],
			order_by="creation asc",
			limit=1,
		)
		if active_types:
			default_shift = active_types[0].name

	# 5. Optionally create persistent Shift Assignment if none exists
	if default_shift and auto_assign and frappe.db.exists("DocType", "Shift Assignment"):
		try:
			existing_sa = frappe.db.exists("Shift Assignment", {"employee": employee_id, "status": "Active"})
			if not existing_sa:
				sa_doc = frappe.get_doc({
					"doctype": "Shift Assignment",
					"employee": employee_id,
					"shift_type": default_shift,
					"start_date": "2026-01-01",
					"status": "Active",
				})
				sa_doc.insert(ignore_permissions=True)
				frappe.db.commit()
		except Exception as e:
			frappe.logger().warning(f"Could not auto-create Shift Assignment for {employee_id}: {e}")

	return default_shift


def get_shift_window(
	shift_type_doc: Any,
	attendance_date: Union[datetime.date, str],
) -> Tuple[datetime.datetime, datetime.datetime, datetime.datetime, datetime.datetime, bool]:
	"""
	Calculates the exact shift start, shift end, and checkin/checkout query window.
	Handles both Normal Day Shifts (e.g. 09:00 - 17:00) and Overnight Shifts (e.g. 22:00 - 06:00 next day).

	Returns:
	(shift_start, shift_end, window_start, window_end, is_overnight)
	"""
	att_date = getdate(attendance_date)
	start_time = _parse_time(shift_type_doc.get("start_time"))
	end_time = _parse_time(shift_type_doc.get("end_time"))

	# Determine if overnight (end_time earlier than or equal to start_time)
	is_overnight = end_time <= start_time

	shift_start = datetime.datetime.combine(att_date, start_time)
	if is_overnight:
		shift_end = datetime.datetime.combine(att_date + datetime.timedelta(days=1), end_time)
	else:
		shift_end = datetime.datetime.combine(att_date, end_time)

	# Check-in pre-window and post-window
	begin_before_mins = cint(shift_type_doc.get("begin_check_in_before_shift_start_time") or 60)
	allow_after_mins = cint(shift_type_doc.get("allow_check_out_after_shift_end_time") or 60)

	window_start = shift_start - datetime.timedelta(minutes=begin_before_mins)
	window_end = shift_end + datetime.timedelta(minutes=allow_after_mins)

	return shift_start, shift_end, window_start, window_end, is_overnight


def get_checkin_logs_for_window(
	employee: str,
	window_start: datetime.datetime,
	window_end: datetime.datetime,
) -> List[Dict[str, Any]]:
	"""
	Fetches all chronological Employee Checkin records for the employee within [window_start, window_end].
	Also ensures checkins on the target calendar date are covered so late or evening checkins are included.
	"""
	att_date = window_start.date()
	day_start = datetime.datetime.combine(att_date, datetime.time.min)
	day_end = datetime.datetime.combine(window_end.date(), datetime.time.max)
	q_start = min(window_start, day_start)
	q_end = max(window_end, day_end)

	logs = frappe.get_all(
		"Employee Checkin",
		fields=["name", "employee", "time", "log_type", "shift", "skip_auto_attendance"],
		filters={
			"employee": employee,
			"time": [
				"between",
				[
					q_start.strftime("%Y-%m-%d %H:%M:%S"),
					q_end.strftime("%Y-%m-%d %H:%M:%S"),
				],
			],
			"skip_auto_attendance": 0,
		},
		order_by="time asc",
	)
	return logs


def calculate_working_hours_from_checkins(
	checkin_logs: List[Dict[str, Any]],
) -> Dict[str, Any]:
	"""
	Processes chronological check-in logs and computes:
	- Sequential pairing of IN and OUT events (handling multiple IN/OUT pairs)
	- Consecutive INs: retains the first IN of consecutive arrivals
	- Total working hours (sum of all valid IN/OUT intervals)
	- First valid IN timestamp
	- Last valid OUT timestamp
	- Valid check-in presence boolean
	- Processed checkin doc names
	"""
	if not checkin_logs:
		return {
			"total_working_hours": 0.0,
			"first_in": None,
			"last_out": None,
			"has_valid_checkin": False,
			"intervals": [],
			"log_names": [],
		}

	# Ensure chronological order
	sorted_logs = sorted(checkin_logs, key=lambda x: get_datetime(x.get("time")))

	total_seconds = 0.0
	intervals = []
	log_names = [l.get("name") for l in sorted_logs if l.get("name")]

	current_in_time = None
	first_in = None
	last_out = None

	for log in sorted_logs:
		log_type = (log.get("log_type") or "").strip().upper()
		t = get_datetime(log.get("time"))

		if log_type == "IN":
			if first_in is None:
				first_in = t
			if current_in_time is None:
				current_in_time = t
			# If consecutive IN, maintain current_in_time (earliest arrival)

		elif log_type == "OUT":
			last_out = t
			if current_in_time is not None:
				duration_sec = (t - current_in_time).total_seconds()
				if duration_sec > 0:
					total_seconds += duration_sec
					intervals.append({
						"in": current_in_time,
						"out": t,
						"hours": round(duration_sec / 3600.0, 2),
					})
				current_in_time = None
			# If orphan OUT without preceding IN, ignored from working hours

	# If there was an IN but no OUT, check if first_in exists
	has_valid_checkin = first_in is not None
	is_currently_clocked_in = current_in_time is not None
	total_working_hours = round(total_seconds / 3600.0, 2)

	# If employee is currently clocked in, their active session has NO clock-out yet.
	# Do not return a previous session's OUT punch as the active session's last_out.
	effective_last_out = None if is_currently_clocked_in else last_out

	return {
		"total_working_hours": total_working_hours,
		"first_in": first_in,
		"last_out": effective_last_out,
		"has_valid_checkin": has_valid_checkin,
		"is_currently_clocked_in": is_currently_clocked_in,
		"intervals": intervals,
		"log_names": log_names,
	}


def ensure_shift_type_grace_periods():
	"""
	Ensures all Shift Types have a late_entry_grace_period of at least 30 minutes,
	and reconciles any existing Attendance records where clock-in occurred within 30 minutes of shift start.
	"""
	try:
		if frappe.db.exists("DocType", "Shift Type"):
			frappe.db.sql("""
				UPDATE `tabShift Type`
				SET late_entry_grace_period = 30
				WHERE late_entry_grace_period < 30 OR late_entry_grace_period IS NULL
			""")
			frappe.db.commit()

		if frappe.db.exists("DocType", "Attendance") and frappe.db.exists("DocType", "Shift Type"):
			frappe.db.sql("""
				UPDATE `tabAttendance` a
				INNER JOIN `tabShift Type` s ON (a.shift = s.name OR a.shift = s.shift_name)
				SET a.late_entry = 0,
				    a.remarks = REPLACE(a.remarks, ' | Late Entry', '')
				WHERE a.late_entry = 1
				  AND a.in_time IS NOT NULL
				  AND TIMESTAMPDIFF(MINUTE, CONCAT(a.attendance_date, ' ', s.start_time), a.in_time) <= 30
			""")
			frappe.db.commit()
	except Exception:
		pass


def evaluate_grace_periods(
	shift_type_doc: Any,
	shift_start: datetime.datetime,
	shift_end: datetime.datetime,
	first_in: Optional[datetime.datetime],
	last_out: Optional[datetime.datetime],
) -> Tuple[int, int]:
	"""
	Evaluates Late Entry and Early Exit flags against shift grace periods:
	- late_entry: 1 if first_in > shift_start + late_entry_grace_period minutes (default: 30 minutes).
	  Clocking in up to 30 minutes after shift start is NOT marked as late entry.
	- early_exit: 1 if last_out < shift_end - early_exit_grace_period minutes
	"""
	late_entry = 0
	early_exit = 0

	raw_grace = cint(shift_type_doc.get("late_entry_grace_period")) if shift_type_doc else 0
	# Standard: Clocking in within 30 minutes after shift start is NOT late entry
	late_grace = max(30, raw_grace) if raw_grace else 30
	early_grace = cint(shift_type_doc.get("early_exit_grace_period") or 15) if shift_type_doc else 15

	if first_in:
		late_cutoff = shift_start + datetime.timedelta(minutes=late_grace)
		if first_in > late_cutoff:
			late_entry = 1

	if last_out:
		early_cutoff = shift_end - datetime.timedelta(minutes=early_grace)
		if last_out < early_cutoff:
			early_exit = 1

	return late_entry, early_exit


def check_approved_leave(
	employee: str,
	attendance_date: Union[datetime.date, str],
) -> Tuple[bool, Optional[str], Optional[str]]:
	"""
	Checks if employee has an Approved Leave Application covering the attendance date.
	Returns: (is_on_leave, leave_application_name, leave_type)
	"""
	d = getdate(attendance_date)
	leaves = frappe.get_all(
		"Leave Application",
		fields=["name", "leave_type"],
		filters={
			"employee": employee,
			"status": "Approved",
			"from_date": ["<=", d],
			"to_date": [">=", d],
		},
		limit=1,
	)
	if leaves:
		return True, leaves[0].name, leaves[0].leave_type
	return False, None, None


def is_company_holiday(target_date: Union[datetime.date, str]) -> Tuple[bool, Optional[str]]:
	"""
	Checks whether target_date exists in the Company Holiday Calendar (tabHoliday).
	Returns: (is_holiday, holiday_name)
	"""
	d = getdate(target_date)
	if not frappe.db.exists("DocType", "Holiday"):
		return False, None
	holidays = frappe.get_all(
		"Holiday",
		filters={"holiday_date": d},
		fields=["name", "holiday_name"],
		limit=1,
	)
	if holidays:
		return True, holidays[0].holiday_name or holidays[0].name
	return False, None


def is_weekly_off_for_shift(
	shift_type_or_doc: Any,
	target_date: Union[datetime.date, str],
) -> bool:
	"""
	Determines whether target_date is a configured weekly off for the employee's shift.
	Defaults to Saturday, Sunday if not explicitly configured on the Shift Type.
	"""
	d = getdate(target_date)
	day_name = d.strftime("%A")  # e.g., 'Saturday', 'Sunday'

	if isinstance(shift_type_or_doc, str):
		if not frappe.db.exists("Shift Type", shift_type_or_doc):
			return day_name in ["Saturday", "Sunday"]
		shift_doc = frappe.get_cached_doc("Shift Type", shift_type_or_doc)
	else:
		shift_doc = shift_type_or_doc

	weekly_offs_str = shift_doc.get("weekly_off_days") if shift_doc else None
	if not weekly_offs_str:
		weekly_offs_str = "Saturday, Sunday"

	off_days = [w.strip().lower() for w in weekly_offs_str.split(",") if w.strip()]
	return day_name.lower() in off_days


STATUS_PRIORITY = {
	"Holiday": 70,
	"Weekly Off": 60,
	"On Leave": 50,
	"Present": 40,
	"Half Day": 20,
	"Absent": 10,
}


def determine_attendance_status(
	shift_type_doc: Any,
	working_hours: float,
	has_valid_checkin: bool,
	is_on_leave: bool = False,
	is_holiday: bool = False,
	is_weekly_off: bool = False,
	is_currently_clocked_in: bool = False,
) -> str:
	"""
	Determines the Attendance status according to strict enterprise priority rules:
	Holiday > Weekly Off > Approved Leave > Present > Half Day > Absent

	An employee must never be marked Absent if the date is an approved holiday,
	weekly off, or approved leave.
	"""
	# Priority 1: Holiday
	if is_holiday:
		return "Holiday"

	# Priority 2: Weekly Off
	if is_weekly_off:
		return "Weekly Off"

	# Priority 3: Approved Leave
	if is_on_leave:
		present_thresh = flt(shift_type_doc.get("working_hours_threshold_for_present") or 8.0)
		if working_hours >= present_thresh:
			return "Present"
		return "On Leave"

	# Priority 4: No valid check-in on a normal working day -> Absent
	if not has_valid_checkin:
		return "Absent"

	# If the employee is currently clocked in (working on active shift right now)
	if is_currently_clocked_in:
		return "Present"

	# Working hours thresholds
	half_day_thresh = flt(shift_type_doc.get("working_hours_threshold_for_half_day") or 4.0)
	present_thresh = flt(shift_type_doc.get("working_hours_threshold_for_present") or 8.0)

	if working_hours < half_day_thresh:
		return "Half Day" if has_valid_checkin else "Absent"
	elif working_hours < present_thresh:
		return "Half Day"
	else:
		return "Present"


def upsert_attendance_record(
	employee: str,
	attendance_date: Union[datetime.date, str],
	status: str,
	shift: Optional[str] = None,
	in_time: Optional[datetime.datetime] = None,
	out_time: Optional[datetime.datetime] = None,
	working_hours: float = 0.0,
	late_entry: int = 0,
	early_exit: int = 0,
	leave_application: Optional[str] = None,
	leave_type: Optional[str] = None,
	remarks: Optional[str] = None,
	checkin_names: Optional[List[str]] = None,
	auto_clocked_out: Optional[int] = None,
	clock_out_reason: Optional[str] = None,
	auto_clock_out_time: Optional[datetime.datetime] = None,
	force_status: bool = False,
	office_location: Optional[str] = None,
) -> Dict[str, Any]:
	"""
	Upserts an Attendance record into tabAttendance.
	DUPLICATE PREVENTION & STATUS PRIORITY GUARD:
	1. Queries MariaDB for existing record for (employee, attendance_date).
	2. If existing: prevents lower-priority status from overwriting higher-priority status.
	3. If non-existing: inserts a new Attendance document.
	4. Updates linked Employee Checkin records with the Attendance ID.
	"""
	d = getdate(attendance_date)
	existing_name = frappe.db.get_value(
		"Attendance",
		{"employee": employee, "attendance_date": d},
		"name",
	)

	emp_name = frappe.db.get_value("Employee", employee, "full_name") or employee

	# Enforce Status Priority:
	# Holiday (70) > Weekly Off (60) > On Leave (50) > Present (40) > Half Day (20) > Absent (10)
	if existing_name and not force_status:
		existing_status = frappe.db.get_value("Attendance", existing_name, "status")
		existing_prio = STATUS_PRIORITY.get(existing_status, 0)
		new_prio = STATUS_PRIORITY.get(status, 0)
		if existing_prio > new_prio:
			status = existing_status
			if existing_status == "On Leave" and not leave_application:
				leave_application = frappe.db.get_value("Attendance", existing_name, "leave_application")
				leave_type = frappe.db.get_value("Attendance", existing_name, "leave_type")

	data = {
		"employee": employee,
		"employee_name": emp_name,
		"attendance_date": d,
		"status": status,
		"shift": shift,
		"in_time": in_time.strftime("%Y-%m-%d %H:%M:%S") if in_time else None,
		"out_time": out_time.strftime("%Y-%m-%d %H:%M:%S") if out_time else None,
		"working_hours": round(flt(working_hours), 2),
		"late_entry": cint(late_entry),
		"early_exit": cint(early_exit),
		"leave_application": leave_application,
		"leave_type": leave_type,
		"remarks": remarks or f"Auto calculated via Shift Attendance on {now_datetime().strftime('%Y-%m-%d %H:%M:%S')}",
	}

	# Persist office_location
	if office_location:
		data["office_location"] = office_location
	elif checkin_names:
		try:
			first_chk = frappe.get_all(
				"Employee Checkin",
				filters={"name": ["in", checkin_names]},
				fields=["office_location"],
				order_by="time asc",
				limit=1,
			)
			if first_chk and first_chk[0].get("office_location"):
				data["office_location"] = first_chk[0].get("office_location")
		except Exception:
			pass

	if out_time is None:
		data["out_time"] = None
		data["auto_clocked_out"] = 0
		data["clock_out_reason"] = None
		data["auto_clock_out_time"] = None
	else:
		# Detect or assign auto clock out tracking
		if auto_clocked_out is not None:
			data["auto_clocked_out"] = cint(auto_clocked_out)
		if clock_out_reason is not None:
			data["clock_out_reason"] = clock_out_reason
		if auto_clock_out_time is not None:
			data["auto_clock_out_time"] = (
				auto_clock_out_time.strftime("%Y-%m-%d %H:%M:%S")
				if hasattr(auto_clock_out_time, "strftime")
				else str(auto_clock_out_time)
			)

		# Auto-propagate from checkin logs if not explicitly passed
		if auto_clocked_out is None and checkin_names:
			try:
				auto_checkins = frappe.get_all(
					"Employee Checkin",
					filters={"name": ["in", checkin_names], "is_auto_clock_out": 1, "log_type": "OUT"},
					fields=["name", "clock_out_reason", "time"],
					order_by="time desc",
					limit=1,
				)
				if auto_checkins:
					data["auto_clocked_out"] = 1
					data["clock_out_reason"] = auto_checkins[0].get("clock_out_reason")
					data["auto_clock_out_time"] = str(auto_checkins[0].get("time"))
			except Exception:
				pass

	if existing_name:
		doc = frappe.get_doc("Attendance", existing_name)
		doc.update(data)
		doc.save(ignore_permissions=True)
		if data.get("out_time") is None:
			frappe.db.set_value("Attendance", existing_name, {
				"out_time": None,
				"auto_clocked_out": 0,
				"clock_out_reason": None,
				"auto_clock_out_time": None,
			}, update_modified=False)
		action = "updated"
	else:
		doc = frappe.get_doc({"doctype": "Attendance", **data})
		doc.insert(ignore_permissions=True)
		action = "created"

	frappe.db.commit()

	# Link processed checkin logs to this attendance record
	if checkin_names:
		for cname in checkin_names:
			if cname:
				frappe.db.set_value("Employee Checkin", cname, "attendance", doc.name, update_modified=False)
		frappe.db.commit()

	return {
		"attendance_id": doc.name,
		"action": action,
		"employee": employee,
		"employee_name": emp_name,
		"attendance_date": str(d),
		"status": status,
		"shift": shift,
		"working_hours": round(flt(working_hours), 2),
		"late_entry": cint(late_entry),
		"early_exit": cint(early_exit),
		"in_time": str(in_time) if in_time else None,
		"out_time": str(out_time) if out_time else None,
		"auto_clocked_out": cint(data.get("auto_clocked_out", 0)),
		"clock_out_reason": data.get("clock_out_reason"),
		"auto_clock_out_time": data.get("auto_clock_out_time"),
	}


def process_attendance_for_employee_shift(
	employee: str,
	shift_type_name: str,
	attendance_date: Union[datetime.date, str],
	force_status: bool = False,
) -> Dict[str, Any]:
	"""
	Executes full calculation pipeline for a single employee shift on attendance_date:
	1. Check Holiday in Holiday Calendar
	2. Check Weekly Off for Shift
	3. Check Approved Leave
	4. Fetch checkins & calculate working hours & pairs
	5. Check grace periods (late / early)
	6. Determine status with strict priority:
	   Holiday > Weekly Off > Approved Leave > Present > Late Entry > Half Day > Absent
	7. Upsert tabAttendance idempotently
	"""
	if not frappe.db.exists("Shift Type", shift_type_name):
		raise frappe.ValidationError(_("Shift Type '{0}' does not exist").format(shift_type_name))

	shift_doc = frappe.get_doc("Shift Type", shift_type_name)

	# 1. Check Holiday Calendar
	is_holiday, holiday_name = is_company_holiday(attendance_date)

	# 2. Check Weekly Off
	is_weekly_off = is_weekly_off_for_shift(shift_doc, attendance_date)

	# 3. Check Approved Leave
	is_on_leave, leave_app, leave_type = check_approved_leave(employee, attendance_date)

	# 4. Compute shift time window (handles normal & overnight)
	shift_start, shift_end, window_start, window_end, is_overnight = get_shift_window(
		shift_doc, attendance_date
	)

	# 5. Fetch check-in logs in window
	logs = get_checkin_logs_for_window(employee, window_start, window_end)

	# 6. Calculate working hours from pairs
	calc_res = calculate_working_hours_from_checkins(logs)
	total_working_hours = calc_res["total_working_hours"]
	first_in = calc_res["first_in"]
	last_out = calc_res["last_out"]
	has_valid_checkin = calc_res["has_valid_checkin"]
	log_names = calc_res["log_names"]

	# 7. Evaluate grace periods
	late_entry, early_exit = evaluate_grace_periods(
		shift_doc, shift_start, shift_end, first_in, last_out
	)

	# 8. Determine status adhering strictly to priority:
	# Holiday > Weekly Off > Approved Leave > Present > Half Day > Absent
	status = determine_attendance_status(
		shift_type_doc=shift_doc,
		working_hours=total_working_hours,
		has_valid_checkin=has_valid_checkin,
		is_on_leave=is_on_leave,
		is_holiday=is_holiday,
		is_weekly_off=is_weekly_off,
		is_currently_clocked_in=calc_res.get("is_currently_clocked_in", False),
	)

	# Build remarks
	if is_holiday:
		remarks = f"Company Holiday: {holiday_name or 'Holiday'}"
		if has_valid_checkin:
			remarks += f" (Punches recorded: {total_working_hours} hrs)"
	elif is_weekly_off:
		remarks = f"Weekly Off: {getdate(attendance_date).strftime('%A')}"
		if has_valid_checkin:
			remarks += f" (Punches recorded: {total_working_hours} hrs)"
	elif is_on_leave:
		remarks = f"Shift: {shift_type_name} | Approved Leave ({leave_type})"
	else:
		remarks = f"Shift: {shift_type_name} ({shift_doc.start_time} - {shift_doc.end_time})"
		if is_overnight:
			remarks += " [Overnight]"
		if late_entry:
			remarks += " | Late Entry"
		if early_exit:
			remarks += " | Early Exit"

	# 9. Upsert to Attendance (Duplicate prevention & priority guard)
	is_clocked_in_now = calc_res.get("is_currently_clocked_in", False)
	effective_out = None if is_clocked_in_now else last_out

	upsert_res = upsert_attendance_record(
		employee=employee,
		attendance_date=attendance_date,
		status=status,
		shift=shift_type_name,
		in_time=first_in,
		out_time=effective_out,
		working_hours=total_working_hours,
		late_entry=late_entry,
		early_exit=early_exit,
		leave_application=leave_app,
		leave_type=leave_type,
		remarks=remarks,
		checkin_names=log_names,
		auto_clocked_out=0 if is_clocked_in_now else None,
		force_status=force_status,
	)

	return upsert_res


def process_auto_attendance_for_date(
	target_date: Optional[Union[datetime.date, str]] = None,
	shift_type_name: Optional[str] = None,
	employee: Optional[str] = None,
) -> List[Dict[str, Any]]:
	"""
	Calculates automatic attendance for all active shift assignments on target_date.
	Default target_date is today.
	"""
	ensure_shift_type_grace_periods()
	d = getdate(target_date) if target_date else getdate(nowdate())
	assignments = get_active_shift_assignments(
		target_date=d,
		employee=employee,
		shift_type=shift_type_name,
	)

	results = []
	for a in assignments:
		emp = a["employee"]
		shift_name = a["shift_type"]
		try:
			res = process_attendance_for_employee_shift(
				employee=emp,
				shift_type_name=shift_name,
				attendance_date=d,
			)
			results.append(res)
		except Exception as e:
			frappe.log_error(
				title=f"Auto Attendance Error for {emp} on {d}",
				message=str(e),
			)
			results.append({
				"employee": emp,
				"attendance_date": str(d),
				"status": "Error",
				"error": str(e),
			})

	return results


def process_auto_attendance_job():
	"""
	Scheduler / Background Job Entrypoint:
	Processes attendance for both yesterday and today.
	Ensures overnight shifts that finish in the morning of today are reconciled for yesterday's shift date,
	and ongoing day shifts are updated for today.
	"""
	today = getdate(nowdate())
	yesterday = today - datetime.timedelta(days=1)

	# Process yesterday (to finalize overnight shifts and full-day logs)
	res_yesterday = process_auto_attendance_for_date(target_date=yesterday)

	# Process today (for ongoing tracking)
	res_today = process_auto_attendance_for_date(target_date=today)

	return {
		"yesterday": len(res_yesterday),
		"today": len(res_today),
		"timestamp": str(now_datetime()),
	}


def process_auto_attendance_daily():
	"""
	Daily scheduler task:
	Runs complete reconciliation for the past 3 days to capture any retroactive check-in syncing.
	"""
	today = getdate(nowdate())
	results = {}
	for offset in [2, 1, 0]:
		d = today - datetime.timedelta(days=offset)
		res = process_auto_attendance_for_date(target_date=d)
		results[str(d)] = len(res)
	return results

