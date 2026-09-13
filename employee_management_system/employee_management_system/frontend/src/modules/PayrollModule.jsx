import { useState, useEffect } from "react";
import {
  CreditCard,
  Plus,
  Search,
  CheckCircle2,
  AlertCircle,
  Clock,
  Sparkles,
  RefreshCw,
  Calendar,
  Building2,
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
  apiGenerateBatchPayroll,
  apiFetchPayrollRuns,
} from "../services/apiService";

export function PayrollModule({
  departments = [],
  employees = [],
  onRefreshData,
}) {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [search, setSearch] = useState("");
  const [batchResult, setBatchResult] = useState(null);

  const currentYearMonth = `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, "0")}`;

  const [batchForm, setBatchForm] = useState({
    salary_month: currentYearMonth,
    department: "All Departments",
    designation: "All Designations",
    regenerate: false,
  });

  const loadPayrollRuns = async () => {
    setLoading(true);
    try {
      const data = await apiFetchPayrollRuns();
      if (Array.isArray(data)) {
        setRuns(data);
      }
    } catch (err) {
      console.error("Failed to load payroll runs:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPayrollRuns();
  }, []);

  const handleOpenRunModal = () => {
    setBatchForm({
      salary_month: currentYearMonth,
      department: "All Departments",
      designation: "All Designations",
      regenerate: false,
    });
    setBatchResult(null);
    setIsAddOpen(true);
  };

  const handleRunBatch = async (e) => {
    e.preventDefault();
    if (!batchForm.salary_month) return;

    setGenerating(true);
    setBatchResult(null);

    try {
      const res = await apiGenerateBatchPayroll({
        salary_month: batchForm.salary_month,
        department: batchForm.department !== "All Departments" ? batchForm.department : null,
        designation: batchForm.designation !== "All Designations" ? batchForm.designation : null,
        regenerate: batchForm.regenerate,
      });

      setBatchResult(res);
      loadPayrollRuns();
      if (onRefreshData) onRefreshData();
    } catch (err) {
      alert(err.message || "Failed to generate batch payroll");
    } finally {
      setGenerating(false);
    }
  };

  const filteredRuns = runs.filter(
    (p) =>
      (p.payroll_title || "").toLowerCase().includes(search.toLowerCase()) ||
      (p.salary_month || "").toLowerCase().includes(search.toLowerCase()) ||
      (p.department || "").toLowerCase().includes(search.toLowerCase())
  );

  const totalDisbursed = runs.reduce(
    (acc, curr) => acc + Number(curr.total_amount || 0),
    0
  );

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center space-x-2">
            <CreditCard className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
            <span>Payroll Execution & Batch Processing</span>
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Automate monthly salary calculation with Loss of Pay (LOP) integration and bulk slip generation
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            onClick={loadPayrollRuns}
            className="text-xs h-9 cursor-pointer"
            title="Refresh runs"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          </Button>
          <Button
            onClick={handleOpenRunModal}
            className="bg-indigo-600 hover:bg-indigo-700 font-semibold shadow-md cursor-pointer text-xs h-9"
          >
            <Plus className="mr-1.5 h-4 w-4" /> Run Payroll Batch
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="border-l-4 border-l-indigo-500">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">
                Total Payroll Batches
              </p>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">
                {runs.length} Runs
              </h3>
            </div>
            <CreditCard className="h-8 w-8 text-indigo-500" />
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-emerald-500">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">
                Total Net Disbursed
              </p>
              <h3 className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                ${totalDisbursed.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </h3>
            </div>
            <CheckCircle2 className="h-8 w-8 text-emerald-500" />
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-amber-500">
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">
                Active Staff Eligible
              </p>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">
                {employees.filter((e) => e.status !== "Inactive").length} Employees
              </h3>
            </div>
            <Clock className="h-8 w-8 text-amber-500" />
          </CardContent>
        </Card>
      </div>

      {/* Search & Filter Bar */}
      <Card className="p-4 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <Input
              placeholder="Search payroll runs by title, month, or department..."
              className="pl-9 text-xs"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
      </Card>

      {/* Payroll Runs History Table */}
      <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Payroll Batch</TableHead>
              <TableHead>Month</TableHead>
              <TableHead>Department</TableHead>
              <TableHead>Employees</TableHead>
              <TableHead>Processed / Skipped</TableHead>
              <TableHead>Failed</TableHead>
              <TableHead>Total Net Pay</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Run Date</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredRuns.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} className="text-center py-8 text-slate-400 text-sm">
                  No payroll batches recorded yet. Click &quot;Run Payroll Batch&quot; to generate slips.
                </TableCell>
              </TableRow>
            ) : (
              filteredRuns.map((p) => (
                <TableRow key={p.name}>
                  <TableCell>
                    <div className="font-semibold text-slate-900 dark:text-slate-100">
                      {p.payroll_title || p.name}
                    </div>
                    <div className="text-[10px] text-slate-400 font-mono">{p.name}</div>
                  </TableCell>
                  <TableCell className="font-mono text-xs font-medium text-indigo-600 dark:text-indigo-400">
                    {p.salary_month}
                  </TableCell>
                  <TableCell className="text-xs">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                      {p.department || "All"}
                    </span>
                  </TableCell>
                  <TableCell className="font-medium text-xs">
                    {p.total_employees || 0}
                  </TableCell>
                  <TableCell className="text-xs text-emerald-600 font-semibold">
                    {p.successful_slips || 0}
                  </TableCell>
                  <TableCell className="text-xs">
                    {p.failed_slips > 0 ? (
                      <span className="text-rose-600 font-bold">{p.failed_slips}</span>
                    ) : (
                      <span className="text-slate-400">0</span>
                    )}
                  </TableCell>
                  <TableCell className="font-bold text-slate-900 dark:text-slate-100">
                    ${Number(p.total_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        p.status === "Completed"
                          ? "success"
                          : p.status === "Processing"
                          ? "warning"
                          : "destructive"
                      }
                    >
                      {p.status || "Completed"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right text-xs text-slate-500">
                    {p.creation ? new Date(p.creation).toLocaleDateString() : "N/A"}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Generate Batch Payroll Modal */}
      <Dialog
        isOpen={isAddOpen}
        onClose={() => setIsAddOpen(false)}
        title="Run Batch Payroll Generation"
        maxWidth="max-w-lg"
      >
        <form onSubmit={handleRunBatch} className="space-y-4 pt-2">
          {batchResult && (
            <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/50 text-emerald-700 dark:text-emerald-300 text-xs">
              <div className="font-bold flex items-center mb-1">
                <CheckCircle2 className="h-4 w-4 mr-1.5 text-emerald-600" />
                <span>Batch Payroll Run Completed Successfully!</span>
              </div>
              <p className="text-[11px] leading-relaxed">
                Generated <strong>{batchResult.processed_slips}</strong> new slip(s),{" "}
                <strong>{batchResult.skipped_slips}</strong> existing slip(s) preserved.
                <br />
                Total Disbursement: <strong>${Number(batchResult.total_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
              </p>
            </div>
          )}

          <div className="p-3 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-900/50 text-indigo-700 dark:text-indigo-300 text-xs flex items-start space-x-2">
            <Sparkles className="h-4 w-4 shrink-0 text-indigo-500 mt-0.5" />
            <div className="text-[11px] leading-relaxed">
              <strong>Automated LOP & Attendance Integration:</strong>
              <br />
              Absent days and unpaid leaves are automatically retrieved from employee attendance records. Loss of pay is computed dynamically:
              <br />
              <code className="text-[10px] bg-indigo-100 dark:bg-indigo-900/60 px-1 py-0.5 rounded mt-0.5 inline-block">
                Daily Salary = Basic / Days in Month | LOP Deduction = Daily Salary * LOP Days
              </code>
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
              Salary Month (YYYY-MM) *
            </label>
            <Input
              type="month"
              required
              value={batchForm.salary_month}
              onChange={(e) => setBatchForm({ ...batchForm, salary_month: e.target.value })}
              className="text-xs"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Department
              </label>
              <Select
                value={batchForm.department}
                onChange={(e) => setBatchForm({ ...batchForm, department: e.target.value })}
              >
                <option value="All Departments">All Departments</option>
                {departments.map((d) => (
                  <option key={d.name} value={d.department_name}>
                    {d.department_name}
                  </option>
                ))}
              </Select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Designation
              </label>
              <Select
                value={batchForm.designation}
                onChange={(e) => setBatchForm({ ...batchForm, designation: e.target.value })}
              >
                <option value="All Designations">All Designations</option>
                <option value="Software Engineer">Software Engineer</option>
                <option value="Senior Software Engineer">Senior Software Engineer</option>
                <option value="Product Manager">Product Manager</option>
                <option value="HR Manager">HR Manager</option>
                <option value="QA Lead">QA Lead</option>
              </Select>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
            <label className="flex items-center space-x-2 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={batchForm.regenerate}
                onChange={(e) => setBatchForm({ ...batchForm, regenerate: e.target.checked })}
                className="rounded text-indigo-600"
              />
              <span className="font-medium text-slate-700 dark:text-slate-300">
                Regenerate Existing Slips (Recalculate & overwrite existing slips for this month)
              </span>
            </label>
            <p className="text-[10px] text-slate-400 ml-5 mt-0.5">
              By default, batch generation is strictly idempotent and safely skips employees who already have a slip for this month.
            </p>
          </div>

          <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex justify-end space-x-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsAddOpen(false)}
              className="text-xs cursor-pointer"
            >
              Close
            </Button>
            <Button
              type="submit"
              disabled={generating}
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs cursor-pointer"
            >
              {generating ? "Generating..." : "Start Batch Generation"}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
