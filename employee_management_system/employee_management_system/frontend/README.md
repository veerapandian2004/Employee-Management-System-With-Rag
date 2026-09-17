# Frontend - Employee Management System (EMS)

Modern React 19 application built with Vite, Tailwind CSS v4, Lucide React, and shadcn/ui components.

---

## 📁 Project Structure

```
frontend/src/
├── components/
│   ├── layout/
│   │   ├── Header.jsx             # Top bar with title, search, live sync indicator, theme picker & logout
│   │   └── Sidebar.jsx            # Role-filtered collapsible navigation, counts badges & user profile badge
│   ├── GpsClockWidget.jsx         # Secure GPS clock IN/OUT, live stopwatch, shift display & auto clock-out notifications
│   └── ui/
│       ├── utils.js               # Common Tailwind merge utility (cn)
│       ├── badge.jsx              # Status badge primitive (success, warning, destructive, outline)
│       ├── button.jsx             # Button primitive (default, outline, ghost, success, destructive)
│       ├── card.jsx               # Container card primitives
│       ├── dialog.jsx             # Modal dialog container
│       ├── input.jsx              # Styled form input
│       ├── select.jsx             # Styled dropdown selector
│       └── table.jsx              # Responsive data table primitives
├── modules/
│   ├── LoginModule.jsx            # Authentication screen with demo role quick-switchers
│   ├── DashboardModule.jsx        # Dual-mode dashboard (Executive view with today's active & on-leave staff metrics; Employee portal)
│   ├── EmployeeModule.jsx         # Directory view (Admin/HR) and Profile view (Employee)
│   ├── DepartmentModule.jsx       # Department hierarchy & cost center manager
│   ├── LeaveApplicationModule.jsx # Leave application filing & 1-click approval flow
│   ├── LeaveTypeModule.jsx        # Leave policy & rollover management
│   ├── SalarySlipModule.jsx       # Paystub generator with child tables (allowances/deductions) & print view
│   ├── HRDocumentModule.jsx       # Company policy & handbook reader with category filters
│   ├── ChatModule.jsx             # Grounded HR AI Assistant with DB citations & prompt suggestions
│   ├── AttendanceModule.jsx       # Shift attendance tracking with status-aware Clock IN/OUT controls & GPS widget
│   ├── ShiftManagementModule.jsx  # Shift schedule CRUD, weekly offs, and 30-min late entry grace period management
│   └── PayrollModule.jsx          # Payroll batch run component
├── services/
│   ├── apiService.js              # Full backend REST client with session credentials & error handling
│   └── mockData.js                # Fallback schema seed data
├── App.jsx                        # Master root component: session check, role tab gating, API synchronization
├── index.css                      # Tailwind CSS v4 theming variables (Light, Dark Slate, Ocean Blue)
└── main.jsx                       # React DOM entrypoint
```

---

## 🛠️ Available Scripts

- `npm run dev`: Launches local Vite development server with proxy to Frappe port 8001.
- `npm run build`: Bundles the application for production into `dist/`.
- `npm run lint`: Runs ESLint across all codebase files (`0 errors, 0 warnings`).
- `npm run preview`: Locally previews the production build.
