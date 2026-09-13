import { useState, useEffect } from "react";
import {
  Users,
  Plus,
  Search,
  Mail,
  Phone,
  Building2,
  Calendar,
  DollarSign,
  UserCheck,
  Briefcase,
  Edit,
  Trash2,
  Eye,
  Grid,
  List,
  Award,
  Copy,
  Check,
  ExternalLink,
  Clock,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { Dialog } from "../components/ui/dialog";
// Helper to compute tenure from date of joining
function calculateTenure(dateString) {
  if (!dateString) return "N/A";
  const start = new Date(dateString);
  if (isNaN(start.getTime())) return "N/A";
  const now = new Date();
  let years = now.getFullYear() - start.getFullYear();
  let months = now.getMonth() - start.getMonth();
  if (months < 0) {
    years--;
    months += 12;
  }
  if (years <= 0 && months <= 0) return "Recently Joined";
  if (years === 0) return `${months} mo${months > 1 ? "s" : ""}`;
  if (months === 0) return `${years} yr${years > 1 ? "s" : ""}`;
  return `${years} yr${years > 1 ? "s" : ""} ${months} mo${months > 1 ? "s" : ""}`;
}

export function DetailedEmployeeProfile({
  emp,
  employees = [],
  canManage = false,
  onEdit,
  isSelf = false,
  onClose,
}) {
  const [activeTab, setActiveTab] = useState("overview");
  const [copiedField, setCopiedField] = useState(null);

  const copyToClipboard = (text, field) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const tenure = calculateTenure(emp?.date_of_joining);
  const annualSalary = Number(emp?.basic_salary || 0);
  const monthlySalary = Math.round(annualSalary / 12);
  const biweeklySalary = Math.round(annualSalary / 26);
  const dailySalary = Math.round(annualSalary / 260);

  const manager = employees.find(
    (e) =>
      e.name === emp?.reporting_manager ||
      e.naming_series === emp?.reporting_manager ||
      (emp?.reporting_manager &&
        e.full_name &&
        e.full_name.toLowerCase() === emp.reporting_manager.toLowerCase())
  );

  const directReports = employees.filter(
    (e) =>
      e.name !== emp?.name &&
      (e.reporting_manager === emp?.name ||
        e.reporting_manager === emp?.naming_series ||
        (emp?.full_name &&
          e.reporting_manager &&
          e.reporting_manager.toLowerCase() === emp.full_name.toLowerCase()))
  );

  const skillList = emp?.skills
    ? emp.skills
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
    : [];

  return (
    <div className="space-y-6">
      {/* 1. HERO BANNER */}
      <div className="relative rounded-2xl overflow-hidden bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 dark:from-slate-950 dark:via-indigo-950 dark:to-slate-900 theme-blue:from-[#0b1329] theme-blue:via-[#111c3a] theme-blue:to-[#0b1329] p-6 sm:p-7 text-white shadow-xl border border-indigo-500/20 dark:border-slate-800 theme-blue:border-[#1c2d58]">
        {/* Ambient Glows */}
        <div className="absolute top-0 right-0 -mt-10 -mr-10 w-64 h-64 rounded-full bg-indigo-500/10 blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-1/4 -mb-10 w-48 h-48 rounded-full bg-sky-500/10 blur-2xl pointer-events-none" />

        <div className="relative flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5">
            {/* Avatar Squircle with Active Indicator */}
            <div className="relative shrink-0">
              <div className="h-20 w-20 sm:h-24 sm:w-24 rounded-2xl bg-white/10 dark:bg-slate-800/60 backdrop-blur-md p-1.5 ring-4 ring-white/15 dark:ring-white/10 shadow-2xl flex items-center justify-center">
                <div className="h-full w-full rounded-xl bg-gradient-to-tr from-indigo-500 via-purple-600 to-sky-500 flex items-center justify-center text-white font-extrabold text-3xl sm:text-4xl shadow-inner">
                  {emp?.full_name ? emp.full_name[0].toUpperCase() : "E"}
                </div>
              </div>
              <span
                className={`absolute -bottom-1 -right-1 h-5 w-5 rounded-full border-2 border-slate-900 ${
                  emp?.status === "Active"
                    ? "bg-emerald-500"
                    : emp?.status === "On Leave"
                    ? "bg-amber-500"
                    : "bg-slate-400"
                }`}
                title={`Status: ${emp?.status || "Active"}`}
              />
            </div>

            {/* Core Info */}
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-1.5">
                <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
                  {emp?.full_name || "Employee Profile"}
                </h2>
                <div className="inline-flex items-center gap-1 bg-white/15 hover:bg-white/20 backdrop-blur-xs px-2.5 py-1 rounded-lg border border-white/20 text-xs font-mono font-medium text-white transition-colors">
                  <span>{emp?.naming_series || emp?.name || "ID"}</span>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(emp?.naming_series || emp?.name, "id")}
                    className="hover:text-indigo-200 transition-colors p-0.5 ml-0.5 cursor-pointer"
                    title="Copy Employee ID"
                  >
                    {copiedField === "id" ? (
                      <Check className="h-3 w-3 text-emerald-300" />
                    ) : (
                      <Copy className="h-3 w-3" />
                    )}
                  </button>
                </div>
              </div>

              <p className="text-indigo-200 font-medium text-sm flex flex-wrap items-center gap-x-2 gap-y-1">
                <span>{emp?.designation || "Designation Unassigned"}</span>
                <span className="opacity-40">•</span>
                <span>{emp?.department || "Department Unassigned"}</span>
              </p>

              <div className="flex flex-wrap items-center gap-2 mt-3 text-xs">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 backdrop-blur-xs font-medium">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  {emp?.status || "Active"} Employee
                </span>
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-white/10 text-indigo-100 border border-white/15 backdrop-blur-xs">
                  <Briefcase className="h-3.5 w-3.5 text-indigo-300" />
                  {emp?.employment_type || "Full-Time"}
                </span>
                {emp?.date_of_joining && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-white/10 text-indigo-100 border border-white/15 backdrop-blur-xs">
                    <Clock className="h-3.5 w-3.5 text-indigo-300" />
                    Tenure: {tenure}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Quick Action Buttons */}
          <div className="flex items-center gap-2 self-start md:self-center shrink-0">
            {emp?.email && (
              <a
                href={`mailto:${emp.email}`}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white text-xs font-semibold backdrop-blur-xs transition-all border border-white/15 shadow-xs"
              >
                <Mail className="h-3.5 w-3.5" />
                <span>Send Email</span>
              </a>
            )}
            {canManage && onEdit && (
              <Button
                onClick={() => onEdit(emp)}
                className="bg-white text-indigo-800 hover:bg-slate-100 dark:bg-slate-100 dark:text-indigo-900 font-semibold shadow-md text-xs px-3.5 py-2 h-auto rounded-xl"
              >
                <Edit className="h-3.5 w-3.5 mr-1.5" />
                Edit Profile
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* 2. KEY METRIC STRIP */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 theme-blue:bg-[#152347] border border-slate-200/80 dark:border-slate-800 theme-blue:border-[#1c2d58] transition-all hover:shadow-xs">
          <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 theme-blue:text-slate-300 text-xs font-medium mb-1">
            <Building2 className="h-4 w-4 text-indigo-500" />
            <span>Department</span>
          </div>
          <div className="font-bold text-slate-900 dark:text-slate-100 theme-blue:text-white text-sm truncate">
            {emp?.department || "Unassigned"}
          </div>
          <div className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">
            {emp?.employment_type || "Standard Role"}
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 theme-blue:bg-[#152347] border border-slate-200/80 dark:border-slate-800 theme-blue:border-[#1c2d58] transition-all hover:shadow-xs">
          <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 theme-blue:text-slate-300 text-xs font-medium mb-1">
            <Clock className="h-4 w-4 text-sky-500" />
            <span>Tenure</span>
          </div>
          <div className="font-bold text-slate-900 dark:text-slate-100 theme-blue:text-white text-sm truncate">
            {tenure}
          </div>
          <div className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">
            Joined {emp?.date_of_joining || "N/A"}
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 theme-blue:bg-[#152347] border border-slate-200/80 dark:border-slate-800 theme-blue:border-[#1c2d58] transition-all hover:shadow-xs">
          <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 theme-blue:text-slate-300 text-xs font-medium mb-1">
            <DollarSign className="h-4 w-4 text-emerald-500" />
            <span>Annual Base</span>
          </div>
          <div className="font-bold text-emerald-600 dark:text-emerald-400 text-sm">
            ${annualSalary.toLocaleString()}
          </div>
          <div className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">
            ~${monthlySalary.toLocaleString()} / mo
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 theme-blue:bg-[#152347] border border-slate-200/80 dark:border-slate-800 theme-blue:border-[#1c2d58] transition-all hover:shadow-xs">
          <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 theme-blue:text-slate-300 text-xs font-medium mb-1">
            <Users className="h-4 w-4 text-violet-500" />
            <span>Reporting Hierarchy</span>
          </div>
          <div
            className="font-bold text-slate-900 dark:text-slate-100 theme-blue:text-white text-sm truncate"
            title={manager ? manager.full_name : "Direct Executive Tier"}
          >
            {manager ? manager.full_name : (emp?.reporting_manager || "Executive Tier")}
          </div>
          <div className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">
            {directReports.length} direct report{directReports.length === 1 ? "" : "s"}
          </div>
        </div>
      </div>

      {/* 3. INTERACTIVE NAVIGATION TABS */}
      <div className="border-b border-slate-200 dark:border-slate-800 theme-blue:border-[#1c2d58]">
        <nav className="flex space-x-2 overflow-x-auto pb-px" aria-label="Tabs">
          {[
            { id: "overview", label: "Position & Hierarchy", icon: Briefcase },
            { id: "contact", label: "Contact & Security", icon: Mail },
            { id: "compensation", label: "Compensation Breakdown", icon: DollarSign },
            { id: "skills", label: `Skills & Competencies (${skillList.length})`, icon: Award },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold transition-all border-b-2 whitespace-nowrap cursor-pointer ${
                  isActive
                    ? "border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400 font-bold"
                    : "border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 theme-blue:hover:text-white"
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* 4. TAB CONTENTS */}
      {activeTab === "overview" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-in fade-in duration-150">
          {/* Role Specification Card */}
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 theme-blue:bg-[#111c3a] border border-slate-200 dark:border-slate-800 theme-blue:border-[#1c2d58] shadow-xs space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 flex items-center gap-1.5">
              <Briefcase className="h-3.5 w-3.5 text-indigo-500" />
              Role & Employment Details
            </h4>
            <div className="space-y-3 text-xs">
              <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800/80 theme-blue:border-[#1c2d58]">
                <span className="text-slate-500 dark:text-slate-400">Designation</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200 theme-blue:text-white">
                  {emp?.designation || "Not specified"}
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800/80 theme-blue:border-[#1c2d58]">
                <span className="text-slate-500 dark:text-slate-400">Department</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200 theme-blue:text-white">
                  {emp?.department || "Not specified"}
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800/80 theme-blue:border-[#1c2d58]">
                <span className="text-slate-500 dark:text-slate-400">Employment Type</span>
                <span className="font-medium text-slate-800 dark:text-slate-200 theme-blue:text-white">
                  {emp?.employment_type || "Full-Time"}
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800/80 theme-blue:border-[#1c2d58]">
                <span className="text-slate-500 dark:text-slate-400">Date of Joining</span>
                <span className="font-medium text-slate-800 dark:text-slate-200 theme-blue:text-white">
                  {emp?.date_of_joining || "N/A"}
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800/80 theme-blue:border-[#1c2d58]">
                <span className="text-slate-500 dark:text-slate-400">Calculated Service Tenure</span>
                <span className="font-medium text-slate-800 dark:text-slate-200 theme-blue:text-white">
                  {tenure}
                </span>
              </div>
              <div className="flex justify-between py-1.5">
                <span className="text-slate-500 dark:text-slate-400">Employee Identification</span>
                <span className="font-mono text-xs font-semibold text-indigo-600 dark:text-indigo-400">
                  {emp?.naming_series || emp?.name}
                </span>
              </div>
            </div>
          </div>

          {/* Hierarchy & Reporting Card */}
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 theme-blue:bg-[#111c3a] border border-slate-200 dark:border-slate-800 theme-blue:border-[#1c2d58] shadow-xs space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 flex items-center gap-1.5">
              <Users className="h-3.5 w-3.5 text-indigo-500" />
              Organizational Tree & Direct Line
            </h4>

            {/* Reporting Manager */}
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 theme-blue:bg-[#152347] border border-slate-200/60 dark:border-slate-700/60 theme-blue:border-[#1c2d58]">
              <div className="text-[11px] font-semibold text-slate-400 dark:text-slate-400 mb-2 uppercase tracking-wider">
                Direct Supervisor / Manager
              </div>
              {manager ? (
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-500 to-sky-500 flex items-center justify-center text-white font-bold text-sm shrink-0 shadow-xs">
                    {manager.full_name ? manager.full_name[0] : "M"}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-bold text-slate-900 dark:text-slate-100 theme-blue:text-white truncate">
                      {manager.full_name}
                    </div>
                    <div className="text-xs text-slate-500 dark:text-slate-400 truncate">
                      {manager.designation} • {manager.department}
                    </div>
                  </div>
                  {manager.email && (
                    <a
                      href={`mailto:${manager.email}`}
                      className="text-slate-400 hover:text-indigo-600 p-1.5 rounded-lg hover:bg-white dark:hover:bg-slate-700 transition-colors"
                      title={`Email ${manager.full_name}`}
                    >
                      <Mail className="h-4 w-4" />
                    </a>
                  )}
                </div>
              ) : (
                <div className="flex items-center gap-2.5 text-xs text-slate-600 dark:text-slate-300">
                  <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                  <span>
                    {emp?.reporting_manager
                      ? `Assigned: ${emp.reporting_manager}`
                      : "Direct Executive / No intermediate manager"}
                  </span>
                </div>
              )}
            </div>

            {/* Direct Reports */}
            <div>
              <div className="text-[11px] font-semibold text-slate-400 dark:text-slate-400 mb-2 uppercase tracking-wider flex items-center justify-between">
                <span>Direct Reports</span>
                <span className="text-indigo-600 dark:text-indigo-400 font-bold">
                  {directReports.length} {directReports.length === 1 ? "Person" : "People"}
                </span>
              </div>
              {directReports.length > 0 ? (
                <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                  {directReports.map((report) => (
                    <div
                      key={report.name || report.naming_series}
                      className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/40 theme-blue:bg-[#152347]/60 border border-slate-100 dark:border-slate-800 text-xs"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div className="h-7 w-7 rounded-lg bg-indigo-100 dark:bg-indigo-900/60 text-indigo-700 dark:text-indigo-300 flex items-center justify-center font-bold text-xs shrink-0">
                          {report.full_name ? report.full_name[0] : "R"}
                        </div>
                        <div className="min-w-0">
                          <p className="font-semibold text-slate-800 dark:text-slate-200 theme-blue:text-white truncate">
                            {report.full_name}
                          </p>
                          <p className="text-[11px] text-slate-400 truncate">
                            {report.designation || report.department}
                          </p>
                        </div>
                      </div>
                      <Badge variant="outline" className="text-[10px] shrink-0 ml-2">
                        {report.naming_series || report.name}
                      </Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 dark:text-slate-500 italic p-3 rounded-lg bg-slate-50 dark:bg-slate-800/30 text-center">
                  No direct reports currently reporting to this employee.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === "contact" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-in fade-in duration-150">
          {/* Primary Communication Channels */}
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 theme-blue:bg-[#111c3a] border border-slate-200 dark:border-slate-800 theme-blue:border-[#1c2d58] shadow-xs space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 flex items-center gap-1.5">
              <Mail className="h-3.5 w-3.5 text-indigo-500" />
              Direct Communication Channels
            </h4>

            {/* Email Card */}
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 theme-blue:bg-[#152347] border border-slate-200/70 dark:border-slate-700/60 theme-blue:border-[#1c2d58]">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">
                  Corporate Email
                </span>
                <span className="text-[10px] text-emerald-500 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3" /> Primary
                </span>
              </div>
              <div className="flex items-center justify-between gap-2 mt-1">
                <span className="text-sm font-semibold text-slate-800 dark:text-slate-200 theme-blue:text-white truncate">
                  {emp?.email || "No email on record"}
                </span>
                <div className="flex items-center gap-1 shrink-0">
                  {emp?.email && (
                    <>
                      <button
                        type="button"
                        onClick={() => copyToClipboard(emp.email, "email")}
                        className="p-1.5 text-slate-400 hover:text-indigo-600 rounded-lg hover:bg-white dark:hover:bg-slate-700 transition-colors cursor-pointer"
                        title="Copy email address"
                      >
                        {copiedField === "email" ? (
                          <Check className="h-4 w-4 text-emerald-500" />
                        ) : (
                          <Copy className="h-4 w-4" />
                        )}
                      </button>
                      <a
                        href={`mailto:${emp.email}`}
                        className="p-1.5 text-slate-400 hover:text-indigo-600 rounded-lg hover:bg-white dark:hover:bg-slate-700 transition-colors"
                        title="Send email"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Phone Card */}
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 theme-blue:bg-[#152347] border border-slate-200/70 dark:border-slate-700/60 theme-blue:border-[#1c2d58]">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">
                  Direct Telephone / Mobile
                </span>
                <span className="text-[10px] text-indigo-500 font-semibold">Voice & SMS</span>
              </div>
              <div className="flex items-center justify-between gap-2 mt-1">
                <span className="text-sm font-semibold text-slate-800 dark:text-slate-200 theme-blue:text-white truncate">
                  {emp?.phone || "No phone number on record"}
                </span>
                <div className="flex items-center gap-1 shrink-0">
                  {emp?.phone && (
                    <>
                      <button
                        type="button"
                        onClick={() => copyToClipboard(emp.phone, "phone")}
                        className="p-1.5 text-slate-400 hover:text-indigo-600 rounded-lg hover:bg-white dark:hover:bg-slate-700 transition-colors cursor-pointer"
                        title="Copy phone number"
                      >
                        {copiedField === "phone" ? (
                          <Check className="h-4 w-4 text-emerald-500" />
                        ) : (
                          <Copy className="h-4 w-4" />
                        )}
                      </button>
                      <a
                        href={`tel:${emp.phone}`}
                        className="p-1.5 text-slate-400 hover:text-indigo-600 rounded-lg hover:bg-white dark:hover:bg-slate-700 transition-colors"
                        title="Call direct"
                      >
                        <Phone className="h-4 w-4" />
                      </a>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Security & Access Profile */}
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 theme-blue:bg-[#111c3a] border border-slate-200 dark:border-slate-800 theme-blue:border-[#1c2d58] shadow-xs space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
              Security & Identity Access
            </h4>
            <div className="space-y-3 text-xs">
              <div className="flex justify-between py-2 border-b border-slate-100 dark:border-slate-800 theme-blue:border-[#1c2d58]">
                <span className="text-slate-500 dark:text-slate-400">Frappe System User ID</span>
                <span className="font-mono font-medium text-slate-800 dark:text-slate-200 theme-blue:text-white truncate max-w-[180px]">
                  {emp?.user_id || emp?.email || "Synced User"}
                </span>
              </div>
              <div className="flex justify-between py-2 border-b border-slate-100 dark:border-slate-800 theme-blue:border-[#1c2d58]">
                <span className="text-slate-500 dark:text-slate-400">Portal Security Role</span>
                <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                  {emp?.user_id === "Administrator" ? "System Administrator" : "Employee Portal User"}
                </span>
              </div>
              <div className="flex justify-between py-2 border-b border-slate-100 dark:border-slate-800 theme-blue:border-[#1c2d58]">
                <span className="text-slate-500 dark:text-slate-400">Authentication Method</span>
                <span className="font-medium text-slate-800 dark:text-slate-200 theme-blue:text-white">
                  Corporate Email SSO / Password
                </span>
              </div>
              <div className="flex justify-between py-2">
                <span className="text-slate-500 dark:text-slate-400">Account Authorization</span>
                <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-semibold">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Verified & Active
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === "compensation" && (
        <div className="space-y-4 animate-in fade-in duration-150">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 theme-blue:bg-[#111c3a] border border-slate-200 dark:border-slate-800 theme-blue:border-[#1c2d58] shadow-xs md:col-span-2 space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 flex items-center gap-1.5">
                  <DollarSign className="h-3.5 w-3.5 text-emerald-500" />
                  Annual Base Compensation
                </h4>
                <Badge variant="success" className="text-xs">
                  Salary Grade Active
                </Badge>
              </div>

              <div className="flex items-baseline gap-2">
                <span className="text-3xl sm:text-4xl font-black text-emerald-600 dark:text-emerald-400">
                  ${annualSalary.toLocaleString()}
                </span>
                <span className="text-sm font-medium text-slate-400">USD / Year</span>
              </div>

              <div className="grid grid-cols-3 gap-3 pt-4 border-t border-slate-100 dark:border-slate-800 theme-blue:border-[#1c2d58]">
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 theme-blue:bg-[#152347]">
                  <span className="text-[11px] text-slate-400 block font-medium">Monthly Est.</span>
                  <span className="text-sm font-bold text-slate-800 dark:text-slate-200 theme-blue:text-white">
                    ${monthlySalary.toLocaleString()}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 theme-blue:bg-[#152347]">
                  <span className="text-[11px] text-slate-400 block font-medium">Bi-Weekly Est.</span>
                  <span className="text-sm font-bold text-slate-800 dark:text-slate-200 theme-blue:text-white">
                    ${biweeklySalary.toLocaleString()}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 theme-blue:bg-[#152347]">
                  <span className="text-[11px] text-slate-400 block font-medium">Daily Rate (~260d)</span>
                  <span className="text-sm font-bold text-slate-800 dark:text-slate-200 theme-blue:text-white">
                    ${dailySalary.toLocaleString()}
                  </span>
                </div>
              </div>
            </div>

            <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 theme-blue:bg-[#111c3a] border border-slate-200 dark:border-slate-800 theme-blue:border-[#1c2d58] shadow-xs space-y-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Disbursement Policy
              </h4>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                Compensation is disbursed according to corporate payroll cycle schedules.
                Statutory deductions, benefits packages, and performance bonuses are processed separately in the Payroll ledger.
              </p>
              <div className="pt-2 text-[11px] text-indigo-600 dark:text-indigo-400 font-medium leading-relaxed">
                • Currency: US Dollar (USD)
                <br />
                • Direct Deposit: Automated
                <br />
                • Tax Compliance: Form W-2 / W-4
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === "skills" && (
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 theme-blue:bg-[#111c3a] border border-slate-200 dark:border-slate-800 theme-blue:border-[#1c2d58] shadow-xs space-y-5 animate-in fade-in duration-150">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100 theme-blue:text-white flex items-center gap-2">
                <Award className="h-4 w-4 text-indigo-500" />
                Specialized Competencies & Skill Matrix
              </h4>
              <p className="text-xs text-slate-400 mt-0.5">
                Verified functional, technical, and operational skill qualifications
              </p>
            </div>
            <Badge variant="secondary" className="px-3 py-1 font-semibold">
              {skillList.length} Verified Skill{skillList.length === 1 ? "" : "s"}
            </Badge>
          </div>

          {skillList.length > 0 ? (
            <div className="flex flex-wrap gap-2.5 pt-2">
              {skillList.map((skill, idx) => (
                <div
                  key={idx}
                  className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-indigo-50/70 dark:bg-indigo-950/40 theme-blue:bg-[#1c2d58]/60 border border-indigo-200/80 dark:border-indigo-800/60 text-indigo-900 dark:text-indigo-200 theme-blue:text-indigo-200 text-xs font-semibold shadow-2xs hover:scale-105 transition-transform"
                >
                  <span className="h-2 w-2 rounded-full bg-indigo-500" />
                  <span>{skill}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-10 border border-dashed border-slate-200 dark:border-slate-800 theme-blue:border-[#1c2d58] rounded-xl">
              <Award className="h-10 w-10 text-slate-300 dark:text-slate-600 mx-auto mb-2" />
              <p className="text-sm font-medium text-slate-600 dark:text-slate-400">
                No verified skills recorded yet
              </p>
              <p className="text-xs text-slate-400 mt-1">
                Edit this employee record to assign skills, certifications, and technical domains.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Footer close button for modal dialog view */}
      {onClose && (
        <div className="pt-3 border-t border-slate-100 dark:border-slate-800 theme-blue:border-[#1c2d58] flex justify-end">
          <Button onClick={onClose} variant="outline" className="text-xs px-4">
            Close Record
          </Button>
        </div>
      )}
    </div>
  );
}

export function EmployeeModule({
  employees = [],
  departments = [],
  userRole = "Administrator",
  currentUser = {},
  onAddEmployee,
  onUpdateEmployee,
  onDeleteEmployee,
  searchQuery = "",
  autoOpenAdd = false,
  onResetAutoOpenAdd,
}) {
  const [viewMode, setViewMode] = useState("grid");
  const [selectedDeptFilter, setSelectedDeptFilter] = useState("ALL");
  const [selectedStatusFilter, setSelectedStatusFilter] = useState("ALL");
  const [selectedTypeFilter, setSelectedTypeFilter] = useState("ALL");
  const [localSearch, setLocalSearch] = useState("");

  const [isAddOpen, setIsAddOpen] = useState(false);
  const [editingEmp, setEditingEmp] = useState(null);
  const [viewingEmp, setViewingEmp] = useState(null);

  const canManage = userRole === "Administrator" || userRole === "HR";
  const isEmployeeRole = userRole === "Employee";

  const isProtectedRecord = (emp) => {
    if (!emp) return false;
    const id = (emp.name || emp.naming_series || "").trim();
    const userId = (emp.user_id || emp.email || "").toLowerCase().trim();
    const currentEmpId = (currentUser?.employee?.name || currentUser?.employee?.naming_series || "").trim();
    const currentUserId = (currentUser?.user || currentUser?.email || "").toLowerCase().trim();

    if (id === "EMP-001" || userId === "admin@ems.com" || userId === "administrator") {
      return true;
    }
    if (currentEmpId && id === currentEmpId) {
      return true;
    }
    if (currentUserId && userId === currentUserId) {
      return true;
    }
    return false;
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
    setEditingEmp(null);
    setIsAddOpen(true);
  };

  useEffect(() => {
    if (autoOpenAdd) {
      const timer = setTimeout(() => {
        handleOpenAdd();
        if (onResetAutoOpenAdd) onResetAutoOpenAdd();
      }, 50);
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoOpenAdd]);

  const handleOpenEdit = (emp) => {
    setEditingEmp(emp);
    setFormData({ ...emp });
    setIsAddOpen(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!formData.full_name || !formData.email?.trim()) return;

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

    if (editingEmp) {
      await onUpdateEmployee(payload);
    } else {
      await onAddEmployee({ ...payload, name: payload.naming_series });
    }
    setIsAddOpen(false);
  };

  // Filter Logic
  const effectiveSearch = (searchQuery || localSearch).toLowerCase();
  const filteredEmployees = employees.filter((emp) => {
    const matchesSearch =
      emp.full_name?.toLowerCase().includes(effectiveSearch) ||
      emp.email?.toLowerCase().includes(effectiveSearch) ||
      emp.naming_series?.toLowerCase().includes(effectiveSearch) ||
      emp.designation?.toLowerCase().includes(effectiveSearch);

    const matchesDept = selectedDeptFilter === "ALL" || emp.department === selectedDeptFilter;
    const matchesStatus = selectedStatusFilter === "ALL" || emp.status === selectedStatusFilter;
    const matchesType = selectedTypeFilter === "ALL" || emp.employment_type === selectedTypeFilter;

    return matchesSearch && matchesDept && matchesStatus && matchesType;
  });

  // If Employee role: render their personal profile view directly
  const userIdentifier = (currentUser?.email || currentUser?.user || "").toLowerCase();
  const myEmployee =
    currentUser?.employee ||
    employees.find(
      (e) =>
        (e.user_id && e.user_id.toLowerCase() === userIdentifier) ||
        (e.email && e.email.toLowerCase() === userIdentifier) ||
        (currentUser?.user && e.user_id === currentUser.user) ||
        (currentUser?.email && e.email === currentUser.email)
    ) ||
    (employees.length === 1 && (employees[0]?.user_id === currentUser?.user || employees[0]?.email === currentUser?.email)
      ? employees[0]
      : employees.length === 1
      ? employees[0]
      : null);

  if (isEmployeeRole) {
    if (!myEmployee) {
      return (
        <div className="space-y-6 animate-in fade-in duration-300 max-w-4xl mx-auto p-12 text-center bg-white dark:bg-slate-900 theme-blue:bg-[#111c3a] rounded-2xl border border-slate-200 dark:border-slate-800 theme-blue:border-[#1c2d58] shadow-sm">
          <UserCheck className="h-12 w-12 text-slate-400 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-slate-800 dark:text-slate-200 theme-blue:text-white">
            No Employee Profile Linked
          </h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 theme-blue:text-slate-300 mt-1 max-w-md mx-auto">
            Your user account ({currentUser?.email || currentUser?.user}) is not linked to an active Employee record yet. Please contact your administrator or HR manager to link your profile.
          </p>
        </div>
      );
    }

    return (
      <div className="space-y-6 animate-in fade-in duration-300 max-w-5xl mx-auto">
        <DetailedEmployeeProfile
          emp={myEmployee}
          employees={employees}
          canManage={false}
          isSelf={true}
        />
      </div>
    );
  }

  // Administrator & HR directory view
  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center space-x-2">
            <Users className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
            <span>Employee Directory</span>
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Manage employee master data, designations, managers, and profiles
          </p>
        </div>

        {canManage && (
          <Button onClick={handleOpenAdd} className="bg-indigo-600 hover:bg-indigo-700 font-semibold shadow-md cursor-pointer">
            <Plus className="mr-2 h-4 w-4" /> Add Employee
          </Button>
        )}
      </div>

      {/* Filter and View Control Toolbar */}
      <Card className="p-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3 flex-1">
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <Input
                placeholder="Filter by name, email, ID..."
                className="pl-9 text-sm"
                value={localSearch}
                onChange={(e) => setLocalSearch(e.target.value)}
              />
            </div>

            <Select
              className="w-full sm:w-44 text-sm"
              value={selectedDeptFilter}
              onChange={(e) => setSelectedDeptFilter(e.target.value)}
            >
              <option value="ALL">All Departments</option>
              {departments.map((d) => (
                <option key={d.name} value={d.department_name}>
                  {d.department_name}
                </option>
              ))}
            </Select>

            <Select
              className="w-full sm:w-36 text-sm"
              value={selectedStatusFilter}
              onChange={(e) => setSelectedStatusFilter(e.target.value)}
            >
              <option value="ALL">All Status</option>
              <option value="Active">Active</option>
              <option value="Inactive">Inactive</option>
              <option value="On Leave">On Leave</option>
            </Select>

            <Select
              className="w-full sm:w-40 text-sm"
              value={selectedTypeFilter}
              onChange={(e) => setSelectedTypeFilter(e.target.value)}
            >
              <option value="ALL">All Types</option>
              <option value="Full-Time">Full-Time</option>
              <option value="Part-Time">Part-Time</option>
              <option value="Contract">Contract</option>
              <option value="Intern">Intern</option>
            </Select>
          </div>

          <div className="flex items-center space-x-1 border border-slate-200 dark:border-slate-700 rounded-lg p-1 bg-slate-50 dark:bg-slate-800 shrink-0 self-end md:self-auto">
            <button
              onClick={() => setViewMode("grid")}
              className={`p-1.5 rounded-md transition-colors cursor-pointer ${
                viewMode === "grid" ? "bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-400 shadow-xs" : "text-slate-500 hover:text-slate-900 dark:text-slate-400"
              }`}
              title="Grid View"
            >
              <Grid className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode("table")}
              className={`p-1.5 rounded-md transition-colors cursor-pointer ${
                viewMode === "table" ? "bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-400 shadow-xs" : "text-slate-500 hover:text-slate-900 dark:text-slate-400"
              }`}
              title="Table View"
            >
              <List className="h-4 w-4" />
            </button>
          </div>
        </div>
      </Card>

      {/* Main Content: Grid or Table */}
      {viewMode === "grid" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredEmployees.map((emp) => (
            <Card key={emp.naming_series || emp.name} className="overflow-hidden hover:shadow-lg transition-all group">
              <CardContent className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="relative">
                      {emp.profile_image ? (
                        <img
                          src={emp.profile_image}
                          alt={emp.full_name}
                          className="h-12 w-12 rounded-full object-cover ring-2 ring-indigo-100"
                        />
                      ) : (
                        <div className="h-12 w-12 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-lg">
                          {emp.full_name ? emp.full_name[0] : "E"}
                        </div>
                      )}
                      <span
                        className={`absolute bottom-0 right-0 h-3 w-3 rounded-full ring-2 ring-white dark:ring-slate-900 ${
                          emp.status === "Active"
                            ? "bg-emerald-500"
                            : emp.status === "On Leave"
                            ? "bg-amber-500"
                            : "bg-slate-400"
                        }`}
                      />
                    </div>

                    <div>
                      <h3 className="font-bold text-slate-900 dark:text-slate-100 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                        {emp.full_name}
                      </h3>
                      <p className="text-xs text-slate-500 dark:text-slate-400 font-mono">{emp.naming_series || emp.name}</p>
                    </div>
                  </div>

                  <Badge
                    variant={
                      emp.status === "Active"
                        ? "success"
                        : emp.status === "On Leave"
                        ? "warning"
                        : "secondary"
                    }
                  >
                    {emp.status}
                  </Badge>
                </div>

                <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 space-y-2 text-xs text-slate-600 dark:text-slate-300">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400 flex items-center gap-1.5">
                      <Briefcase className="h-3.5 w-3.5 text-indigo-500" /> Designation
                    </span>
                    <span className="font-medium text-slate-800 dark:text-slate-200">{emp.designation || "N/A"}</span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-slate-400 flex items-center gap-1.5">
                      <Building2 className="h-3.5 w-3.5 text-indigo-500" /> Department
                    </span>
                    <span className="font-medium text-slate-800 dark:text-slate-200">{emp.department || "Unassigned"}</span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-slate-400 flex items-center gap-1.5">
                      <Mail className="h-3.5 w-3.5 text-indigo-500" /> Email
                    </span>
                    <span className="font-medium text-slate-800 dark:text-slate-200 truncate max-w-[160px]">{emp.email || "N/A"}</span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-slate-400 flex items-center gap-1.5">
                      <DollarSign className="h-3.5 w-3.5 text-emerald-500" /> Basic Salary
                    </span>
                    <span className="font-bold text-slate-900 dark:text-slate-100">${Number(emp.basic_salary || 0).toLocaleString()}</span>
                  </div>
                </div>

                {/* Actions Footer */}
                <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-end space-x-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-8 text-xs text-slate-600 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400 cursor-pointer"
                    onClick={() => setViewingEmp(emp)}
                  >
                    <Eye className="mr-1 h-3.5 w-3.5" /> Details
                  </Button>

                  {canManage && (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-8 text-xs cursor-pointer"
                        onClick={() => handleOpenEdit(emp)}
                      >
                        <Edit className="mr-1 h-3.5 w-3.5" /> Edit
                      </Button>
                      {!isProtectedRecord(emp) && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-8 text-xs text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 cursor-pointer"
                          onClick={() => onDeleteEmployee(emp.name || emp.naming_series)}
                          title="Delete Employee"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        /* Table View */
        <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Employee ID</TableHead>
                <TableHead>Name & Email</TableHead>
                <TableHead>Department</TableHead>
                <TableHead>Designation</TableHead>
                <TableHead>Employment Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Basic Salary</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredEmployees.map((emp) => (
                <TableRow key={emp.naming_series || emp.name}>
                  <TableCell className="font-mono text-xs font-semibold text-slate-700 dark:text-slate-300">
                    {emp.naming_series || emp.name}
                  </TableCell>
                  <TableCell>
                    <div className="font-semibold text-slate-900 dark:text-slate-100">{emp.full_name}</div>
                    <div className="text-xs text-slate-400 dark:text-slate-500">{emp.email}</div>
                  </TableCell>
                  <TableCell className="text-slate-800 dark:text-slate-200">{emp.department}</TableCell>
                  <TableCell className="text-slate-800 dark:text-slate-200">{emp.designation}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{emp.employment_type}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        emp.status === "Active"
                          ? "success"
                          : emp.status === "On Leave"
                          ? "warning"
                          : "secondary"
                      }
                    >
                      {emp.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-semibold text-slate-900 dark:text-slate-100">
                    ${Number(emp.basic_salary || 0).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right space-x-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-8 text-xs text-slate-600 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400 cursor-pointer"
                      onClick={() => setViewingEmp(emp)}
                    >
                      <Eye className="h-3.5 w-3.5" />
                    </Button>
                    {canManage && (
                      <>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 text-xs cursor-pointer"
                          onClick={() => handleOpenEdit(emp)}
                        >
                          <Edit className="h-3.5 w-3.5" />
                        </Button>
                        {!isProtectedRecord(emp) && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-8 text-xs text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 cursor-pointer"
                            onClick={() => onDeleteEmployee(emp.name || emp.naming_series)}
                            title="Delete Employee"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Add / Edit Dialog Form with complete fields */}
      {canManage && (
        <Dialog
          isOpen={isAddOpen}
          onClose={() => setIsAddOpen(false)}
          title={editingEmp ? "Edit Employee Record" : "Create New Employee"}
          description={
            editingEmp
              ? "Update employee profile details."
              : "Fill out employee details. Login credentials (Username: Email, Password: Full Name without spaces) will be generated automatically."
          }
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
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                  Email * <span className="text-[10px] font-normal text-slate-500">(Used for login)</span>
                </label>
                <Input
                  type="email"
                  placeholder="john.doe@company.com"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  required
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                  Phone Number
                </label>
                <Input
                  placeholder="e.g. +91 98765 43210"
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
                  {employees
                    .filter((e) => (editingEmp ? (e.name || e.naming_series) !== (editingEmp.name || editingEmp.naming_series) : true))
                    .map((e) => (
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
              <Button type="submit" className="bg-indigo-600 hover:bg-indigo-700 font-semibold cursor-pointer">
                {editingEmp ? "Update Employee" : "Create Employee"}
              </Button>
            </div>
          </form>
        </Dialog>
      )}

      {/* View Detail Dialog */}
      {viewingEmp && (
        <Dialog
          isOpen={Boolean(viewingEmp)}
          onClose={() => setViewingEmp(null)}
          title="Official Personnel Record"
          description="Comprehensive employee record, organizational tree, credentials and compensation"
          maxWidth="max-w-4xl"
        >
          <DetailedEmployeeProfile
            emp={viewingEmp}
            employees={employees}
            canManage={canManage}
            onEdit={(emp) => {
              setViewingEmp(null);
              handleOpenEdit(emp);
            }}
            onClose={() => setViewingEmp(null)}
          />
        </Dialog>
      )}
    </div>
  );
}
