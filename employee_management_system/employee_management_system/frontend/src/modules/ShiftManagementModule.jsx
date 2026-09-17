import { useState, useEffect } from "react";
import {
  Clock,
  Calendar,
  Users,
  Plus,
  Trash2,
  Edit2,
  CheckCircle2,
  XCircle,
  CalendarDays,
  ShieldAlert,
  Search,
} from "lucide-react";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Dialog } from "../components/ui/dialog";
import {
  apiFetchShiftTypes,
  apiCreateShiftType,
  apiUpdateShiftType,
  apiDeleteShiftType,
  apiFetchShiftAssignments,
  apiCreateShiftAssignment,
  apiUpdateShiftAssignment,
  apiDeleteShiftAssignment,
  apiFetchHolidays,
  apiCreateHoliday,
  apiDeleteHoliday,
} from "../services/apiService";

const DAYS_OF_WEEK = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

export function ShiftManagementModule({ employees = [], userRole = "Administrator" }) {
  const [activeTab, setActiveTab] = useState("types"); // 'types' | 'assignments' | 'holidays'
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");

  // Data lists
  const [shiftTypes, setShiftTypes] = useState([]);
  const [shiftAssignments, setShiftAssignments] = useState([]);
  const [holidays, setHolidays] = useState([]);

  // Modals
  const [typeModalOpen, setTypeModalOpen] = useState(false);
  const [editingType, setEditingType] = useState(null);
  const [typeForm, setTypeForm] = useState({
    shift_name: "",
    start_time: "09:00:00",
    end_time: "18:00:00",
    grace_period_minutes: 30,
    half_day_threshold_hours: 4.0,
    weekly_off_days: ["Saturday", "Sunday"],
    enable_auto_attendance: 1,
    is_active: 1,
  });

  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [editingAssign, setEditingAssign] = useState(null);
  const [assignForm, setAssignForm] = useState({
    employee: "",
    shift_type: "",
    start_date: new Date().toISOString().split("T")[0],
    end_date: "",
    status: "Active",
  });

  const [holidayModalOpen, setHolidayModalOpen] = useState(false);
  const [holidayForm, setHolidayForm] = useState({
    holiday_name: "",
    holiday_date: new Date().toISOString().split("T")[0],
    description: "",
  });

  // Load data
  const loadData = async () => {
    setLoading(true);
    try {
      const [st, sa, hl] = await Promise.all([
        apiFetchShiftTypes(),
        apiFetchShiftAssignments(),
        apiFetchHolidays(),
      ]);
      if (Array.isArray(st)) setShiftTypes(st);
      if (Array.isArray(sa)) setShiftAssignments(sa);
      if (Array.isArray(hl)) setHolidays(hl);
    } catch (err) {
      console.error("Failed to load shift management data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Handlers for Shift Types
  const handleOpenTypeModal = (st = null) => {
    if (st) {
      setEditingType(st);
      const daysArr = st.weekly_off_days
        ? st.weekly_off_days.split(",").map((d) => d.trim()).filter(Boolean)
        : ["Saturday", "Sunday"];
      setTypeForm({
        shift_name: st.shift_name || st.name,
        start_time: st.start_time || "09:00:00",
        end_time: st.end_time || "18:00:00",
        grace_period_minutes: st.late_entry_grace_period ?? st.grace_period_minutes ?? 30,
        half_day_threshold_hours: st.half_day_threshold_hours ?? 4.0,
        weekly_off_days: daysArr,
        enable_auto_attendance: st.enable_auto_attendance ? 1 : 0,
        is_active: st.is_active !== undefined ? (st.is_active ? 1 : 0) : 1,
      });
    } else {
      setEditingType(null);
      setTypeForm({
        shift_name: "",
        start_time: "09:00:00",
        end_time: "18:00:00",
        grace_period_minutes: 30,
        half_day_threshold_hours: 4.0,
        weekly_off_days: ["Saturday", "Sunday"],
        enable_auto_attendance: 1,
        is_active: 1,
      });
    }
    setTypeModalOpen(true);
  };

  const handleSaveType = async (e) => {
    e.preventDefault();
    if (!typeForm.shift_name) return;

    const payload = {
      ...typeForm,
      late_entry_grace_period: typeForm.grace_period_minutes,
      weekly_off_days: typeForm.weekly_off_days.join(", "),
    };

    try {
      if (editingType) {
        await apiUpdateShiftType(editingType.name, payload);
      } else {
        await apiCreateShiftType(payload);
      }
      setTypeModalOpen(false);
      loadData();
    } catch (err) {
      alert(err.message || "Failed to save shift type");
    }
  };

  const handleDeleteType = async (name) => {
    if (!confirm(`Are you sure you want to delete shift type "${name}"?`)) return;
    try {
      await apiDeleteShiftType(name);
      loadData();
    } catch (err) {
      alert(err.message || "Failed to delete shift type");
    }
  };

  const toggleWeeklyOffDay = (day) => {
    setTypeForm((prev) => {
      const exists = prev.weekly_off_days.includes(day);
      return {
        ...prev,
        weekly_off_days: exists
          ? prev.weekly_off_days.filter((d) => d !== day)
          : [...prev.weekly_off_days, day],
      };
    });
  };

  // Handlers for Shift Assignments
  const handleOpenAssignModal = (sa = null) => {
    if (sa) {
      setEditingAssign(sa);
      setAssignForm({
        employee: sa.employee,
        shift_type: sa.shift_type,
        start_date: sa.start_date,
        end_date: sa.end_date || "",
        status: sa.status || "Active",
      });
    } else {
      setEditingAssign(null);
      setAssignForm({
        employee: employees.length > 0 ? employees[0].name : "",
        shift_type: shiftTypes.length > 0 ? shiftTypes[0].name : "",
        start_date: new Date().toISOString().split("T")[0],
        end_date: "",
        status: "Active",
      });
    }
    setAssignModalOpen(true);
  };

  const handleSaveAssign = async (e) => {
    e.preventDefault();
    if (!assignForm.employee || !assignForm.shift_type || !assignForm.start_date) return;

    try {
      if (editingAssign) {
        await apiUpdateShiftAssignment(editingAssign.name, assignForm);
      } else {
        await apiCreateShiftAssignment(assignForm);
      }
      setAssignModalOpen(false);
      loadData();
    } catch (err) {
      alert(err.message || "Failed to save shift assignment");
    }
  };

  const handleDeleteAssign = async (name) => {
    if (!confirm("Are you sure you want to remove this shift assignment?")) return;
    try {
      await apiDeleteShiftAssignment(name);
      loadData();
    } catch (err) {
      alert(err.message || "Failed to delete shift assignment");
    }
  };

  // Handlers for Holidays
  const handleSaveHoliday = async (e) => {
    e.preventDefault();
    if (!holidayForm.holiday_name || !holidayForm.holiday_date) return;

    try {
      await apiCreateHoliday(holidayForm);
      setHolidayModalOpen(false);
      setHolidayForm({
        holiday_name: "",
        holiday_date: new Date().toISOString().split("T")[0],
        description: "",
      });
      loadData();
    } catch (err) {
      alert(err.message || "Failed to add holiday");
    }
  };

  const handleDeleteHoliday = async (name) => {
    if (!confirm(`Are you sure you want to delete holiday "${name}"?`)) return;
    try {
      await apiDeleteHoliday(name);
      loadData();
    } catch (err) {
      alert(err.message || "Failed to delete holiday");
    }
  };

  // Filtered views
  const filteredTypes = shiftTypes.filter((st) =>
    (st.shift_name || st.name || "").toLowerCase().includes(search.toLowerCase())
  );

  const filteredAssignments = shiftAssignments.filter((sa) => {
    const empName = sa.employee_name || sa.employee || "";
    const shift = sa.shift_type || "";
    const q = search.toLowerCase();
    return empName.toLowerCase().includes(q) || shift.toLowerCase().includes(q);
  });

  const filteredHolidays = holidays.filter((h) =>
    (h.holiday_name || "").toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 theme-blue:text-blue-50">
            Shift & Holiday Management
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Configure shift schedules, weekly offs, grace periods, employee assignments, and official holidays.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          {activeTab === "types" && (
            <Button
              onClick={() => handleOpenTypeModal()}
              className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs h-9 cursor-pointer"
            >
              <Plus className="h-4 w-4 mr-1.5" />
              Add Shift Type
            </Button>
          )}
          {activeTab === "assignments" && (
            <Button
              onClick={() => handleOpenAssignModal()}
              className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs h-9 cursor-pointer"
            >
              <Plus className="h-4 w-4 mr-1.5" />
              Assign Shift
            </Button>
          )}
          {activeTab === "holidays" && (
            <Button
              onClick={() => setHolidayModalOpen(true)}
              className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs h-9 cursor-pointer"
            >
              <Plus className="h-4 w-4 mr-1.5" />
              Add Holiday
            </Button>
          )}
        </div>
      </div>

      {/* Tabs Bar */}
      <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2">
        <div className="flex space-x-2">
          <button
            type="button"
            onClick={() => setActiveTab("types")}
            className={`flex items-center space-x-2 px-3.5 py-2 text-xs font-semibold rounded-lg transition-colors cursor-pointer ${
              activeTab === "types"
                ? "bg-indigo-50 text-indigo-600 dark:bg-indigo-950/60 dark:text-indigo-400"
                : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
          >
            <Clock className="h-3.5 w-3.5" />
            <span>Shift Types ({shiftTypes.length})</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("assignments")}
            className={`flex items-center space-x-2 px-3.5 py-2 text-xs font-semibold rounded-lg transition-colors cursor-pointer ${
              activeTab === "assignments"
                ? "bg-indigo-50 text-indigo-600 dark:bg-indigo-950/60 dark:text-indigo-400"
                : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
          >
            <Users className="h-3.5 w-3.5" />
            <span>Assignments ({shiftAssignments.length})</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("holidays")}
            className={`flex items-center space-x-2 px-3.5 py-2 text-xs font-semibold rounded-lg transition-colors cursor-pointer ${
              activeTab === "holidays"
                ? "bg-indigo-50 text-indigo-600 dark:bg-indigo-950/60 dark:text-indigo-400"
                : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
          >
            <CalendarDays className="h-3.5 w-3.5" />
            <span>Holidays ({holidays.length})</span>
          </button>
        </div>

        <div className="relative w-48 sm:w-64">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
          <Input
            placeholder="Filter records..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8 text-xs h-8 bg-slate-50 dark:bg-slate-800"
          />
        </div>
      </div>

      {/* Tab 1: Shift Types */}
      {activeTab === "types" && (
        <Card className="overflow-hidden border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600 dark:text-slate-300">
              <thead className="bg-slate-50 dark:bg-slate-800/80 text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="px-4 py-3 font-semibold">Shift Name</th>
                  <th className="px-4 py-3 font-semibold">Hours</th>
                  <th className="px-4 py-3 font-semibold">Grace Period</th>
                  <th className="px-4 py-3 font-semibold">Half-Day Threshold</th>
                  <th className="px-4 py-3 font-semibold">Weekly Offs</th>
                  <th className="px-4 py-3 font-semibold">Auto Attendance</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredTypes.length === 0 ? (
                  <tr>
                    <td colSpan="8" className="py-8 text-center text-slate-400">
                      No shift types configured. Click &quot;Add Shift Type&quot; to define one.
                    </td>
                  </tr>
                ) : (
                  filteredTypes.map((st) => (
                    <tr key={st.name} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                      <td className="px-4 py-3 font-semibold text-slate-900 dark:text-slate-100">
                        {st.shift_name || st.name}
                      </td>
                      <td className="px-4 py-3">
                        {st.start_time} - {st.end_time}
                      </td>
                      <td className="px-4 py-3">{st.late_entry_grace_period || st.grace_period_minutes || 30} mins</td>
                      <td className="px-4 py-3">{st.half_day_threshold_hours || 0} hrs</td>
                      <td className="px-4 py-3 max-w-[200px] truncate" title={st.weekly_off_days}>
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                          {st.weekly_off_days || "None"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {st.enable_auto_attendance ? (
                          <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 text-[10px]">
                            Enabled
                          </Badge>
                        ) : (
                          <Badge className="bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 text-[10px]">
                            Disabled
                          </Badge>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {st.is_active !== 0 ? (
                          <span className="flex items-center text-emerald-600 font-medium">
                            <CheckCircle2 className="h-3 w-3 mr-1" /> Active
                          </span>
                        ) : (
                          <span className="flex items-center text-slate-400">
                            <XCircle className="h-3 w-3 mr-1" /> Inactive
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right space-x-1.5">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleOpenTypeModal(st)}
                          className="h-7 w-7 text-slate-500 hover:text-indigo-600 cursor-pointer"
                        >
                          <Edit2 className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteType(st.name)}
                          className="h-7 w-7 text-slate-500 hover:text-rose-600 cursor-pointer"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Tab 2: Shift Assignments */}
      {activeTab === "assignments" && (
        <Card className="overflow-hidden border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600 dark:text-slate-300">
              <thead className="bg-slate-50 dark:bg-slate-800/80 text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="px-4 py-3 font-semibold">Employee</th>
                  <th className="px-4 py-3 font-semibold">Assigned Shift</th>
                  <th className="px-4 py-3 font-semibold">Start Date</th>
                  <th className="px-4 py-3 font-semibold">End Date</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredAssignments.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="py-8 text-center text-slate-400">
                      No shift assignments found. Click &quot;Assign Shift&quot; to assign an employee.
                    </td>
                  </tr>
                ) : (
                  filteredAssignments.map((sa) => (
                    <tr key={sa.name} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-900 dark:text-slate-100">
                          {sa.employee_name || sa.employee}
                        </div>
                        <div className="text-[10px] text-slate-400">{sa.employee}</div>
                      </td>
                      <td className="px-4 py-3 font-medium text-indigo-600 dark:text-indigo-400">
                        {sa.shift_type}
                      </td>
                      <td className="px-4 py-3">{sa.start_date}</td>
                      <td className="px-4 py-3">{sa.end_date || "Ongoing"}</td>
                      <td className="px-4 py-3">
                        <Badge
                          className={
                            sa.status === "Active"
                              ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300"
                              : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400"
                          }
                        >
                          {sa.status || "Active"}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-right space-x-1.5">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleOpenAssignModal(sa)}
                          className="h-7 w-7 text-slate-500 hover:text-indigo-600 cursor-pointer"
                        >
                          <Edit2 className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteAssign(sa.name)}
                          className="h-7 w-7 text-slate-500 hover:text-rose-600 cursor-pointer"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Tab 3: Company Holidays */}
      {activeTab === "holidays" && (
        <Card className="overflow-hidden border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600 dark:text-slate-300">
              <thead className="bg-slate-50 dark:bg-slate-800/80 text-[11px] uppercase tracking-wider text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="px-4 py-3 font-semibold">Holiday Name</th>
                  <th className="px-4 py-3 font-semibold">Date</th>
                  <th className="px-4 py-3 font-semibold">Day of Week</th>
                  <th className="px-4 py-3 font-semibold">Description</th>
                  <th className="px-4 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredHolidays.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="py-8 text-center text-slate-400">
                      No holidays listed. Click &quot;Add Holiday&quot; to configure one.
                    </td>
                  </tr>
                ) : (
                  filteredHolidays.map((h) => {
                    const d = h.holiday_date ? new Date(h.holiday_date) : null;
                    const dayName = d
                      ? d.toLocaleDateString("en-US", { weekday: "long", timeZone: "UTC" })
                      : "";
                    return (
                      <tr key={h.name} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                        <td className="px-4 py-3 font-semibold text-slate-900 dark:text-slate-100 flex items-center space-x-2">
                          <Calendar className="h-3.5 w-3.5 text-indigo-500" />
                          <span>{h.holiday_name}</span>
                        </td>
                        <td className="px-4 py-3 font-medium">{h.holiday_date}</td>
                        <td className="px-4 py-3">
                          <span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-medium">
                            {dayName}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-500">{h.description || "Official Holiday"}</td>
                        <td className="px-4 py-3 text-right">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDeleteHoliday(h.name)}
                            className="h-7 w-7 text-slate-500 hover:text-rose-600 cursor-pointer"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Dialog: Shift Type Form */}
      <Dialog
        isOpen={typeModalOpen}
        onClose={() => setTypeModalOpen(false)}
        title={editingType ? "Edit Shift Type" : "Add New Shift Type"}
      >

          <form onSubmit={handleSaveType} className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block mb-1">
                Shift Name *
              </label>
              <Input
                required
                placeholder="e.g. Standard Morning 9-6"
                value={typeForm.shift_name}
                onChange={(e) => setTypeForm({ ...typeForm, shift_name: e.target.value })}
                className="text-xs"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block mb-1">
                  Start Time *
                </label>
                <Input
                  type="time"
                  step="1"
                  required
                  value={typeForm.start_time}
                  onChange={(e) => setTypeForm({ ...typeForm, start_time: e.target.value })}
                  className="text-xs"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block mb-1">
                  End Time *
                </label>
                <Input
                  type="time"
                  step="1"
                  required
                  value={typeForm.end_time}
                  onChange={(e) => setTypeForm({ ...typeForm, end_time: e.target.value })}
                  className="text-xs"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block mb-1">
                  Late Entry Grace Period (Minutes)
                </label>
                <Input
                  type="number"
                  min="0"
                  max="120"
                  value={typeForm.grace_period_minutes}
                  onChange={(e) =>
                    setTypeForm({ ...typeForm, grace_period_minutes: parseInt(e.target.value) || 0 })
                  }
                  className="text-xs"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block mb-1">
                  Half-Day Threshold (Hours)
                </label>
                <Input
                  type="number"
                  step="0.5"
                  min="1"
                  max="12"
                  value={typeForm.half_day_threshold_hours}
                  onChange={(e) =>
                    setTypeForm({ ...typeForm, half_day_threshold_hours: parseFloat(e.target.value) || 0 })
                  }
                  className="text-xs"
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block mb-1.5">
                Weekly Off Days
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
                {DAYS_OF_WEEK.map((day) => {
                  const checked = typeForm.weekly_off_days.includes(day);
                  return (
                    <button
                      type="button"
                      key={day}
                      onClick={() => toggleWeeklyOffDay(day)}
                      className={`text-[11px] py-1 px-2 rounded border transition-colors cursor-pointer text-center ${
                        checked
                          ? "bg-indigo-600 text-white border-indigo-600 font-semibold"
                          : "bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400"
                      }`}
                    >
                      {day.slice(0, 3)}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-800">
              <label className="flex items-center space-x-2 text-xs cursor-pointer">
                <input
                  type="checkbox"
                  checked={typeForm.enable_auto_attendance === 1}
                  onChange={(e) =>
                    setTypeForm({ ...typeForm, enable_auto_attendance: e.target.checked ? 1 : 0 })
                  }
                  className="rounded text-indigo-600"
                />
                <span>Enable Auto Attendance</span>
              </label>

              <label className="flex items-center space-x-2 text-xs cursor-pointer">
                <input
                  type="checkbox"
                  checked={typeForm.is_active === 1}
                  onChange={(e) =>
                    setTypeForm({ ...typeForm, is_active: e.target.checked ? 1 : 0 })
                  }
                  className="rounded text-indigo-600"
                />
                <span>Active</span>
              </label>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100 dark:border-slate-800">
              <Button
                type="button"
                variant="outline"
                onClick={() => setTypeModalOpen(false)}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button type="submit" className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs cursor-pointer">
                {editingType ? "Update Shift" : "Create Shift"}
              </Button>
            </div>
          </form>
      </Dialog>

      {/* Dialog: Shift Assignment Form */}
      <Dialog
        isOpen={assignModalOpen}
        onClose={() => setAssignModalOpen(false)}
        title={editingAssign ? "Edit Shift Assignment" : "Assign Shift to Employee"}
      >

          <form onSubmit={handleSaveAssign} className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block mb-1">
                Employee *
              </label>
              <select
                required
                value={assignForm.employee}
                onChange={(e) => setAssignForm({ ...assignForm, employee: e.target.value })}
                className="w-full text-xs rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-2"
              >
                <option value="">Select Employee</option>
                {employees.map((emp) => (
                  <option key={emp.name} value={emp.name}>
                    {emp.full_name} ({emp.name}) - {emp.department || "General"}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block mb-1">
                Shift Type *
              </label>
              <select
                required
                value={assignForm.shift_type}
                onChange={(e) => setAssignForm({ ...assignForm, shift_type: e.target.value })}
                className="w-full text-xs rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-2"
              >
                <option value="">Select Shift Type</option>
                {shiftTypes.map((st) => (
                  <option key={st.name} value={st.name}>
                    {st.shift_name || st.name} ({st.start_time} - {st.end_time})
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block mb-1">
                  Start Date *
                </label>
                <Input
                  type="date"
                  required
                  value={assignForm.start_date}
                  onChange={(e) => setAssignForm({ ...assignForm, start_date: e.target.value })}
                  className="text-xs"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block mb-1">
                  End Date (Optional)
                </label>
                <Input
                  type="date"
                  value={assignForm.end_date}
                  onChange={(e) => setAssignForm({ ...assignForm, end_date: e.target.value })}
                  className="text-xs"
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block mb-1">
                Status
              </label>
              <select
                value={assignForm.status}
                onChange={(e) => setAssignForm({ ...assignForm, status: e.target.value })}
                className="w-full text-xs rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-2"
              >
                <option value="Active">Active</option>
                <option value="Inactive">Inactive</option>
              </select>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100 dark:border-slate-800">
              <Button
                type="button"
                variant="outline"
                onClick={() => setAssignModalOpen(false)}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button type="submit" className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs cursor-pointer">
                {editingAssign ? "Update Assignment" : "Save Assignment"}
              </Button>
            </div>
          </form>
      </Dialog>

      {/* Dialog: Holiday Form */}
      <Dialog
        isOpen={holidayModalOpen}
        onClose={() => setHolidayModalOpen(false)}
        title="Add Official Company Holiday"
      >

          <form onSubmit={handleSaveHoliday} className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block mb-1">
                Holiday Name *
              </label>
              <Input
                required
                placeholder="e.g. Independence Day, Diwali"
                value={holidayForm.holiday_name}
                onChange={(e) =>
                  setHolidayForm({ ...holidayForm, holiday_name: e.target.value })
                }
                className="text-xs"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block mb-1">
                Holiday Date *
              </label>
              <Input
                type="date"
                required
                value={holidayForm.holiday_date}
                onChange={(e) =>
                  setHolidayForm({ ...holidayForm, holiday_date: e.target.value })
                }
                className="text-xs"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 dark:text-slate-300 block mb-1">
                Description (Optional)
              </label>
              <Input
                placeholder="National holiday / Public celebration"
                value={holidayForm.description}
                onChange={(e) =>
                  setHolidayForm({ ...holidayForm, description: e.target.value })
                }
                className="text-xs"
              />
            </div>

            <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100 dark:border-slate-800">
              <Button
                type="button"
                variant="outline"
                onClick={() => setHolidayModalOpen(false)}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button type="submit" className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs cursor-pointer">
                Add Holiday
              </Button>
            </div>
          </form>
      </Dialog>
    </div>
  );
}
