# Copyright (c) 2026, veera and contributors
# For license information, please see license.txt

import math
import frappe
from frappe import _
from frappe.utils import flt

# Mean Earth radius in meters
EARTH_RADIUS_METERS = 6371000.0


def validate_coordinates(latitude, longitude):
	"""
	Validates that latitude and longitude are valid numeric floats
	within standard geographic bounds:
	- Latitude: -90.0 to 90.0
	- Longitude: -180.0 to 180.0
	"""
	if latitude is None or longitude is None:
		frappe.throw(_("GPS coordinates (latitude and longitude) are required."))

	try:
		lat = float(latitude)
		lon = float(longitude)
	except (ValueError, TypeError):
		frappe.throw(_("Invalid GPS coordinates: latitude and longitude must be valid floating point numbers."))

	if math.isnan(lat) or math.isinf(lat) or not (-90.0 <= lat <= 90.0):
		frappe.throw(_(f"Invalid latitude {lat}. Must be between -90.0 and 90.0 degrees."))

	if math.isnan(lon) or math.isinf(lon) or not (-180.0 <= lon <= 180.0):
		frappe.throw(_(f"Invalid longitude {lon}. Must be between -180.0 and 180.0 degrees."))

	return lat, lon


def haversine_distance(lat1, lon1, lat2, lon2):
	"""
	Calculates the great-circle distance between two points on the Earth's surface
	using the Haversine formula.
	
	Returns distance in meters rounded to 2 decimal places.
	"""
	lat1_rad = math.radians(float(lat1))
	lon1_rad = math.radians(float(lon1))
	lat2_rad = math.radians(float(lat2))
	lon2_rad = math.radians(float(lon2))

	delta_lat = lat2_rad - lat1_rad
	delta_lon = lon2_rad - lon1_rad

	a = (
		math.sin(delta_lat / 2.0) ** 2
		+ math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2.0) ** 2
	)
	c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

	distance = EARTH_RADIUS_METERS * c
	return round(distance, 2)


def validate_gps_accuracy(accuracy, max_accuracy=50.0):
	"""
	Validates that the reported GPS accuracy reading is acceptable.
	Rejects low-quality readings where accuracy is worse (larger number)
	than the configured threshold.
	"""
	if accuracy is None:
		frappe.throw(_("GPS accuracy reading is required."))

	try:
		acc = float(accuracy)
	except (ValueError, TypeError):
		frappe.throw(_("Invalid GPS accuracy reading. Must be a numeric value in meters."))

	if math.isnan(acc) or math.isinf(acc) or acc < 0:
		frappe.throw(_("Invalid GPS accuracy reading."))

	max_acc = float(max_accuracy) if max_accuracy else 50.0

	if acc > max_acc:
		frappe.throw(
			_("Location accuracy is too low. Please move to an open area and try again."),
			title=_("Low GPS Accuracy"),
		)

	return round(acc, 2)


def validate_office_radius(emp_lat, emp_lon, office_lat, office_lon, allowed_radius=150.0, office_name="Office"):
	"""
	Calculates the distance between the employee's GPS position and the office,
	and verifies that the employee is physically inside the authorized radius.
	"""
	distance = haversine_distance(emp_lat, emp_lon, office_lat, office_lon)
	radius = flt(allowed_radius) if allowed_radius else 150.0

	if distance > radius:
		frappe.throw(
			_(
				f"You are outside the authorized office radius for {office_name}. "
				f"Your distance is {distance:.1f} meters, but the allowed radius is {radius:.0f} meters."
			),
			title=_("Outside Office Location"),
		)

	return distance

