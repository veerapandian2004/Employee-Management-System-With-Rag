import { useState } from "react";
import {
  Users,
  Building2,
  CalendarCheck,
  FileSpreadsheet,
  Receipt,
  CreditCard,
  Plus,
  ArrowUpRight,
  TrendingUp,
  CheckCircle2,
  XCircle,
  Clock,
  Briefcase,
  MessageSquare,
  DollarSign,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Dialog } from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Select } from "../components/ui/select";
import { GpsClockWidget } from "../components/GpsClockWidget";
import { ApplyLeaveDialog } from "../components/ApplyLeaveDialog";

export function DashboardModule({
  employees = [],
  departments = [],
  leaveApplications = [],
  leaveTypes = [],
  salarySlips = [],
  setActiveTab,
  onUpdateLeaveStatus,
  onAddEmployee,
  onAddLeaveApplication,
  userRole = "Administrator",
  currentUser = null,
}) {
  const isEmployee = userRole === "Employee";
  const isAdmin = userRole === "Administrator";

  const activeEmpCount = employees.filter((e) => e.status === "Active").length;
  const onLeaveEmpCount = employees.filter((e) => e.status === "On Leave").length;
  const pendingLeaves = leaveApplications.filter((l) => l.status === "Pending");
  const totalPayrollOutflow = salarySlips.reduce((acc, curr) => acc + Number(curr.net_pay || 0), 0);

  const isSelfLeave = (leave) => {
    if (!leave) return false;
    const myEmpId = currentUser?.employee?.name || currentUser?.employee?.naming_series;
    const myFullName = currentUser?.full_name;
    const myEmail = currentUser?.email || currentUser?.employee?.email || currentUser?.user;
    return Boolean(
      (myEmpId && (leave.employee === myEmpId || leave.employee_name === myEmpId)) ||
      (myFullName && leave.employee_name === myFullName) ||
      (myEmail && (leave.employee === myEmail || leave.employee_email === myEmail))
    );
  };

  // For HR, self-leaves require Administrator approval, so they are not actionable by this HR user
  const actionablePendingLeaves = isAdmin
    ? pendingLeaves
    : pendingLeaves.filter((l) => !isSelfLeave(l));

  // Employee-specific stats
  const myEmployeeRecord = currentUser?.employee || null;
  const myLeaves = leaveApplications; // Already filtered for employee by backend
  const myApprovedLeaves = myLeaves.filter((l) => l.status === "Approved");
  const myPendingLeaves = myLeaves.filter((l) => l.status === "Pending");
  const myDaysTaken = myApprovedLeaves.reduce((acc, curr) => acc + Number(curr.total_days || 0), 0);
  const myLatestSlip = salarySlips[0] || null;

  // Modal State for directly adding employee on Dashboard (Admin/HR only)
  const [isAddOpen, setIsAddOpen] = useState(false);

  // Modal State for directly applying leave on Dashboard
  const [isLeaveDialogOpen, setIsLeaveDialogOpen] = useState(false);
  const handleOpenApplyLeave = () => {
    setIsLeaveDialogOpen(true);
  };

  // Helper to dynamically calculate next 3-digit employee ID
  const getNextEmployeeId = () => {
    let maxNum = 0;
    employees.forEach((emp) => {
      const id = emp.naming_series || emp.name || "";
      const match = id.match(/EMP-(\d+)/i);
      if (match) {
        let numStr = match[1];
        if (numStr.length > 5 && numStr.endsWith("00001")) {
          numStr = numStr.slice(0, -5);
        }
        const num = parseInt(numStr, 10);
        if (!isNaN(num) && num < 10000 && num > maxNum) {
          maxNum = num;
        }
      }
    });
    return `EMP-${String(maxNum + 1).padStart(3, "0")}`;
  };

  const getFreshInitialForm = () => ({
    naming_series: getNextEmployeeId(),
    full_name: "",
    email: "",
    phone: "",
    department: departments[0]?.department_name || "Engineering",
    designation: "Software Engineer",
    date_of_joining: new Date().toISOString().split("T")[0],
    reporting_manager: "",
    employment_type: "Full-Time",
    status: "Active",
    basic_salary: 75000,
    skills: "",
    profile_image: "",
    user_id: "",
  });

  const [formData, setFormData] = useState(getFreshInitialForm);

  const handleOpenAdd = () => {
    setFormData(getFreshInitialForm());
    setIsAddOpen(true);
  };

  const handleSave = (e) => {
    e.preventDefault();
    if (!formData.full_name) return;

    let phone = formData.phone?.trim() || "";
    if (phone && !phone.startsWith("+")) {
      const digits = phone.replace(/\D/g, "");
      if (digits.length === 10) {
        phone = `+91${digits}`;
      } else if (digits.length > 0) {
        phone = `+${digits}`;
      }
    }

    const payload = { ...formData, phone };

    if (onAddEmployee) {
      onAddEmployee({ ...payload, name: payload.naming_series });
    }
    setIsAddOpen(false);
  };

  // -------------------------------------------------------------
  // RENDER: EMPLOYEE VIEW
  // -------------------------------------------------------------
  if (isEmployee) {
    return (
      <div className="space-y-6 animate-in fade-in duration-300">
        {/* Top Banner Hero for Employee */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-indigo-900 via-indigo-800 to-purple-900 p-6 sm:p-8 text-white shadow-xl">
          <div className="absolute top-0 right-0 -mt-12 -mr-12 h-64 w-64 rounded-full bg-indigo-500/20 blur-3xl" />
          <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="space-y-2">
              <Badge className="bg-indigo-500/30 text-indigo-100 border-indigo-400/30 font-medium">
                Employee Portal
              </Badge>
              <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
                Welcome back, {currentUser?.full_name || "Employee"} 👋
              </h2>
              <p className="text-indigo-200 text-sm max-w-xl leading-relaxed">
                Track your leave balances, view your monthly paystubs, browse company handbooks, and chat with your HR assistant.
              </p>
            </div>
            <div className="flex flex-wrap gap-3 shrink-0">
              <Button
                onClick={handleOpenApplyLeave}
                className="bg-indigo-600 hover:bg-indigo-700 font-semibold shadow-md cursor-pointer"
              >
                <Plus className="mr-2 h-4 w-4" /> Apply for Leave
              </Button>
              <Button
                onClick={() => setActiveTab("salary_slip")}
                variant="outline"
                className="border-indigo-400/40 bg-indigo-950/40 text-white hover:bg-indigo-900/60"
              >
                <Receipt className="mr-2 h-4 w-4" /> View Paystubs
              </Button>
            </div>
          </div>
        </div>

        {/* GPS-Based Employee Clock IN / Clock OUT Attendance Widget */}
        <GpsClockWidget />

        {/* Employee KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="border-l-4 border-l-indigo-600">
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Department</p>
                  <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100 mt-1">
                    {myEmployeeRecord?.department || "Engineering"}
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    {myEmployeeRecord?.designation || "Staff Member"}
                  </p>
                </div>
                <div className="h-12 w-12 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 flex items-center justify-center">
                  <Briefcase className="h-6 w-6" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-l-4 border-l-amber-600">
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Leave Days Taken</p>
                  <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">{myDaysTaken} Days</h3>
                  <p className="text-xs text-amber-600 dark:text-amber-400 font-medium mt-0.5">
                    {myPendingLeaves.length} application(s) pending
                  </p>
                </div>
                <div className="h-12 w-12 rounded-xl bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400 flex items-center justify-center">
                  <FileSpreadsheet className="h-6 w-6" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-l-4 border-l-emerald-600">
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Latest Net Pay</p>
                  <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">
                    {myLatestSlip ? `$${Number(myLatestSlip.net_pay || 0).toLocaleString()}` : "$0"}
                  </h3>
                  <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium mt-0.5">
                    {myLatestSlip?.salary_month || "No recent slip"}
                  </p>
                </div>
                <div className="h-12 w-12 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
                  <DollarSign className="h-6 w-6" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-l-4 border-l-purple-600">
            <CardContent className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Status</p>
                  <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100 mt-1">
                    {myEmployeeRecord?.status || "Active"}
                  </h3>
                  <p className="text-xs text-purple-600 dark:text-purple-400 font-medium mt-0.5">
                    {myEmployeeRecord?.employment_type || "Full-Time"}
                  </p>
                </div>
                <div className="h-12 w-12 rounded-xl bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400 flex items-center justify-center">
                  <CheckCircle2 className="h-6 w-6" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Employee Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left 2 Cols: My Recent Leaves & Paystubs */}
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>My Recent Leave Applications</CardTitle>
                  <CardDescription>Track status of your requested time off</CardDescription>
                </div>
                <div className="flex items-center space-x-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleOpenApplyLeave}
                    className="text-xs border-indigo-200 dark:border-indigo-800 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/50 cursor-pointer"
                  >
                    <Plus className="mr-1 h-3.5 w-3.5" /> Apply
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setActiveTab("leave_application")}
                    className="text-xs text-indigo-600 dark:text-indigo-400 cursor-pointer"
                  >
                    View All <ArrowUpRight className="ml-1 h-3.5 w-3.5" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {myLeaves.length === 0 ? (
                  <div className="py-8 text-center text-slate-500 dark:text-slate-400">
                    <CalendarCheck className="mx-auto h-8 w-8 text-slate-400 dark:text-slate-500 mb-2 opacity-60" />
                    <p className="text-sm font-medium">No leave applications filed yet.</p>
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100 dark:divide-slate-800">
                    {myLeaves.slice(0, 5).map((leave) => (
                      <div key={leave.name} className="py-3.5 flex items-center justify-between gap-4">
                        <div>
                          <div className="font-semibold text-sm text-slate-900 dark:text-slate-100">{leave.leave_type}</div>
                          <div className="text-xs text-slate-500 dark:text-slate-400 flex items-center space-x-2 mt-0.5">
                            <span>{leave.from_date} to {leave.to_date}</span>
                            <span>•</span>
                            <span>{leave.total_days} day(s)</span>
                          </div>
                        </div>
                        <Badge
                          variant={
                            leave.status === "Approved"
                              ? "success"
                              : leave.status === "Pending"
                              ? "warning"
                              : "destructive"
                          }
                        >
                          {leave.status}
                        </Badge>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* My Paystubs Preview */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>My Paystubs</CardTitle>
                  <CardDescription>Monthly salary disbursements</CardDescription>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setActiveTab("salary_slip")}
                  className="text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300"
                >
                  View All <ArrowUpRight className="ml-1 h-3.5 w-3.5" />
                </Button>
              </CardHeader>
              <CardContent>
                {salarySlips.length === 0 ? (
                  <div className="py-8 text-center text-slate-500 dark:text-slate-400">
                    <Receipt className="mx-auto h-8 w-8 text-slate-400 dark:text-slate-500 mb-2 opacity-60" />
                    <p className="text-sm font-medium">No salary slips generated yet.</p>
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100 dark:divide-slate-800">
                    {salarySlips.slice(0, 4).map((slip) => (
                      <div key={slip.name} className="py-3 flex items-center justify-between">
                        <div>
                          <div className="font-semibold text-sm text-slate-900 dark:text-slate-100">{slip.salary_month}</div>
                          <div className="text-xs text-slate-500 dark:text-slate-400">Slip ID: {slip.name}</div>
                        </div>
                        <div className="text-right">
                          <div className="font-extrabold text-emerald-600 dark:text-emerald-400 text-sm">
                            ${Number(slip.net_pay || 0).toLocaleString()}
                          </div>
                          <Badge variant="secondary" className="text-[10px] mt-0.5">
                            {slip.select || "Draft"}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Right 1 Col: Quick Shortcuts & Resources */}
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Quick Employee Actions</CardTitle>
                <CardDescription>Shortcuts to key services</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <button
                  onClick={handleOpenApplyLeave}
                  className="w-full flex items-center justify-between p-3 rounded-lg border border-slate-200 dark:border-slate-800 hover:border-indigo-300 dark:hover:border-indigo-500/50 hover:bg-indigo-50/50 dark:hover:bg-indigo-950/30 transition-all text-left group cursor-pointer"
                >
                  <div className="flex items-center space-x-3">
                    <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                      <FileSpreadsheet className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">Apply for Leave</div>
                      <div className="text-xs text-slate-500 dark:text-slate-400">Request vacation, sick or casual time off</div>
                    </div>
                  </div>
                  <Plus className="h-4 w-4 text-slate-400 group-hover:text-indigo-600 dark:group-hover:text-indigo-400" />
                </button>

                <button
                  onClick={() => setActiveTab("employee")}
                  className="w-full flex items-center justify-between p-3 rounded-lg border border-slate-200 dark:border-slate-800 hover:border-indigo-300 dark:hover:border-indigo-500/50 hover:bg-indigo-50/50 dark:hover:bg-indigo-950/30 transition-all text-left group"
                >
                  <div className="flex items-center space-x-3">
                    <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                      <Users className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">My Profile</div>
                      <div className="text-xs text-slate-500 dark:text-slate-400">View personal details & job role</div>
                    </div>
                  </div>
                  <ArrowUpRight className="h-4 w-4 text-slate-400 group-hover:text-indigo-600 dark:group-hover:text-indigo-400" />
                </button>

                <button
                  onClick={() => setActiveTab("chat")}
                  className="w-full flex items-center justify-between p-3 rounded-lg border border-slate-200 dark:border-slate-800 hover:border-indigo-300 dark:hover:border-indigo-500/50 hover:bg-indigo-50/50 dark:hover:bg-indigo-950/30 transition-all text-left group"
                >
                  <div className="flex items-center space-x-3">
                    <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                      <MessageSquare className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">SQL Chat Assistant</div>
                      <div className="text-xs text-slate-500 dark:text-slate-400">Ask database questions & generate SQL</div>
                    </div>
                  </div>
                  <ArrowUpRight className="h-4 w-4 text-slate-400 group-hover:text-indigo-600 dark:group-hover:text-indigo-400" />
                </button>
              </CardContent>
            </Card>

            {/* Employment Overview */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Employment Overview</CardTitle>
                <CardDescription>Your role & organization details</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-xs">
                <div className="flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                  <span className="text-slate-500 dark:text-slate-400">Department</span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">{myEmployeeRecord?.department || "General"}</span>
                </div>
                <div className="flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                  <span className="text-slate-500 dark:text-slate-400">Designation</span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">{myEmployeeRecord?.designation || "Staff"}</span>
                </div>
                <div className="flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                  <span className="text-slate-500 dark:text-slate-400">Status</span>
                  <Badge variant="success" className="text-[10px]">{myEmployeeRecord?.status || "Active"}</Badge>
                </div>
                <div className="flex items-center justify-between py-1">
                  <span className="text-slate-500 dark:text-slate-400">Joining Date</span>
                  <span className="font-mono text-slate-700 dark:text-slate-300">{myEmployeeRecord?.date_of_joining || "N/A"}</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Apply Leave Modal */}
        <ApplyLeaveDialog
          isOpen={isLeaveDialogOpen}
          onClose={() => setIsLeaveDialogOpen(false)}
          onAddLeaveApplication={onAddLeaveApplication}
          leaveTypes={leaveTypes}
          employees={employees}
          userRole={userRole}
          currentUser={currentUser}
        />
      </div>
    );
  }

  // -------------------------------------------------------------
  // RENDER: ADMIN & HR VIEW
  // -------------------------------------------------------------
  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Top Banner Hero */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-indigo-900 via-indigo-800 to-purple-900 p-6 sm:p-8 text-white shadow-xl">
        <div className="absolute top-0 right-0 -mt-12 -mr-12 h-64 w-64 rounded-full bg-indigo-500/20 blur-3xl" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <Badge className="bg-indigo-500/30 text-indigo-100 border-indigo-400/30 font-medium">
              {isAdmin ? "Enterprise Dashboard" : "HR Management Portal"}
            </Badge>
            <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
              Welcome back, {currentUser?.full_name || (isAdmin ? "Administrator" : "HR Manager")} 👋
            </h2>
            <p className="text-indigo-200 text-sm max-w-xl leading-relaxed">
              Manage your workforce, departments, leave requests, and payroll slips seamlessly from one central hub.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 shrink-0">
            <Button
              onClick={handleOpenAdd}
              className="bg-indigo-600 hover:bg-indigo-700 font-semibold shadow-md cursor-pointer"
            >
              <Plus className="mr-2 h-4 w-4" /> Add Employee
            </Button>
            {userRole !== "Administrator" && (
              <Button
                onClick={handleOpenApplyLeave}
                className="bg-indigo-700 hover:bg-indigo-800 text-white font-semibold shadow-md cursor-pointer"
              >
                <Plus className="mr-2 h-4 w-4" /> Apply for Leave
              </Button>
            )}
            <Button
              onClick={() => setActiveTab("leave_application")}
              variant="outline"
              className="border-indigo-400/40 bg-indigo-950/40 text-white hover:bg-indigo-900/60 cursor-pointer"
            >
              <FileSpreadsheet className="mr-2 h-4 w-4" /> Review Leaves
            </Button>
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-l-4 border-l-indigo-600">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Total Staff</p>
                <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">{employees.length}</h3>
                <div className="flex items-center space-x-2 mt-1 text-xs text-slate-500 dark:text-slate-400">
                  <span className="text-emerald-600 dark:text-emerald-400 font-medium">{activeEmpCount} Active</span>
                  <span>•</span>
                  <span className="text-amber-600 dark:text-amber-400 font-medium">{onLeaveEmpCount} On Leave</span>
                </div>
              </div>
              <div className="h-12 w-12 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 flex items-center justify-center">
                <Users className="h-6 w-6" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-emerald-600">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Departments</p>
                <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">{departments.length}</h3>
                <div className="flex items-center space-x-1 mt-1 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                  <TrendingUp className="h-3.5 w-3.5" />
                  <span>Active Business Units</span>
                </div>
              </div>
              <div className="h-12 w-12 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
                <Building2 className="h-6 w-6" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-amber-600">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Pending Leaves</p>
                <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">{pendingLeaves.length}</h3>
                <div className="flex items-center space-x-1 mt-1 text-xs text-amber-600 dark:text-amber-400 font-medium">
                  <Clock className="h-3.5 w-3.5" />
                  <span>Requires HR approval</span>
                </div>
              </div>
              <div className="h-12 w-12 rounded-xl bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400 flex items-center justify-center">
                <FileSpreadsheet className="h-6 w-6" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-purple-600">
          <CardContent className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Monthly Outflow</p>
                <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">
                  ${totalPayrollOutflow.toLocaleString()}
                </h3>
                <div className="flex items-center space-x-1 mt-1 text-xs text-purple-600 dark:text-purple-400 font-medium">
                  <Receipt className="h-3.5 w-3.5" />
                  <span>{salarySlips.length} Slips Generated</span>
                </div>
              </div>
              <div className="h-12 w-12 rounded-xl bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400 flex items-center justify-center">
                <CreditCard className="h-6 w-6" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Layout Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Pending Approvals & Departments */}
        <div className="lg:col-span-2 space-y-6">
          {/* Pending Leave Requests */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center space-x-2">
                  <span>Pending Leave Requests</span>
                  {actionablePendingLeaves.length > 0 && (
                    <Badge variant="warning">{actionablePendingLeaves.length} Action Needed</Badge>
                  )}
                </CardTitle>
                <CardDescription>Leave applications requiring manager response</CardDescription>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setActiveTab("leave_application")}
                className="text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300"
              >
                View All <ArrowUpRight className="ml-1 h-3.5 w-3.5" />
              </Button>
            </CardHeader>
            <CardContent>
              {pendingLeaves.length === 0 ? (
                <div className="py-8 text-center text-slate-500 dark:text-slate-400">
                  <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-500 mb-2 opacity-60" />
                  <p className="text-sm font-medium">All leave applications up to date!</p>
                </div>
              ) : (
                <div className="divide-y divide-slate-100 dark:divide-slate-800">
                  {pendingLeaves.map((leave) => (
                    <div key={leave.name} className="py-3.5 flex items-center justify-between gap-4">
                      <div className="flex items-center space-x-3">
                        <div className="h-9 w-9 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-700 dark:text-slate-200 font-semibold text-sm">
                          {leave.employee_name ? leave.employee_name[0] : "E"}
                        </div>
                        <div>
                          <div className="font-semibold text-sm text-slate-900 dark:text-slate-100">{leave.employee_name}</div>
                          <div className="text-xs text-slate-500 dark:text-slate-400 flex items-center space-x-2">
                            <span>{leave.leave_type}</span>
                            <span>•</span>
                            <span>{leave.total_days} day(s) ({leave.from_date} to {leave.to_date})</span>
                          </div>
                        </div>
                      </div>

                      {isSelfLeave(leave) && !isAdmin ? (
                        <div className="flex items-center shrink-0">
                          <Badge
                            variant="outline"
                            className="text-xs font-semibold text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 border-amber-300 dark:border-amber-800"
                          >
                            Pending Admin Approval
                          </Badge>
                        </div>
                      ) : (
                        <div className="flex items-center space-x-2 shrink-0">
                          <Button
                            size="sm"
                            variant="success"
                            className="h-8 text-xs cursor-pointer"
                            onClick={() => onUpdateLeaveStatus && onUpdateLeaveStatus(leave.name, "Approved")}
                          >
                            <CheckCircle2 className="mr-1 h-3.5 w-3.5" /> Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            className="h-8 text-xs cursor-pointer"
                            onClick={() => onUpdateLeaveStatus && onUpdateLeaveStatus(leave.name, "Rejected")}
                          >
                            <XCircle className="mr-1 h-3.5 w-3.5" /> Reject
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Department Breakdown */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Departments Overview</CardTitle>
                <CardDescription>Department heads, structure & headcount</CardDescription>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setActiveTab("department")}
                className="text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300"
              >
                Manage Depts <ArrowUpRight className="ml-1 h-3.5 w-3.5" />
              </Button>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {departments.map((dept) => {
                  const deptStaffCount = employees.filter((e) => e.department === dept.department_name).length;
                  return (
                    <div
                      key={dept.name}
                      className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-semibold text-slate-900 dark:text-slate-100 text-sm flex items-center space-x-2">
                          <Building2 className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
                          <span>{dept.department_name}</span>
                        </span>
                        <Badge variant="secondary" className="text-xs font-semibold">
                          {deptStaffCount} Staff
                        </Badge>
                      </div>
                      <div className="text-xs text-slate-500 dark:text-slate-400 space-y-1">
                        <div className="flex justify-between">
                          <span>Head:</span>
                          <span className="font-medium text-slate-700 dark:text-slate-300">{dept.department_head_name || dept.department_head || "Unassigned"}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Cost Center:</span>
                          <span className="font-mono text-slate-600 dark:text-slate-400">{dept.cost_center || "N/A"}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right 1 Col: Quick Links */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Quick Management Actions</CardTitle>
              <CardDescription>Direct navigation shortcuts</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <button
                onClick={() => setActiveTab("employee")}
                className="w-full flex items-center justify-between p-3 rounded-lg border border-slate-200 dark:border-slate-800 hover:border-indigo-300 dark:hover:border-indigo-500/50 hover:bg-indigo-50/50 dark:hover:bg-indigo-950/30 transition-all text-left group"
              >
                <div className="flex items-center space-x-3">
                  <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                    <Users className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">Manage Employee Directory</div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">View profiles & assign roles</div>
                  </div>
                </div>
                <ArrowUpRight className="h-4 w-4 text-slate-400 group-hover:text-indigo-600 dark:group-hover:text-indigo-400" />
              </button>

              <button
                onClick={() => setActiveTab("leave_application")}
                className="w-full flex items-center justify-between p-3 rounded-lg border border-slate-200 dark:border-slate-800 hover:border-indigo-300 dark:hover:border-indigo-500/50 hover:bg-indigo-50/50 dark:hover:bg-indigo-950/30 transition-all text-left group"
              >
                <div className="flex items-center space-x-3">
                  <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                    <FileSpreadsheet className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">Review Leave Applications</div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">Approve or reject leave requests</div>
                  </div>
                </div>
                <ArrowUpRight className="h-4 w-4 text-slate-400 group-hover:text-indigo-600 dark:group-hover:text-indigo-400" />
              </button>

              <button
                onClick={() => setActiveTab("salary_slip")}
                className="w-full flex items-center justify-between p-3 rounded-lg border border-slate-200 dark:border-slate-800 hover:border-purple-300 dark:hover:border-purple-500/50 hover:bg-purple-50/50 dark:hover:bg-purple-950/30 transition-all text-left group"
              >
                <div className="flex items-center space-x-3">
                  <div className="p-2 rounded-lg bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400 group-hover:bg-purple-600 group-hover:text-white transition-colors">
                    <Receipt className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">Generate Salary Slips</div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">Calculate allowances & deductions</div>
                  </div>
                </div>
                <ArrowUpRight className="h-4 w-4 text-slate-400 group-hover:text-purple-600 dark:group-hover:text-purple-400" />
              </button>

              <button
                onClick={() => setActiveTab("attendance")}
                className="w-full flex items-center justify-between p-3 rounded-lg border border-slate-200 dark:border-slate-800 hover:border-indigo-300 dark:hover:border-indigo-500/50 hover:bg-indigo-50/50 dark:hover:bg-indigo-950/30 transition-all text-left group"
              >
                <div className="flex items-center space-x-3">
                  <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                    <CalendarCheck className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-slate-900 dark:text-slate-100">Employee Attendance</div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">Track daily check-ins & presence</div>
                  </div>
                </div>
                <ArrowUpRight className="h-4 w-4 text-slate-400 group-hover:text-indigo-600 dark:group-hover:text-indigo-400" />
              </button>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Add Employee Dialog Form directly on Dashboard */}
      <Dialog
        isOpen={isAddOpen}
        onClose={() => setIsAddOpen(false)}
        title="Create New Employee"
        description="Fill out all details based on the Employee DocType schema."
        maxWidth="max-w-2xl"
      >
        <form onSubmit={handleSave} className="space-y-4 py-2">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Employee ID / Series *
              </label>
              <Input
                value={formData.naming_series}
                onChange={(e) => setFormData({ ...formData, naming_series: e.target.value })}
                required
                className="font-mono"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Full Name *
              </label>
              <Input
                placeholder="e.g. John Doe"
                value={formData.full_name}
                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                required
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">Email</label>
              <Input
                type="email"
                placeholder="john.doe@company.com"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Phone Number <span className="text-[11px] text-slate-400 font-normal">(e.g. +91 98765 43210)</span>
              </label>
              <Input
                placeholder="e.g. +91 98765 43210 or +1 (555) 019-2834"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">Department</label>
              <Select
                value={formData.department}
                onChange={(e) => setFormData({ ...formData, department: e.target.value })}
              >
                {departments.map((d) => (
                  <option key={d.name} value={d.department_name}>
                    {d.department_name}
                  </option>
                ))}
              </Select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">Designation</label>
              <Input
                placeholder="e.g. Senior Software Engineer"
                value={formData.designation}
                onChange={(e) => setFormData({ ...formData, designation: e.target.value })}
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Date of Joining
              </label>
              <Input
                type="date"
                value={formData.date_of_joining}
                onChange={(e) => setFormData({ ...formData, date_of_joining: e.target.value })}
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Reporting Manager
              </label>
              <Select
                value={formData.reporting_manager}
                onChange={(e) => setFormData({ ...formData, reporting_manager: e.target.value })}
              >
                <option value="">-- No Manager --</option>
                {employees.map((e) => (
                  <option key={e.name || e.naming_series} value={e.name || e.naming_series}>
                    {e.full_name} ({e.name || e.naming_series})
                  </option>
                ))}
              </Select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Employment Type
              </label>
              <Select
                value={formData.employment_type}
                onChange={(e) => setFormData({ ...formData, employment_type: e.target.value })}
              >
                <option value="Full-Time">Full-Time</option>
                <option value="Part-Time">Part-Time</option>
                <option value="Contract">Contract</option>
                <option value="Intern">Intern</option>
              </Select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">Status</label>
              <Select
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value })}
              >
                <option value="Active">Active</option>
                <option value="Inactive">Inactive</option>
                <option value="On Leave">On Leave</option>
              </Select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Basic Salary ($)
              </label>
              <Input
                type="number"
                value={formData.basic_salary}
                onChange={(e) => setFormData({ ...formData, basic_salary: Number(e.target.value) })}
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Profile Image URL
              </label>
              <Input
                placeholder="https://..."
                value={formData.profile_image}
                onChange={(e) => setFormData({ ...formData, profile_image: e.target.value })}
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">Skills</label>
            <Input
              placeholder="e.g. React, Node.js, SQL, Agile"
              value={formData.skills}
              onChange={(e) => setFormData({ ...formData, skills: e.target.value })}
            />
          </div>

          <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex justify-end space-x-3">
            <Button type="button" variant="outline" onClick={() => setIsAddOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" className="bg-indigo-600 hover:bg-indigo-700 font-semibold">
              Create Employee
            </Button>
          </div>
        </form>
      </Dialog>

      {/* Apply Leave Modal */}
      {userRole !== "Administrator" && (
        <ApplyLeaveDialog
          isOpen={isLeaveDialogOpen}
          onClose={() => setIsLeaveDialogOpen(false)}
          onAddLeaveApplication={onAddLeaveApplication}
          leaveTypes={leaveTypes}
          employees={employees}
          userRole={userRole}
          currentUser={currentUser}
        />
      )}
    </div>
  );
}
