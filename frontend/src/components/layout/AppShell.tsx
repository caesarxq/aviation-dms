import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { LayoutDashboard, FileText, AlertTriangle, Plane, ClipboardList, ClipboardCheck, Wrench, AlertOctagon, ShieldAlert, Users, BarChart3, Calendar, Share2, Edit2, Monitor, Bell } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { safetyApi } from "../../api/safety";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/notifications", icon: Bell, label: "Notifications" },
  { to: "/documents", icon: FileText, label: "Documents" },
  { to: "/occurrences", icon: AlertTriangle, label: "Safety Occurrences" },
  { to: "/roc", icon: Plane, label: "ROC & Fleet" },
  { to: "/missions", icon: ClipboardList, label: "Missions" },
  { to: "/quality-audits", icon: ClipboardCheck, label: "Quality Audits" },
  { to: "/corrective-actions", icon: Wrench, label: "Corrective Actions" },
  { to: "/dangerous-goods", icon: AlertOctagon, label: "Dangerous Goods" },
  { to: "/security", icon: ShieldAlert, label: "Security" },
  { to: "/outsourced-functions", icon: Users, label: "Outsourced Functions" },
  { to: "/safety-kpis", icon: BarChart3, label: "Safety KPIs" },
  { to: "/security-reviews", icon: Calendar, label: "Security Reviews" },
  { to: "/dg-responsibility-matrix", icon: Share2, label: "DG Responsibility" },
];

const utilityItems = [
  { to: "/documents/DOC-001/edit", icon: Edit2, label: "Document Editor" },
  { to: "/documents/DOC-001/view", icon: Monitor, label: "Document Viewer" },
];

export function AppShell() {
  const navigate = useNavigate();
  const { data: unread } = useQuery({
    queryKey: ["unread-notifications"],
    queryFn: () => safetyApi.getUnreadCount(),
    refetchInterval: 60000,
  });

  const unreadCount = unread?.unread_count ?? 0;

  return (
    <div className="flex min-h-screen bg-kfl-canvas">
      <aside className="app-sidebar sticky top-0 flex h-screen w-[264px] shrink-0 flex-col bg-kfl-dark px-4 py-5 text-white shadow-xl">
        <div className="mb-7 flex items-center justify-between gap-3 px-2">
          <button onClick={() => navigate("/")} className="rounded-md p-1 text-left focus-visible:ring-2 focus-visible:ring-sky-300" aria-label="Go to dashboard">
            <img src="/brand/kfl-logo.png" alt="Kenya Flying Labs" className="h-12 w-auto object-contain object-left" />
          </button>
          <button
            onClick={() => navigate("/notifications")}
            className="relative rounded-md p-2 text-slate-200 transition hover:bg-white/10 hover:text-white"
            aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ""}`}
          >
            <Bell size={18} />
            {unreadCount > 0 && (
              <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            )}
          </button>
        </div>

        <div className="sidebar-section-label mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.14em] text-sky-200/70">Operations</div>
        <nav className="space-y-1" aria-label="Primary navigation">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `group flex min-h-10 items-center gap-3 rounded-md border-l-[3px] px-3 text-[13px] font-medium transition ${
                  isActive
                    ? "border-kfl-blue bg-kfl-blue/20 text-white shadow-sm"
                    : "border-transparent text-slate-300 hover:bg-white/[0.07] hover:text-white"
                }`
              }
            >
              <item.icon size={17} strokeWidth={1.8} className="shrink-0" />
              <span className="nav-label truncate">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-section-label mb-3 mt-7 px-3 text-[10px] font-bold uppercase tracking-[0.14em] text-sky-200/70">Tools</div>
        <nav className="space-y-1" aria-label="Tools navigation">
          {utilityItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `group flex min-h-10 items-center gap-3 rounded-md border-l-[3px] px-3 text-[13px] font-medium transition ${
                  isActive
                    ? "border-kfl-blue bg-kfl-blue/20 text-white"
                    : "border-transparent text-slate-300 hover:bg-white/[0.07] hover:text-white"
                }`
              }
            >
              <item.icon size={17} strokeWidth={1.8} className="shrink-0" />
              <span className="nav-label truncate">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto border-t border-white/10 px-3 pt-4 text-[11px] text-slate-400">
          <div className="flex items-center gap-2 text-emerald-300">
            <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_0_3px_rgba(52,211,153,0.15)]" />
            <span>Operational control active</span>
          </div>
          <div className="mt-2 text-slate-500">KFL Aviation DMS · v1.0</div>
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-auto bg-kfl-canvas">
        <Outlet />
      </main>
    </div>
  );
}