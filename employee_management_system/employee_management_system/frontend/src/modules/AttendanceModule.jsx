import { useState, useEffect } from "react";
import {
  CalendarCheck,
  Plus,
  Search,
  Edit,
  Trash2,
  RefreshCw,
  Clock,
  LogIn,
  LogOut,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { Dialog } from "../components/ui/dialog";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "../components/ui/table";
import {
  apiRecalculateAttendance,
  apiEmployeeCheckin,
  apiEmployeeCheckout,
  apiFetchShiftTypes,
  apiClockIn,
  apiClockOut,
} from "../services/apiService";
import { GpsClockWidget } from "../components/GpsClockWidget";

export function AttendanceModule({
  attendance = [],
  employees = [],
  userRole = "Administrator",
  currentUser = null,
  onRefreshData,
  onAddAttendance,
  onUpdateAttendance,
  onDeleteAttendance,
}) {
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [editingAtt, setEditingAtt] = useState(null);
  const [filterStatus, setFilterStatus] = useState("ALL");
  const [filterShift, setFilterShift] = useState("ALL");
  const [filterDate, setFilterDate] = useState("");
  const [search, setSearch] = useState("");
  const [shiftTypes, setShiftTypes] = useState([]);
  const [isRecalculating, setIsRecalculating] = useState(false);
  const [widgetRefreshKey, setWidgetRefreshKey] = useState(0);
  const [actionMessage, setActionMessage] = useState(null);

  useEffect(() => {
    async function loadShifts() {
      try {
        const types = await apiFetchShiftTypes();
        if (Array.isArray(types)) {
          setShiftTypes(types);
        }
      } catch (err) {
        console.warn("Failed to load shift types:", err);
      }
    }
    loadShifts();
  }, []);

  const showNotification = (text, type = "success") => {
    setActionMessage({ text, type });
    setTimeout(() => {
      setActionMessage(null);
    }, 4000);
  };

  const initialForm = {
    employee: employees[0]?.naming_series || employees[0]?.name || "EMP-001",
    employee_name: employees[0]?.full_name || "",
    attendance_date: new Date().toISOString().split("T")[0],
    status: "Present",
    check_in: "09:00 AM",
    check_out: "05:00 PM",
    shift: shiftTypes[0]?.shift_name || "Day Shift",
    working_hours: 8.0,
    late_entry: 0,
    early_exit: 0,
    remarks: "",
  };

  const [formData, setFormData] = useState(initialForm);

  const handleOpenAdd = () => {
    setFormData({
      ...initialForm,
      employee: employees[0]?.naming_series || employees[0]?.name || "EMP-001",
      employee_name: employees[0]?.full_name || "",
      shift: shiftTypes[0]?.shift_name || "Day Shift",
    });
    setEditingAtt(null);
    setIsAddOpen(true);
  };

  const handleOpenEdit = (att) => {
    setEditingAtt(att);
    setFormData({ ...att });
    setIsAddOpen(true);
  };

  const handleSave = (e) => {
    e.preventDefault();
    if (!formData.employee) return;

    if (editingAtt) {
      onUpdateAttendance(formData);
      showNotification("Attendance record updated successfully!");
    } else {
      onAddAttendance({
        ...formData,
        name: `ATT-${String(attendance.length + 1).padStart(3, "0")}`,
      });
      showNotification("Attendance record logged successfully!");
    }
    setIsAddOpen(false);
  };

  const handleRecalculate = async () => {
    setIsRecalculating(true);
    try {
      const res = await apiRecalculateAttendance(filterDate || null);
      showNotification(
        res?.message || "Shift attendance recalculation completed successfully!",
        "success"
      );
      setWidgetRefreshKey((k) => k + 1);
      window.dispatchEvent(new CustomEvent("attendance-status-changed"));
      if (onRefreshData) {
        await onRefreshData();
      }
    } catch (err) {
      showNotification(err?.message || "Recalculation failed", "error");
    } finally {
      setIsRecalculating(false);
    }
  };

  const handleClockIn = async () => {
    try {
      let res;
      try {
        const coords = await new Promise((resolve, reject) => {
          if (!navigator.geolocation) return reject(new Error("No geolocation"));
          navigator.geolocation.getCurrentPosition(
            (pos) => resolve(pos.coords),
            (err) => reject(err),
            { enableHighAccuracy: true, timeout: 5000, maximumAge: 10000 }
          );
        });
        res = await apiClockIn({
          latitude: coords.latitude,
          longitude: coords.longitude,
          accuracy: coords.accuracy,
        });
      } catch {
        res = await apiEmployeeCheckin();
      }
      const tStr = res?.time ? new Date(res.time).toLocaleTimeString() : "now";
      showNotification(`Clocked IN successfully at ${tStr}!`, "success");
      setWidgetRefreshKey((k) => k + 1);
      window.dispatchEvent(new CustomEvent("attendance-status-changed"));
      if (onRefreshData) {
        await onRefreshData();
      }
    } catch (err) {
      showNotification(err?.message || "Clock-in failed", "error");
    }
  };

  const handleClockOut = async () => {
    try {
      let res;
      try {
        const coords = await new Promise((resolve, reject) => {
          if (!navigator.geolocation) return reject(new Error("No geolocation"));
          navigator.geolocation.getCurrentPosition(
            (pos) => resolve(pos.coords),
            (err) => reject(err),
            { enableHighAccuracy: true, timeout: 5000, maximumAge: 10000 }
          );
        });
        res = await apiClockOut({
          latitude: coords.latitude,
          longitude: coords.longitude,
          accuracy: coords.accuracy,
        });
      } catch {
        res = await apiEmployeeCheckout();
      }
      const tStr = res?.time ? new Date(res.time).toLocaleTimeString() : "now";
      showNotification(`Clocked OUT successfully at ${tStr}!`, "success");
      setWidgetRefreshKey((k) => k + 1);
      window.dispatchEvent(new CustomEvent("attendance-status-changed"));
      if (onRefreshData) {
        await onRefreshData();
      }
    } catch (err) {
      showNotification(err?.message || "Clock-out failed", "error");
    }
  };

  const filteredAttendance = attendance.filter((a) => {
    const matchesSearch =
      a.employee_name?.toLowerCase().includes(search.toLowerCase()) ||
      a.employee?.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = filterStatus === "ALL" || a.status === filterStatus;
    const matchesShift = filterShift === "ALL" || a.shift === filterShift;
    const matchesDate = !filterDate || a.attendance_date === filterDate;

    return matchesSearch && matchesStatus && matchesShift && matchesDate;
  });

  const presentCount = attendance.filter((a) => a.status === "Present").length;
  const lateCount = attendance.filter(
    (a) => a.status === "Late" || a.late_entry === 1 || a.late_entry === true
  ).length;
  const absentCount = attendance.filter((a) => a.status === "Absent").length;
  const leaveCount = attendance.filter((a) => a.status === "On Leave").length;
  const halfDayCount = attendance.filter((a) => a.status === "Half Day").length;

  const isAdminOrHR = userRole === "Administrator" || userRole === "HR";

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header and Action Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center space-x-2">
            <CalendarCheck className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
            <span>Shift-Based Attendance</span>
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Automated workforce tracking with Shift Types, IN/OUT pairings, grace periods, and night shifts
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Quick Clock IN / OUT (Employees & HR only) */}
          {userRole !== "Administrator" && (
            <>
              <Button
                onClick={handleClockIn}
                variant="outline"
                className="border-emerald-600 text-emerald-700 hover:bg-emerald-50 dark:border-emerald-500 dark:text-emerald-400 font-medium shadow-sm text-xs h-9 cursor-pointer"
              >
                <LogIn className="mr-1.5 h-3.5 w-3.5 text-emerald-600" /> Clock IN
              </Button>
              <Button
                onClick={handleClockOut}
                variant="outline"
                className="border-amber-600 text-amber-700 hover:bg-amber-50 dark:border-amber-500 dark:text-amber-400 font-medium shadow-sm text-xs h-9 cursor-pointer"
              >
                <LogOut className="mr-1.5 h-3.5 w-3.5 text-amber-600" /> Clock OUT
              </Button>
            </>
          )}

          {/* Admin Recalculate */}
          {isAdminOrHR && (
            <Button
              onClick={handleRecalculate}
              disabled={isRecalculating}
              variant="outline"
              className="bg-white hover:bg-slate-50 font-semibold shadow-sm text-xs h-9"
            >
              <RefreshCw
                className={`mr-1.5 h-3.5 w-3.5 text-indigo-600 ${
                  isRecalculating ? "animate-spin" : ""
                }`}
              />
              {isRecalculating ? "Calculating..." : "Recalculate Shifts"}
            </Button>
          )}

          {isAdminOrHR && (
            <Button
              onClick={handleOpenAdd}
              className="bg-indigo-600 hover:bg-indigo-700 font-semibold shadow-md text-xs h-9"
            >
              <Plus className="mr-1.5 h-3.5 w-3.5" /> Mark Record
            </Button>
          )}
        </div>
      </div>

      {/* Notification Banner */}
      {actionMessage && (
        <div
          className={`p-3 rounded-lg flex items-center space-x-2 text-sm transition-all duration-300 ${
            actionMessage.type === "error"
              ? "bg-rose-50 text-rose-800 border border-rose-200 dark:bg-rose-950/40 dark:text-rose-300"
              : "bg-emerald-50 text-emerald-800 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300"
          }`}
        >
          {actionMessage.type === "error" ? (
            <AlertCircle className="h-4 w-4 shrink-0" />
          ) : (
            <CheckCircle2 className="h-4 w-4 shrink-0" />
          )}
          <span>{actionMessage.text}</span>
        </div>
      )}

      {/* GPS Clock IN / OUT Attendance Widget (Employees & HR only) */}
      {userRole !== "Administrator" && (
        <GpsClockWidget
          onAttendanceUpdated={onRefreshData}
          refreshTrigger={widgetRefreshKey}
        />
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <Card className="border-l-4 border-l-emerald-500">
          <CardContent className="p-4">
            <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">
              Full-Day Present
            </p>
            <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">
              {presentCount}
            </h3>
          </CardContent>
        </Card>
        <Card className="border-l-4 border-l-amber-500">
          <CardContent className="p-4">
            <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">
              Late Entries
            </p>
            <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">
              {lateCount}
            </h3>
          </CardContent>
        </Card>
        <Card className="border-l-4 border-l-indigo-500">
          <CardContent className="p-4">
            <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">
              Half Day
            </p>
            <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">
              {halfDayCount}
            </h3>
          </CardContent>
        </Card>
        <Card className="border-l-4 border-l-rose-500">
          <CardContent className="p-4">
            <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">
              Absent
            </p>
            <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">
              {absentCount}
            </h3>
          </CardContent>
        </Card>
        <Card className="border-l-4 border-l-blue-500">
          <CardContent className="p-4">
            <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">
              On Approved Leave
            </p>
            <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">
              {leaveCount}
            </h3>
          </CardContent>
        </Card>
      </div>

      {/* Toolbar Filter */}
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative w-full sm:w-60">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <Input
              placeholder="Search employee..."
              className="pl-9 text-sm"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <Select
            className="w-full sm:w-36 text-sm"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
          >
            <option value="ALL">All Status</option>
            <option value="Present">Present</option>
            <option value="Half Day">Half Day</option>
            <option value="Absent">Absent</option>
            <option value="On Leave">On Leave</option>
          </Select>

          <Select
            className="w-full sm:w-40 text-sm"
            value={filterShift}
            onChange={(e) => setFilterShift(e.target.value)}
          >
            <option value="ALL">All Shifts</option>
            {shiftTypes.map((st) => (
              <option key={st.name || st.shift_name} value={st.shift_name || st.name}>
                {st.shift_name || st.name}
              </option>
            ))}
          </Select>

          <Input
            type="date"
            className="w-full sm:w-40 text-sm"
            value={filterDate}
            onChange={(e) => setFilterDate(e.target.value)}
          />

          {filterDate && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setFilterDate("")}
              className="text-xs"
            >
              Clear Date
            </Button>
          )}
        </div>
      </Card>

      {/* Attendance Table */}
      <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Employee</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Shift</TableHead>
              <TableHead>Office</TableHead>
              <TableHead>Check-In</TableHead>
              <TableHead>Check-Out</TableHead>
              <TableHead>Hours</TableHead>
              <TableHead>Status & Flags</TableHead>
              <TableHead>Remarks</TableHead>
              {isAdminOrHR && <TableHead className="text-right">Actions</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredAttendance.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={isAdminOrHR ? 10 : 9}
                  className="text-center py-8 text-slate-400 text-sm"
                >
                  No attendance records found matching filters.
                </TableCell>
              </TableRow>
            ) : (
              filteredAttendance.map((att, idx) => {
                const isLate =
                  att.late_entry === 1 ||
                  att.late_entry === "1" ||
                  att.late_entry === true ||
                  att.status === "Late";
                const isEarlyExit =
                  att.early_exit === 1 ||
                  att.early_exit === "1" ||
                  att.early_exit === true;

                return (
                  <TableRow key={att.name || att.id || `att-${att.employee}-${att.attendance_date}-${idx}`}>
                    <TableCell>
                      <div className="font-semibold text-slate-900 dark:text-slate-100">
                        {att.employee_name || att.employee}
                      </div>
                      <div className="text-xs text-slate-400 dark:text-slate-500 font-mono">
                        {att.employee}
                      </div>
                    </TableCell>
                    <TableCell className="font-medium text-slate-700 dark:text-slate-300 whitespace-nowrap">
                      {att.attendance_date}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="font-normal">
                        {att.shift || "Standard"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-slate-600 dark:text-slate-400 whitespace-nowrap">
                      {att.office_location ? (
                        <span className="inline-flex items-center font-medium text-slate-700 dark:text-slate-300">
                          {att.office_location}
                        </span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-slate-600 dark:text-slate-400 whitespace-nowrap">
                      {att.check_in || "-"}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-slate-600 dark:text-slate-400 whitespace-nowrap">
                      {att.check_out || "-"}
                    </TableCell>
                    <TableCell className="font-mono text-xs font-semibold text-slate-700 dark:text-slate-300">
                      {att.working_hours !== undefined && att.working_hours !== null
                        ? `${att.working_hours} hrs`
                        : "-"}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap items-center gap-1">
                        <Badge
                          variant={
                            att.status === "Present"
                              ? "success"
                              : att.status === "Half Day"
                              ? "warning"
                              : att.status === "Absent"
                              ? "destructive"
                              : "secondary"
                          }
                        >
                          {att.status}
                        </Badge>
                        {Boolean(att.auto_clocked_out) && (
                          <span
                            className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-indigo-100 text-indigo-800 dark:bg-indigo-950/60 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-900"
                            title={`Auto Clock-Out: ${att.clock_out_reason || "Scheduled Shift End"}`}
                          >
                            Auto Clock-Out
                          </span>
                        )}
                        {isLate && (
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200 dark:border-amber-900">
                            Late Entry
                          </span>
                        )}
                        {isEarlyExit && (
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-orange-100 text-orange-800 dark:bg-orange-950/60 dark:text-orange-300 border border-orange-200 dark:border-orange-900">
                            Early Exit
                          </span>
                        )}
                        {att.clock_out_reason && (
                          <span
                            className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border ${
                              att.clock_out_reason === "Left Office Location"
                                ? "bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800"
                                : "bg-blue-100 text-blue-900 border-blue-300 dark:bg-blue-950/60 dark:text-blue-300 dark:border-blue-800"
                            }`}
                            title={`Automatic Clock-Out: ${att.clock_out_reason}`}
                          >
                            {att.clock_out_reason}
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-xs text-slate-500 dark:text-slate-400 max-w-xs truncate">
                      {att.remarks || "-"}
                    </TableCell>
                    {isAdminOrHR && (
                      <TableCell className="text-right space-x-2 whitespace-nowrap">
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 text-xs"
                          onClick={() => handleOpenEdit(att)}
                        >
                          <Edit className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-8 text-xs text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40"
                          onClick={() => onDeleteAttendance(att.name)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </TableCell>
                    )}
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      {/* Add/Edit Modal */}
      <Dialog
        isOpen={isAddOpen}
        onClose={() => setIsAddOpen(false)}
        title={editingAtt ? "Edit Attendance Record" : "Mark Attendance Record"}
        description="Configure attendance details according to Shift Type and Attendance DocType."
        maxWidth="max-w-lg"
      >
        <form onSubmit={handleSave} className="space-y-4 py-2">
          <div>
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
              Employee *
            </label>
            <Select
              value={formData.employee}
              onChange={(e) => {
                const emp = employees.find(
                  (x) => x.naming_series === e.target.value || x.name === e.target.value
                );
                setFormData({
                  ...formData,
                  employee: e.target.value,
                  employee_name: emp ? emp.full_name : "",
                });
              }}
              required
            >
              {employees.map((emp) => (
                <option
                  key={emp.naming_series || emp.name}
                  value={emp.naming_series || emp.name}
                >
                  {emp.full_name} ({emp.naming_series || emp.name})
                </option>
              ))}
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Attendance Date *
              </label>
              <Input
                type="date"
                value={formData.attendance_date}
                onChange={(e) =>
                  setFormData({ ...formData, attendance_date: e.target.value })
                }
                required
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Shift
              </label>
              <Select
                value={formData.shift}
                onChange={(e) => setFormData({ ...formData, shift: e.target.value })}
              >
                {shiftTypes.length > 0 ? (
                  shiftTypes.map((st) => (
                    <option key={st.name} value={st.shift_name || st.name}>
                      {st.shift_name || st.name}
                    </option>
                  ))
                ) : (
                  <>
                    <option value="Day Shift">Day Shift</option>
                    <option value="Night Shift">Night Shift</option>
                  </>
                )}
              </Select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Status
              </label>
              <Select
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value })}
              >
                <option value="Present">Present</option>
                <option value="Half Day">Half Day</option>
                <option value="Absent">Absent</option>
                <option value="On Leave">On Leave</option>
              </Select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Working Hours
              </label>
              <Input
                type="number"
                step="0.1"
                placeholder="8.0"
                value={formData.working_hours ?? 8.0}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    working_hours: parseFloat(e.target.value) || 0,
                  })
                }
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Check-in Time
              </label>
              <Input
                placeholder="09:00 AM"
                value={formData.check_in || ""}
                onChange={(e) => setFormData({ ...formData, check_in: e.target.value })}
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Check-out Time
              </label>
              <Input
                placeholder="05:00 PM"
                value={formData.check_out || ""}
                onChange={(e) => setFormData({ ...formData, check_out: e.target.value })}
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
              Remarks
            </label>
            <Input
              placeholder="e.g. On-time, Shift completed, Approved leave"
              value={formData.remarks || ""}
              onChange={(e) => setFormData({ ...formData, remarks: e.target.value })}
            />
          </div>

          <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex justify-end space-x-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsAddOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              className="bg-indigo-600 hover:bg-indigo-700 font-semibold"
            >
              Save Attendance
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
