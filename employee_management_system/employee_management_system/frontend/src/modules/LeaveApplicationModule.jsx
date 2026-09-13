import { useState } from "react";
import {
  FileSpreadsheet,
  Plus,
  Search,
  CheckCircle2,
  XCircle,
  Clock,
  Trash2,
  Ban,
  AlertTriangle,
} from "lucide-react";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/ui/table";
import { ApplyLeaveDialog } from "../components/ApplyLeaveDialog";
import { Dialog } from "../components/ui/dialog";
import { apiCancelLeaveApplication } from "../services/apiService";

export function LeaveApplicationModule({
  leaveApplications = [],
  leaveTypes = [],
  employees = [],
  userRole = "Administrator",
  currentUser = {},
  onAddLeaveApplication,
  onUpdateLeaveStatus,
  onDeleteLeaveApplication,
  onRefreshData,
}) {
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [search, setSearch] = useState("");
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [cancellingApp, setCancellingApp] = useState(null);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelLoading, setCancelLoading] = useState(false);

  const canApprove = userRole === "Administrator" || userRole === "HR";

  const handleOpenCancel = (app) => {
    setCancellingApp(app);
    setCancelReason("");
    setCancelDialogOpen(true);
  };

  const handleConfirmCancel = async (e) => {
    e.preventDefault();
    if (!cancellingApp) return;

    setCancelLoading(true);
    try {
      await apiCancelLeaveApplication(cancellingApp.name, cancelReason);
      setCancelDialogOpen(false);
      setCancellingApp(null);
      if (onRefreshData) {
        await onRefreshData();
      } else if (onUpdateLeaveStatus) {
        onUpdateLeaveStatus(cancellingApp.name, "Cancelled");
      }
    } catch (err) {
      alert(err.message || "Failed to cancel leave application");
    } finally {
      setCancelLoading(false);
    }
  };

  const canCancelApp = (app) => {
    if (!app || app.status === "Cancelled" || app.status === "Rejected") return false;
    if (canApprove) return true;
    if (userRole === "Employee") {
      if (app.status === "Pending") return true;
      if (app.status === "Approved") {
        const today = new Date().toISOString().split("T")[0];
        return app.from_date > today;
      }
    }
    return false;
  };

  const handleOpenApply = () => {
    setIsAddOpen(true);
  };

  const filteredApplications = leaveApplications.filter((app) => {
    const matchesSearch =
      app.employee_name?.toLowerCase().includes(search.toLowerCase()) ||
      app.employee?.toLowerCase().includes(search.toLowerCase()) ||
      app.leave_type?.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === "ALL" || app.status === statusFilter;

    return matchesSearch && matchesStatus;
  });

  const pendingCount = leaveApplications.filter((l) => l.status === "Pending").length;
  const approvedCount = leaveApplications.filter((l) => l.status === "Approved").length;
  const rejectedCount = leaveApplications.filter((l) => l.status === "Rejected").length;

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center space-x-2">
            <FileSpreadsheet className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
            <span>{canApprove ? "Leave Applications Management" : "My Leave Requests"}</span>
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            {canApprove
              ? "Review staff leave applications, approve requests, and monitor department schedules"
              : "Submit time-off requests, track approval status, and view historical leaves"}
          </p>
        </div>
        <Button onClick={handleOpenApply} className="bg-indigo-600 hover:bg-indigo-700 font-semibold shadow-md cursor-pointer">
          <Plus className="mr-2 h-4 w-4" /> Apply for Leave
        </Button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="border-l-4 border-l-amber-500">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">Pending Approval</p>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">{pendingCount}</h3>
            </div>
            <Clock className="h-8 w-8 text-amber-500" />
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-emerald-500">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">Approved Requests</p>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">{approvedCount}</h3>
            </div>
            <CheckCircle2 className="h-8 w-8 text-emerald-500" />
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-rose-500">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">Rejected Requests</p>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">{rejectedCount}</h3>
            </div>
            <XCircle className="h-8 w-8 text-rose-500" />
          </CardContent>
        </Card>
      </div>

      {/* Filter Tabs */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <Input
              placeholder="Search by applicant or type..."
              className="pl-9 text-sm"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <div className="flex items-center space-x-1 border border-slate-200 dark:border-slate-700 rounded-lg p-1 bg-slate-50 dark:bg-slate-800">
            {["ALL", "Pending", "Approved", "Rejected", "Cancelled"].map((status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors cursor-pointer ${
                  statusFilter === status
                    ? "bg-white dark:bg-slate-700 text-indigo-700 dark:text-indigo-300 shadow-xs"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100"
                }`}
              >
                {status}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Applicant</TableHead>
              <TableHead>Leave Type</TableHead>
              <TableHead>From - To</TableHead>
              <TableHead>Total Days</TableHead>
              <TableHead>Reason</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Approver</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredApplications.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-8 text-slate-400 text-sm">
                  No leave applications found.
                </TableCell>
              </TableRow>
            ) : (
              filteredApplications.map((app, idx) => (
                <TableRow key={app.name || app.id || `leave-app-${idx}-${app.employee || ''}-${app.from_date || ''}`}>
                  <TableCell>
                    <div className="font-semibold text-slate-900 dark:text-slate-100">{app.employee_name}</div>
                    <div className="text-xs text-slate-400 dark:text-slate-500 font-mono">{app.employee}</div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{app.leave_type}</Badge>
                  </TableCell>
                  <TableCell className="text-xs text-slate-700 dark:text-slate-300 font-mono">
                    {app.from_date} to {app.to_date}
                  </TableCell>
                  <TableCell className="font-bold text-slate-900 dark:text-slate-100">{app.total_days} day(s)</TableCell>
                  <TableCell className="text-xs text-slate-500 dark:text-slate-400 max-w-[200px] truncate">
                    {app.reason || "No reason stated"}
                  </TableCell>
                  <TableCell>
                    {app.status === "Cancelled" ? (
                      <div>
                        <Badge className="bg-slate-100 text-slate-600 border-slate-300 dark:bg-slate-800 dark:text-slate-400">
                          Cancelled
                        </Badge>
                        {app.cancellation_reason && (
                          <div className="text-[10px] text-slate-400 italic truncate max-w-[120px]" title={app.cancellation_reason}>
                            {app.cancellation_reason}
                          </div>
                        )}
                      </div>
                    ) : (
                      <Badge
                        variant={
                          app.status === "Approved"
                            ? "success"
                            : app.status === "Pending"
                            ? "warning"
                            : "destructive"
                        }
                      >
                        {app.status}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-slate-600 dark:text-slate-400">
                    {app.status === "Cancelled" ? (
                      <span className="text-slate-400 text-[11px]">
                        Cancelled by {app.cancelled_by || "User"}
                      </span>
                    ) : (
                      app.approver_name || app.approver || "Pending Review"
                    )}
                  </TableCell>
                  <TableCell className="text-right space-x-1">
                    {canApprove && app.status === "Pending" && (
                      <>
                        <Button
                          size="sm"
                          variant="success"
                          className="h-8 text-xs px-2 cursor-pointer"
                          onClick={() => onUpdateLeaveStatus(app.name, "Approved")}
                          title="Approve Leave"
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          className="h-8 text-xs px-2 cursor-pointer"
                          onClick={() => onUpdateLeaveStatus(app.name, "Rejected")}
                          title="Reject Leave"
                        >
                          <XCircle className="h-3.5 w-3.5" />
                        </Button>
                      </>
                    )}
                    {canCancelApp(app) && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 text-xs text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-950/40 cursor-pointer"
                        onClick={() => handleOpenCancel(app)}
                        title="Cancel Leave Application"
                      >
                        <Ban className="h-3.5 w-3.5" />
                      </Button>
                    )}
                    {(canApprove || app.status === "Pending") && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 text-xs text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 cursor-pointer"
                        onClick={() => onDeleteLeaveApplication(app.name)}
                        title="Delete Application"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Cancel Leave Reason Dialog */}
      <Dialog
        isOpen={cancelDialogOpen}
        onClose={() => setCancelDialogOpen(false)}
        title="Cancel Leave Application"
      >
        <form onSubmit={handleConfirmCancel} className="space-y-4 pt-2">
          <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/50 text-amber-700 dark:text-amber-300 text-xs flex items-start space-x-2">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Confirm Leave Cancellation</p>
              <p className="text-[11px] mt-0.5">
                Cancelling this leave will automatically restore the employee&apos;s leave balance and revert any associated attendance records.
              </p>
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
              Reason for Cancellation (Optional)
            </label>
            <Input
              placeholder="e.g. Travel plans postponed, personal reasons..."
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              className="text-xs"
            />
          </div>

          <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100 dark:border-slate-800">
            <Button
              type="button"
              variant="outline"
              onClick={() => setCancelDialogOpen(false)}
              className="text-xs cursor-pointer"
            >
              Keep Leave
            </Button>
            <Button
              type="submit"
              disabled={cancelLoading}
              className="bg-rose-600 hover:bg-rose-700 text-white text-xs cursor-pointer"
            >
              {cancelLoading ? "Cancelling..." : "Confirm Cancellation"}
            </Button>
          </div>
        </form>
      </Dialog>

      {/* Apply Leave Modal */}
      <ApplyLeaveDialog
        isOpen={isAddOpen}
        onClose={() => setIsAddOpen(false)}
        onAddLeaveApplication={onAddLeaveApplication}
        leaveTypes={leaveTypes}
        employees={employees}
        userRole={userRole}
        currentUser={currentUser}
      />
    </div>
  );
}
