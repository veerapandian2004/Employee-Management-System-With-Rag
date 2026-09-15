import { useState } from "react";
import {
  Receipt,
  Plus,
  Search,
  Printer,
  Edit,
  Trash2,
  DollarSign,
  PlusCircle,
  MinusCircle,
  Eye,
  CheckCircle2,
  Download,
  Mail,
  Send,
  RefreshCw,
} from "lucide-react";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { Dialog } from "../components/ui/dialog";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/ui/table";
import {
  apiDownloadSalarySlipPdf,
  apiSendSalarySlipEmail,
  apiSendBatchSalarySlipEmails,
  apiCalculateLop,
} from "../services/apiService";

export function SalarySlipModule({
  salarySlips = [],
  employees = [],
  onAddSalarySlip,
  onUpdateSalarySlip,
  onDeleteSalarySlip,
  userRole = "Administrator",
  onRefreshData,
}) {
  const isEmployee = userRole === "Employee";
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [editingSlip, setEditingSlip] = useState(null);
  const [viewingSlip, setViewingSlip] = useState(null);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [search, setSearch] = useState("");
  const [downloadingSlip, setDownloadingSlip] = useState(null);
  const [emailingSlip, setEmailingSlip] = useState(null);
  const [batchEmailing, setBatchEmailing] = useState(false);

  const initialForm = {
    employee: employees[0]?.name || employees[0]?.naming_series || "",
    employee_name: employees[0]?.full_name || "",
    salary_month: "September 2026",
    basic_pay: employees[0] ? Math.round(Number(employees[0].basic_salary || 90000) / 12) : 7500,
    hra: employees[0] ? Math.round(Number(employees[0].basic_salary || 90000) / 30) : 3000,
    allowances: [{ allowance_name: "Special Allowance", amount: 500 }],
    deductions: [{ deduction_name: "Provident Fund", amount: 900 }],
    gross_pay: 11000,
    leave_deduction: 0,
    net_pay: 10100,
    select: "Draft",
  };

  const [formData, setFormData] = useState(initialForm);

  const calculateTotals = (data) => {
    const basic = Number(data.basic_pay || 0);
    const hra = Number(data.hra || 0);
    const sumAllowances = (data.allowances || []).reduce(
      (sum, item) => sum + (Number(item.amount) || 0),
      0
    );
    const safeBasic = isNaN(basic) ? 0 : basic;
    const safeHra = isNaN(hra) ? 0 : hra;
    const gross = safeBasic + safeHra + sumAllowances;

    const sumDeductions = (data.deductions || []).reduce(
      (sum, item) => sum + (Number(item.amount) || 0),
      0
    );
    const leaveDed = Number(data.leave_deduction || 0);
    const safeLeaveDed = isNaN(leaveDed) ? 0 : leaveDed;
    const net = gross - sumDeductions - safeLeaveDed;

    return { gross, net: net > 0 ? net : 0 };
  };

  const handleFormChange = (updated) => {
    const { gross, net } = calculateTotals(updated);
    setFormData({
      ...updated,
      gross_pay: gross,
      net_pay: net,
    });
  };

  const handleOpenAdd = () => {
    const defaultEmp = employees[0];
    const bPay = defaultEmp ? Math.round(Number(defaultEmp.basic_salary || 90000) / 12) : 7500;
    const hPay = Math.round(bPay * 0.4);

    const data = {
      ...initialForm,
      employee: defaultEmp ? defaultEmp.name || defaultEmp.naming_series : "",
      employee_name: defaultEmp ? defaultEmp.full_name : "",
      basic_pay: bPay,
      hra: hPay,
    };
    const { gross, net } = calculateTotals(data);
    setFormData({ ...data, gross_pay: gross, net_pay: net });
    setEditingSlip(null);
    setIsAddOpen(true);
  };

  const handleOpenEdit = (slip) => {
    setEditingSlip(slip);
    setFormData({
      ...slip,
      allowances: slip.allowances ? [...slip.allowances] : [],
      deductions: slip.deductions ? [...slip.deductions] : [],
    });
    setIsAddOpen(true);
  };

  const handleAddAllowanceRow = () => {
    const updated = {
      ...formData,
      allowances: [...(formData.allowances || []), { allowance_name: "", amount: 0 }],
    };
    handleFormChange(updated);
  };

  const handleRemoveAllowanceRow = (idx) => {
    const updated = {
      ...formData,
      allowances: formData.allowances.filter((_, i) => i !== idx),
    };
    handleFormChange(updated);
  };

  const handleAddDeductionRow = () => {
    const updated = {
      ...formData,
      deductions: [...(formData.deductions || []), { deduction_name: "", amount: 0 }],
    };
    handleFormChange(updated);
  };

  const handleRemoveDeductionRow = (idx) => {
    const updated = {
      ...formData,
      deductions: formData.deductions.filter((_, i) => i !== idx),
    };
    handleFormChange(updated);
  };

  const handleSave = (e) => {
    e.preventDefault();
    if (!formData.employee) return;

    if (editingSlip) {
      if (onUpdateSalarySlip) {
        onUpdateSalarySlip(formData);
      }
    } else {
      if (onAddSalarySlip) {
        onAddSalarySlip(formData);
      }
    }
    setIsAddOpen(false);
  };

  const handleDownloadPdf = async (name) => {
    try {
      setDownloadingSlip(name);
      await apiDownloadSalarySlipPdf(name);
    } catch (err) {
      alert(err.message || "Failed to download salary slip PDF");
    } finally {
      setDownloadingSlip(null);
    }
  };

  const handleSendEmail = async (name) => {
    try {
      setEmailingSlip(name);
      const res = await apiSendSalarySlipEmail(name);
      alert(res.message || "Salary slip emailed successfully!");
      if (onRefreshData) onRefreshData();
    } catch (err) {
      alert(err.message || "Failed to email salary slip");
    } finally {
      setEmailingSlip(null);
    }
  };

  const handleBatchEmail = async () => {
    if (!confirm("Email salary slips to all active employees for this period?")) return;
    try {
      setBatchEmailing(true);
      const res = await apiSendBatchSalarySlipEmails();
      alert(res.message || "Batch email dispatch completed!");
      if (onRefreshData) onRefreshData();
    } catch (err) {
      alert(err.message || "Batch email dispatch failed");
    } finally {
      setBatchEmailing(false);
    }
  };

  const filteredSlips = salarySlips.filter((s) => {
    const matchesSearch =
      (s.employee_name && s.employee_name.toLowerCase().includes(search.toLowerCase())) ||
      (s.employee && s.employee.toLowerCase().includes(search.toLowerCase())) ||
      (s.salary_month && s.salary_month.toLowerCase().includes(search.toLowerCase()));
    const matchesStatus = statusFilter === "ALL" || s.select === statusFilter;

    return matchesSearch && matchesStatus;
  });

  const totalGross = salarySlips.reduce((acc, curr) => acc + Number(curr.gross_pay || 0), 0);
  const totalNet = salarySlips.reduce((acc, curr) => acc + Number(curr.net_pay || 0), 0);

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className={`space-y-6 ${viewingSlip ? "print:hidden" : ""}`}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center space-x-2">
            <Receipt className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
            <span>{isEmployee ? "My Salary Slips" : "Salary Slips"}</span>
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            {isEmployee
              ? "View and download your monthly salary paystubs and earnings breakdown"
              : "Generate employee paystubs with allowance breakdown, deductions, and net pay"}
          </p>
        </div>
        {!isEmployee && (
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              onClick={handleBatchEmail}
              disabled={batchEmailing}
              className="text-xs h-9 cursor-pointer"
              title="Email all slips to employees"
            >
              <Mail className="mr-1.5 h-3.5 w-3.5 text-indigo-600" />
              {batchEmailing ? "Sending..." : "Email All Slips"}
            </Button>
            <Button onClick={handleOpenAdd} className="bg-indigo-600 hover:bg-indigo-700 font-semibold shadow-md text-xs h-9 cursor-pointer">
              <Plus className="mr-1.5 h-4 w-4" /> Create Salary Slip
            </Button>
          </div>
        )}
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">
                {isEmployee ? "My Gross Earnings" : "Total Gross Earnings"}
              </p>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">${totalGross.toLocaleString()}</h3>
            </div>
            <DollarSign className="h-8 w-8 text-emerald-500" />
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">
                {isEmployee ? "My Net Pay Received" : "Total Net Disbursement"}
              </p>
              <h3 className="text-2xl font-bold text-indigo-600 dark:text-indigo-400 mt-1">${totalNet.toLocaleString()}</h3>
            </div>
            <Receipt className="h-8 w-8 text-indigo-500" />
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase">
                {isEmployee ? "Paystubs Available" : "Total Slips Generated"}
              </p>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">{salarySlips.length} Slips</h3>
            </div>
            <CheckCircle2 className="h-8 w-8 text-purple-500" />
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <Input
              placeholder={isEmployee ? "Search by month..." : "Search by employee or month..."}
              className="pl-9 text-sm"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <div className="flex items-center space-x-1 border border-slate-200 dark:border-slate-800 rounded-lg p-1 bg-slate-50 dark:bg-slate-900">
            {["ALL", "Draft", "Submitted", "Paid"].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors ${
                  statusFilter === st
                    ? "bg-white dark:bg-slate-800 text-indigo-700 dark:text-indigo-400 shadow-xs"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100"
                }`}
              >
                {st}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {/* Salary Slips Table */}
      <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Slip ID</TableHead>
              {!isEmployee && <TableHead>Employee</TableHead>}
              <TableHead>Salary Month</TableHead>
              <TableHead>Basic + HRA</TableHead>
              <TableHead>LOP (Days/Ded)</TableHead>
              <TableHead>Gross Pay</TableHead>
              <TableHead>Net Pay</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Email</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredSlips.length === 0 ? (
              <TableRow>
                <TableCell colSpan={isEmployee ? 9 : 10} className="text-center py-8 text-slate-500 dark:text-slate-400">
                  No salary slips found matching current criteria.
                </TableCell>
              </TableRow>
            ) : (
              filteredSlips.map((slip) => (
                <TableRow key={slip.name}>
                  <TableCell className="font-mono text-xs font-semibold text-slate-700 dark:text-slate-300">{slip.name}</TableCell>
                  {!isEmployee && (
                    <TableCell>
                      <div className="font-semibold text-slate-900 dark:text-slate-100">{slip.employee_name}</div>
                      <div className="text-xs text-slate-400 dark:text-slate-500 font-mono">{slip.employee}</div>
                    </TableCell>
                  )}
                  <TableCell className="font-medium text-slate-700 dark:text-slate-300">{slip.salary_month}</TableCell>
                  <TableCell className="text-xs text-slate-600 dark:text-slate-400">
                    ${Number(slip.basic_pay || 0).toLocaleString()} + ${Number(slip.hra || 0).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-xs font-mono">
                    {Number(slip.lop_days || 0) > 0 ? (
                      <span className="text-rose-600 dark:text-rose-400 font-semibold" title={`Absent: ${slip.absent_days || 0}, Unpaid: ${slip.unpaid_leave_days || 0}`}>
                        {Number(slip.lop_days)}d (-${Number(slip.lop_deduction || slip.leave_deduction || 0).toLocaleString()})
                      </span>
                    ) : (
                      <span className="text-slate-400">0d</span>
                    )}
                  </TableCell>
                  <TableCell className="font-semibold text-slate-800 dark:text-slate-200">
                    ${Number(slip.gross_pay || 0).toLocaleString()}
                  </TableCell>
                  <TableCell className="font-extrabold text-emerald-600 dark:text-emerald-400 text-sm">
                    ${Number(slip.net_pay || 0).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        slip.select === "Paid"
                          ? "success"
                          : slip.select === "Submitted"
                          ? "default"
                          : "secondary"
                      }
                    >
                      {slip.select || "Draft"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      className={
                        slip.email_status === "Sent"
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 text-[10px]"
                          : slip.email_status === "Failed"
                          ? "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 text-[10px]"
                          : "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 text-[10px]"
                      }
                      title={slip.email_sent_at ? `Sent on: ${slip.email_sent_at}` : "Not sent yet"}
                    >
                      {slip.email_status || "Pending"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right space-x-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-8 text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 hover:bg-indigo-50 dark:hover:bg-indigo-950/50 cursor-pointer"
                      onClick={() => setViewingSlip(slip)}
                      title="View Paystub"
                    >
                      <Eye className="h-3.5 w-3.5 mr-1" />
                      View
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-8 text-xs text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer"
                      onClick={() => handleDownloadPdf(slip.name)}
                      disabled={downloadingSlip === slip.name}
                      title="Download PDF"
                    >
                      <Download className={`h-3.5 w-3.5 mr-1 ${downloadingSlip === slip.name ? "animate-bounce" : ""}`} />
                      PDF
                    </Button>
                    {!isEmployee && (
                      <>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-8 text-xs text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-950/50 cursor-pointer"
                          onClick={() => handleSendEmail(slip.name)}
                          disabled={emailingSlip === slip.name}
                          title="Send Email to Employee"
                        >
                          <Mail className={`h-3.5 w-3.5 ${emailingSlip === slip.name ? "animate-spin" : ""}`} />
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 text-xs cursor-pointer"
                          onClick={() => handleOpenEdit(slip)}
                          title="Edit"
                        >
                          <Edit className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-8 text-xs text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/50 cursor-pointer"
                          onClick={() => onDeleteSalarySlip && onDeleteSalarySlip(slip.name)}
                          title="Delete"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
      </div>

      {/* Add / Edit Dialog Form */}
      {!isEmployee && (
        <Dialog
          isOpen={isAddOpen}
          onClose={() => setIsAddOpen(false)}
          title={editingSlip ? "Edit Salary Slip" : "Generate Salary Slip"}
          description="Form based on Salary Slip, Salary Slip Allowance & Deduction DocTypes."
          maxWidth="max-w-2xl"
        >
          <form onSubmit={handleSave} className="space-y-4 py-2">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">Employee *</label>
                <Select
                  value={formData.employee}
                  onChange={(e) => {
                    const emp = employees.find((x) => x.naming_series === e.target.value || x.name === e.target.value);
                    const bPay = emp ? Math.round(Number(emp.basic_salary || 90000) / 12) : 7500;
                    const hPay = Math.round(bPay * 0.4);
                    const updated = {
                      ...formData,
                      employee: e.target.value,
                      employee_name: emp ? emp.full_name : "",
                      basic_pay: bPay,
                      hra: hPay,
                    };
                    handleFormChange(updated);
                  }}
                  required
                >
                  {employees.map((emp) => (
                    <option key={emp.name || emp.naming_series} value={emp.name || emp.naming_series}>
                      {emp.full_name} ({emp.naming_series || emp.name})
                    </option>
                  ))}
                </Select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                  Salary Month *
                </label>
                <Input
                  placeholder="e.g. September 2026"
                  value={formData.salary_month}
                  onChange={(e) => handleFormChange({ ...formData, salary_month: e.target.value })}
                  required
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">Basic Pay ($)</label>
                <Input
                  type="number"
                  value={formData.basic_pay}
                  onChange={(e) => handleFormChange({ ...formData, basic_pay: Number(e.target.value) })}
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">HRA ($)</label>
                <Input
                  type="number"
                  value={formData.hra}
                  onChange={(e) => handleFormChange({ ...formData, hra: Number(e.target.value) })}
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                  Leave Deduction ($)
                </label>
                <Input
                  type="number"
                  value={formData.leave_deduction}
                  onChange={(e) => handleFormChange({ ...formData, leave_deduction: Number(e.target.value) })}
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">Status</label>
                <Select
                  value={formData.select}
                  onChange={(e) => setFormData({ ...formData, select: e.target.value })}
                >
                  <option value="Draft">Draft</option>
                  <option value="Submitted">Submitted</option>
                  <option value="Paid">Paid</option>
                </Select>
              </div>
            </div>

            {/* Child Table: Allowances */}
            <div className="pt-2">
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider">
                  Allowances (Child Table)
                </label>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs text-indigo-600 dark:text-indigo-400"
                  onClick={handleAddAllowanceRow}
                >
                  <PlusCircle className="mr-1 h-3.5 w-3.5" /> Add Allowance
                </Button>
              </div>

              <div className="space-y-2">
                {(formData.allowances || []).map((allow, idx) => (
                  <div key={idx} className="flex items-center space-x-2">
                    <Input
                      placeholder="Allowance Name (e.g. Medical)"
                      className="flex-1 text-xs"
                      value={allow.allowance_name || ""}
                      onChange={(e) => {
                        const val = e.target.value;
                        const newArr = (formData.allowances || []).map((a, i) =>
                          i === idx ? { ...a, allowance_name: val } : a
                        );
                        handleFormChange({ ...formData, allowances: newArr });
                      }}
                    />
                    <Input
                      type="number"
                      placeholder="Amount"
                      className="w-32 text-xs"
                      value={allow.amount || 0}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value) || 0;
                        const newArr = (formData.allowances || []).map((a, i) =>
                          i === idx ? { ...a, amount: val } : a
                        );
                        handleFormChange({ ...formData, allowances: newArr });
                      }}
                    />
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-8 text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/50 px-2"
                      onClick={() => handleRemoveAllowanceRow(idx)}
                    >
                      <MinusCircle className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>

            {/* Child Table: Deductions */}
            <div className="pt-2">
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider">
                  Deductions (Child Table)
                </label>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs text-rose-600 dark:text-rose-400"
                  onClick={handleAddDeductionRow}
                >
                  <PlusCircle className="mr-1 h-3.5 w-3.5" /> Add Deduction
                </Button>
              </div>

              <div className="space-y-2">
                {(formData.deductions || []).map((ded, idx) => (
                  <div key={idx} className="flex items-center space-x-2">
                    <Input
                      placeholder="Deduction Name (e.g. Tax / PF)"
                      className="flex-1 text-xs"
                      value={ded.deduction_name || ""}
                      onChange={(e) => {
                        const val = e.target.value;
                        const newArr = (formData.deductions || []).map((d, i) =>
                          i === idx ? { ...d, deduction_name: val } : d
                        );
                        handleFormChange({ ...formData, deductions: newArr });
                      }}
                    />
                    <Input
                      type="number"
                      placeholder="Amount"
                      className="w-32 text-xs"
                      value={ded.amount || 0}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value) || 0;
                        const newArr = (formData.deductions || []).map((d, i) =>
                          i === idx ? { ...d, amount: val } : d
                        );
                        handleFormChange({ ...formData, deductions: newArr });
                      }}
                    />
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-8 text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/50 px-2"
                      onClick={() => handleRemoveDeductionRow(idx)}
                    >
                      <MinusCircle className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>

            {/* Calculation Breakdown Preview */}
            <div className="bg-indigo-50/70 dark:bg-indigo-950/40 p-4 rounded-xl border border-indigo-100 dark:border-indigo-900/50 flex items-center justify-between text-sm">
              <div>
                <span className="text-slate-600 dark:text-slate-400 block text-xs">Gross Pay:</span>
                <span className="font-bold text-slate-900 dark:text-slate-100">
                  ${Number(formData.gross_pay || 0).toLocaleString()}
                </span>
              </div>
              <div>
                <span className="text-slate-600 dark:text-slate-400 block text-xs">Net Calculated Pay:</span>
                <span className="font-extrabold text-indigo-700 dark:text-indigo-400 text-lg">
                  ${Number(formData.net_pay || 0).toLocaleString()}
                </span>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex justify-end space-x-3">
              <Button type="button" variant="outline" onClick={() => setIsAddOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" className="bg-indigo-600 hover:bg-indigo-700 font-semibold">
                Save Salary Slip
              </Button>
            </div>
          </form>
        </Dialog>
      )}

      {/* Printable Paystub View Dialog */}
      {viewingSlip && (() => {
        const currentEmp = employees.find(
          (e) => e.name === viewingSlip.employee || e.naming_series === viewingSlip.employee
        );
        const totalEarnings =
          Number(viewingSlip.gross_pay) ||
          Number(viewingSlip.basic_pay || 0) +
            Number(viewingSlip.hra || 0) +
            (viewingSlip.allowances || []).reduce((acc, a) => acc + Number(a.amount || 0), 0);
        const totalDeductions =
          (viewingSlip.total_deduction !== undefined && viewingSlip.total_deduction !== null && Number(viewingSlip.total_deduction) > 0)
            ? Number(viewingSlip.total_deduction)
            : Number(viewingSlip.leave_deduction || viewingSlip.lop_deduction || 0) +
              (viewingSlip.deductions || []).reduce((acc, d) => acc + Number(d.amount || 0), 0);

        return (
          <Dialog
            isOpen={Boolean(viewingSlip)}
            onClose={() => setViewingSlip(null)}
            maxWidth="max-w-2xl"
          >
            <div className="space-y-5 py-1 text-slate-900 dark:text-slate-100">
              {/* Corporate Paystub Header */}
              <div className="border-b-2 border-slate-800 dark:border-slate-600 pb-4">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-xl font-black tracking-tight uppercase text-slate-900 dark:text-white">
                      EMP MANAGEMENT CORP
                    </h2>
                    <p className="text-xs font-bold uppercase tracking-wider text-indigo-700 dark:text-indigo-400 mt-0.5">
                      Official Employee Salary Paystub
                    </p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                      Confidential Earnings & Deductions Statement
                    </p>
                  </div>
                  <div className="text-right">
                    <Badge
                      variant={viewingSlip.select === "Paid" ? "success" : "default"}
                      className="text-xs font-bold px-3 py-0.5"
                    >
                      {viewingSlip.select || "Draft"}
                    </Badge>
                    <p className="text-xs font-mono font-semibold text-slate-700 dark:text-slate-300 mt-1.5">
                      Ref: {viewingSlip.name}
                    </p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400">
                      Period: <span className="font-semibold text-slate-800 dark:text-slate-200">{viewingSlip.salary_month}</span>
                    </p>
                  </div>
                </div>
              </div>

              {/* Employee Information Card */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-50 dark:bg-slate-800/60 p-3.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs">
                <div>
                  <span className="text-slate-500 dark:text-slate-400 block text-[11px] uppercase tracking-wider">Employee Name</span>
                  <span className="font-bold text-slate-900 dark:text-slate-100 text-sm">
                    {viewingSlip.employee_name || currentEmp?.full_name || "—"}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 dark:text-slate-400 block text-[11px] uppercase tracking-wider">Employee ID</span>
                  <span className="font-mono font-bold text-slate-900 dark:text-slate-100">
                    {viewingSlip.employee}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 dark:text-slate-400 block text-[11px] uppercase tracking-wider">Department</span>
                  <span className="font-medium text-slate-800 dark:text-slate-200">
                    {currentEmp?.department || "Operations"}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 dark:text-slate-400 block text-[11px] uppercase tracking-wider">Loss of Pay (LOP)</span>
                  <span className="font-medium text-slate-800 dark:text-slate-200">
                    {Number(viewingSlip.lop_days || 0) > 0
                      ? `${viewingSlip.lop_days} Day(s) Unpaid`
                      : "0 Days (Nil)"}
                  </span>
                </div>
              </div>

              {/* Earnings & Deductions Tables */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                {/* Earnings Column */}
                <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden bg-white dark:bg-slate-900">
                  <div className="bg-emerald-50 dark:bg-emerald-950/50 px-3.5 py-2 border-b border-slate-200 dark:border-slate-700">
                    <h4 className="font-bold text-emerald-800 dark:text-emerald-300 uppercase tracking-wider text-[11px]">
                      Earnings Breakdown
                    </h4>
                  </div>
                  <div className="p-3.5 space-y-2">
                    <div className="flex justify-between py-0.5">
                      <span className="text-slate-600 dark:text-slate-400">Basic Salary</span>
                      <span className="font-semibold text-slate-900 dark:text-slate-100 font-mono">
                        ${Number(viewingSlip.basic_pay || 0).toLocaleString()}
                      </span>
                    </div>
                    <div className="flex justify-between py-0.5">
                      <span className="text-slate-600 dark:text-slate-400">House Rent Allowance (HRA)</span>
                      <span className="font-semibold text-slate-900 dark:text-slate-100 font-mono">
                        ${Number(viewingSlip.hra || 0).toLocaleString()}
                      </span>
                    </div>
                    {(viewingSlip.allowances || []).map((a, i) => (
                      <div key={i} className="flex justify-between py-0.5">
                        <span className="text-slate-600 dark:text-slate-400">{a.allowance_name}</span>
                        <span className="font-semibold text-slate-900 dark:text-slate-100 font-mono">
                          ${Number(a.amount || 0).toLocaleString()}
                        </span>
                      </div>
                    ))}
                    <div className="pt-2.5 mt-2 border-t border-slate-200 dark:border-slate-700 flex justify-between font-bold text-slate-900 dark:text-slate-100">
                      <span>Total Gross Earnings</span>
                      <span className="text-emerald-700 dark:text-emerald-400 font-mono">
                        ${totalEarnings.toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Deductions Column */}
                <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden bg-white dark:bg-slate-900">
                  <div className="bg-rose-50 dark:bg-rose-950/50 px-3.5 py-2 border-b border-slate-200 dark:border-slate-700">
                    <h4 className="font-bold text-rose-800 dark:text-rose-300 uppercase tracking-wider text-[11px]">
                      Deductions Breakdown
                    </h4>
                  </div>
                  <div className="p-3.5 space-y-2">
                    {Number(viewingSlip.leave_deduction || viewingSlip.lop_deduction) > 0 ? (
                      <div className="flex justify-between py-0.5 text-rose-700 dark:text-rose-400">
                        <span>Leave / LOP Deduction</span>
                        <span className="font-semibold font-mono">
                          -${Number(viewingSlip.leave_deduction || viewingSlip.lop_deduction).toLocaleString()}
                        </span>
                      </div>
                    ) : (
                      <div className="flex justify-between py-0.5 text-slate-500 dark:text-slate-400">
                        <span>Leave / LOP Deduction</span>
                        <span className="font-semibold font-mono">$0</span>
                      </div>
                    )}
                    {(viewingSlip.deductions || []).map((d, i) => (
                      <div key={i} className="flex justify-between py-0.5">
                        <span className="text-slate-600 dark:text-slate-400">{d.deduction_name}</span>
                        <span className="font-semibold text-slate-900 dark:text-slate-100 font-mono">
                          -${Number(d.amount || 0).toLocaleString()}
                        </span>
                      </div>
                    ))}
                    <div className="pt-2.5 mt-2 border-t border-slate-200 dark:border-slate-700 flex justify-between font-bold text-slate-900 dark:text-slate-100">
                      <span>Total Deductions</span>
                      <span className="text-rose-700 dark:text-rose-400 font-mono">
                        ${totalDeductions.toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Net Pay Box */}
              <div className="bg-emerald-50 dark:bg-emerald-950/40 border-2 border-emerald-500/50 p-4 rounded-xl flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 block">
                    TOTAL NET DISBURSEMENT
                  </span>
                  <span className="text-[11px] text-slate-500 dark:text-slate-400">
                    Gross Earnings (${totalEarnings.toLocaleString()}) − Deductions (${totalDeductions.toLocaleString()})
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-2xl sm:text-3xl font-black text-emerald-700 dark:text-emerald-400 font-mono tracking-tight">
                    ${Number(viewingSlip.net_pay || 0).toLocaleString()}
                  </span>
                </div>
              </div>

              {/* Signatures & Verification (Printed on Paper / PDF) */}
              <div className="pt-6 border-t border-slate-200 dark:border-slate-700 grid grid-cols-2 gap-8 text-xs">
                <div>
                  <div className="h-10 border-b border-dashed border-slate-300 dark:border-slate-600 flex items-end pb-1 text-[11px] text-slate-400">
                    Employee Signature
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1">Received & Acknowledged</p>
                </div>
                <div>
                  <div className="h-10 border-b border-dashed border-slate-300 dark:border-slate-600 flex items-end justify-end pb-1 text-[11px] text-slate-600 dark:text-slate-300 font-semibold">
                    EMP Management Corp HR
                  </div>
                  <p className="text-[11px] text-slate-500 text-right mt-1">Authorized Signatory</p>
                </div>
              </div>

              <p className="text-[10px] text-center text-slate-400 dark:text-slate-500 pt-1">
                This is an official computer-generated salary paystub issued by EMP Management Corp. Questions? Contact hr@ems.com.
              </p>

              {/* Action Buttons (Hidden from Print) */}
              <div className="pt-3 flex justify-end space-x-3 print:hidden border-t border-slate-100 dark:border-slate-800">
                <Button
                  variant="outline"
                  onClick={() => window.print()}
                  className="print:hidden font-semibold cursor-pointer"
                >
                  <Printer className="mr-2 h-4 w-4" /> Print Paystub
                </Button>
                <Button
                  variant="default"
                  onClick={() => setViewingSlip(null)}
                  className="print:hidden cursor-pointer"
                >
                  Close
                </Button>
              </div>
            </div>
          </Dialog>
        );
      })()}
    </div>
  );
}
