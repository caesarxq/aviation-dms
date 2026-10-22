import { Outlet, NavLink } from "react-router-dom";
import { LayoutDashboard, FileText, AlertTriangle, Plane, ClipboardList, ClipboardCheck, Wrench, AlertOctagon, ShieldAlert, Users, BarChart3, Calendar, Share2, Edit2, Monitor, Bell } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { safetyApi } from "../../api/safety";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/documents", icon: FileText, label: "Documents" },
  { to: "/occurrences", icon: AlertTriangle, label: "Safety Occurrences" },
  { to: "/roc", icon: Plane, label: "ROC & Fleet" },
  { to: "/missions", icon: ClipboardList, label: "Missions" },
  { to: "/quality-audits", icon: ClipboardCheck, label: "Quality Audits" },
  { to: "/corrective-actions", icon: Wrench, label: "CARs" },
  { to: "/dangerous-goods", icon: AlertOctagon, label: "Dangerous Goods" },
  { to: "/security", icon: ShieldAlert, label: "Security" },
  { to: "/outsourced-functions", icon: Users, label: "Outsourced Functions" },
  { to: "/safety-kpis", icon: BarChart3, label: "Safety KPIs" },
  { to: "/security-reviews", icon: Calendar, label: "Security Reviews" },
  { to: "/dg-responsibility-matrix", icon: Share2, label: "DG Responsibility" },
  { to: "/documents/DOC-001/edit", icon: Edit2, label: "Document Editor" },
  { to: "/documents/DOC-001/view", icon: Monitor, label: "Document Viewer" },
];

export function AppShell() {
  const { data: unread } = useQuery({
    queryKey: ["unread-notifications"],
    queryFn: () => safetyApi.getUnreadCount(),
    refetchInterval: 60000,
  });

  const unreadCount = unread?.unread_count ?? 0;

  return (
    <div className="flex h-screen">
      <aside className="w-64 bg-kfl-dark text-white p-4">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-bold">KFL Aviation DMS</h1>
          <div className="relative">
            <Bell size={20} className="text-white" />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center">
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            )}
          </div>
        </div>
        <nav className="space-y-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2 rounded ${isActive ? "bg-kfl-teal" : "hover:bg-gray-700"}`
              }
            >
              <item.icon size={18} />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-auto bg-gray-50">
        <Outlet />
      </main>
    </div>
  );
}