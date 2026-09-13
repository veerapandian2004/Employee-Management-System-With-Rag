import { useState } from "react";
import { Building2, Plus, Edit, Trash2, Users, DollarSign, Search, UserCheck, ShieldAlert } from "lucide-react";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { Dialog } from "../components/ui/dialog";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/ui/table";

export function DepartmentModule({
  departments = [],
  employees = [],
  userRole = "Administrator",
  onAddDepartment,
  onUpdateDepartment,
  onDeleteDepartment,
}) {
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [editingDept, setEditingDept] = useState(null);
  const [search, setSearch] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const canManage = userRole === "Administrator" || userRole === "HR";

  const initialForm = {
    department_name: "",
    department_head: "",
    parent_department: "",
    cost_center: "",
  };

  const [formData, setFormData] = useState(initialForm);

  const handleOpenAdd = () => {
    setFormData(initialForm);
    setEditingDept(null);
    setErrorMsg("");
    setIsAddOpen(true);
  };

  const handleOpenEdit = (dept) => {
    setEditingDept(dept);
    setFormData({
      department_name: dept.department_name || dept.name || "",
      department_head: dept.department_head || "",
      parent_department: dept.parent_department || "",
      cost_center: dept.cost_center || "",
    });
    setErrorMsg("");
    setIsAddOpen(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!formData.department_name) return;

    const deptName = formData.department_name.trim();
    const payload = {
      ...formData,
      department_name: deptName,
      name: deptName,
      parent_department: formData.parent_department?.trim() || "",
    };

    try {
      if (editingDept) {
        await onUpdateDepartment({
          ...payload,
          original_name: editingDept.name || editingDept.department_name,
        });
      } else {
        await onAddDepartment(payload);
      }
      setIsAddOpen(false);
    } catch (err) {
      setErrorMsg(err.message || "Failed to save department.");
    }
  };

  const filteredDepts = departments.filter(
    (d) =>
      d.department_name?.toLowerCase().includes(search.toLowerCase()) ||
      d.cost_center?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center space-x-2">
            <Building2 className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
            <span>Department Management</span>
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Organize company hierarchy, department heads, and financial cost centers
          </p>
        </div>

        {canManage && (
          <Button onClick={handleOpenAdd} className="bg-indigo-600 hover:bg-indigo-700 font-semibold shadow-md cursor-pointer">
            <Plus className="mr-2 h-4 w-4" /> Add Department
          </Button>
        )}
      </div>

      {/* KPI stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Total Departments</p>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">{departments.length}</h3>
            </div>
            <div className="h-10 w-10 rounded-lg bg-indigo-50 dark:bg-indigo-950/80 text-indigo-600 dark:text-indigo-400 flex items-center justify-center">
              <Building2 className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Cost Centers</p>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">
                {new Set(departments.map((d) => d.cost_center).filter(Boolean)).size}
              </h3>
            </div>
            <div className="h-10 w-10 rounded-lg bg-emerald-50 dark:bg-emerald-950/80 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
              <DollarSign className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Total Staff Assigned</p>
              <h3 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">{employees.length}</h3>
            </div>
            <div className="h-10 w-10 rounded-lg bg-purple-50 dark:bg-purple-950/80 text-purple-600 dark:text-purple-400 flex items-center justify-center">
              <Users className="h-5 w-5" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filter Bar */}
      <Card className="p-4">
        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Search department or cost center..."
            className="pl-9 text-sm"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </Card>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Department Name</TableHead>
              <TableHead>Department Head</TableHead>
              <TableHead>Parent Department</TableHead>
              <TableHead>Cost Center</TableHead>
              <TableHead>Assigned Staff</TableHead>
              {canManage && <TableHead className="text-right">Actions</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredDepts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={canManage ? 6 : 5} className="text-center py-8 text-slate-400 text-sm">
                  No departments found.
                </TableCell>
              </TableRow>
            ) : (
              filteredDepts.map((dept) => {
                const count = employees.filter((e) => e.department === dept.department_name).length;
                return (
                  <TableRow key={dept.name}>
                    <TableCell className="font-bold text-slate-900 dark:text-slate-100 flex items-center space-x-2">
                      <Building2 className="h-4 w-4 text-indigo-500 shrink-0" />
                      <span>{dept.department_name}</span>
                    </TableCell>
                    <TableCell>
                      {(() => {
                        const headId = dept.department_head;
                        if (!headId || headId === "None") {
                          return <span className="text-slate-400 italic text-xs">Not set</span>;
                        }
                        const headEmp = employees.find(
                          (e) =>
                            (e.name && e.name === headId) ||
                            (e.naming_series && e.naming_series === headId) ||
                            e.full_name === headId
                        );
                        const displayName = headEmp
                          ? `${headEmp.full_name} (${headEmp.name || headEmp.naming_series})`
                          : (dept.department_head_name || headId);

                        return (
                          <span className="font-medium text-slate-800 dark:text-slate-200 flex items-center space-x-1.5">
                            <UserCheck className="h-3.5 w-3.5 text-indigo-500 shrink-0" />
                            <span>{displayName}</span>
                          </span>
                        );
                      })()}
                    </TableCell>
                    <TableCell>
                      {dept.parent_department && dept.parent_department.trim() && dept.parent_department !== "None" ? (
                        <Badge variant="outline">{dept.parent_department}</Badge>
                      ) : (
                        <span className="text-slate-400 text-xs">Root Level</span>
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-slate-600 dark:text-slate-400">
                      {dept.cost_center || "N/A"}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="font-semibold">
                        {count} Employee(s)
                      </Badge>
                    </TableCell>
                    {canManage && (
                      <TableCell className="text-right space-x-2">
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 text-xs cursor-pointer"
                          onClick={() => handleOpenEdit(dept)}
                        >
                          <Edit className="mr-1 h-3.5 w-3.5" /> Edit
                        </Button>
                        {userRole === "Administrator" && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-8 text-xs text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 cursor-pointer"
                            onClick={() => onDeleteDepartment(dept.name || dept.department_name)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </TableCell>
                    )}
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      {/* Add / Edit Dialog */}
      {canManage && (
        <Dialog
          isOpen={isAddOpen}
          onClose={() => setIsAddOpen(false)}
          title={editingDept ? "Edit Department" : "Add New Department"}
          description="Configure Department DocType fields"
          maxWidth="max-w-md"
        >
          <form onSubmit={handleSave} className="space-y-4 py-2">
            {errorMsg && (
              <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/50 text-rose-600 dark:text-rose-400 text-xs flex items-center space-x-2">
                <ShieldAlert className="h-4 w-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Department Name *
              </label>
              <Input
                placeholder="e.g. Quality Assurance"
                value={formData.department_name}
                onChange={(e) => setFormData({ ...formData, department_name: e.target.value })}
                required
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Department Head
              </label>
              <Select
                value={formData.department_head}
                onChange={(e) => {
                  const selectedVal = e.target.value;
                  setFormData({
                    ...formData,
                    department_head: selectedVal,
                  });
                }}
              >
                <option value="">-- Select Department Head --</option>
                {employees.map((emp) => {
                  const empId = emp.name || emp.naming_series;
                  return (
                    <option key={empId} value={empId}>
                      {emp.full_name} ({empId})
                    </option>
                  );
                })}
              </Select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                Parent Department
              </label>
              <Select
                value={formData.parent_department}
                onChange={(e) => setFormData({ ...formData, parent_department: e.target.value })}
              >
                <option value="">-- None (Top Level) --</option>
                {departments
                  .filter((d) => (editingDept ? d.department_name !== editingDept.department_name : true))
                  .map((d) => (
                    <option key={d.name} value={d.department_name}>
                      {d.department_name}
                    </option>
                  ))}
              </Select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-1">Cost Center</label>
              <Input
                placeholder="e.g. CC-QA-105"
                value={formData.cost_center}
                onChange={(e) => setFormData({ ...formData, cost_center: e.target.value })}
              />
            </div>

            <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex justify-end space-x-3">
              <Button type="button" variant="outline" onClick={() => setIsAddOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" className="bg-indigo-600 hover:bg-indigo-700 font-semibold cursor-pointer">
                {editingDept ? "Update Department" : "Save Department"}
              </Button>
            </div>
          </form>
        </Dialog>
      )}
    </div>
  );
}
