import { Outlet, NavLink, useNavigate } from "react-router-dom";
import {
  Activity,
  BarChart3,
  LayoutDashboard,
  FileText,
  AlertTriangle,
  ClipboardList,
  ClipboardCheck,
  AlertOctagon,
  ShieldAlert,
  ShieldCheck,
  Users,
  Bell,
  Shield,
  KeyRound,
  Upload,
  ChevronDown,
  Search,
  CheckCircle,
  ScrollText,
  MailOpen,
  GraduationCap,
  Wrench,
  Clock,
  Award,
  LogOut,
} from "lucide-react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { safetyApi } from "../../api/safety";
import { useAuth } from "../../auth/AuthContext";
import { getPostLoginPath } from "../../auth/permissions";

interface NavItem {
  to: string;
  icon: any;
  label: string;
  permission?: string;
  role?: string;
}

interface SectionProps {
  label: string;
  icon: any;
  items: NavItem[];
  initiallyOpen?: boolean;
}

function CollapsibleSection({ label, icon: Icon, items, initiallyOpen = false }: SectionProps) {
  const [open, setOpen] = useState(initiallyOpen);

  const isActive = items.some((i) => {
    try {
      return window.location.pathname === i.to || window.location.pathname.startsWith(i.to + "/");
    } catch {
      return false;
    }
  });

  const effectiveOpen = open || isActive;

  return (
    <div className="mb-3">
      <button
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-sky-200/70 hover:bg-white/10 transition"
        aria-expanded={effectiveOpen}
        aria-label={label}
      >
        <Icon size={16} className="shrink-0" />
        <span className="flex-1">{label}</span>
        <ChevronDown size={14} className={`shrink-0 transition-transform duration-200 ${effectiveOpen ? "" : "-rotate-90"}`} />
      </button>
      {effectiveOpen && (
        <nav className="space-y-0.5 mt-1 ml-2 pl-3 border-l-2 border-white/5">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-md px-3 py-1.5 text-[12px] font-medium transition ${
                  isActive
                    ? "bg-kfl-blue/20 text-white border-l-2 border-kfl-blue"
                    : "text-slate-300 hover:bg-white/[0.05] hover:text-white border-l-2 border-transparent"
                }`
              }
              onClick={() => setOpen(true)}
            >
              <item.icon size={14} className="shrink-0 opacity-70" />
              <span className="nav-label truncate">{item.label}</span>
            </NavLink>
          ))}
        </nav>
      )}
    </div>
  );
}

const sections: SectionProps[] = [
  {
    label: "Safety",
    icon: AlertTriangle,
    items: [
      { to: "/occurrences", icon: AlertTriangle, label: "Safety Occurrences", permission: "safety:read" },
      { to: "/hazards", icon: AlertTriangle, label: "Hazard Register", permission: "safety:read" },
      { to: "/risk-assessments", icon: ShieldCheck, label: "Risk Assessments", permission: "safety:read" },
      { to: "/investigations", icon: Search, label: "Investigations", permission: "safety:read" },
      { to: "/safety-actions", icon: CheckCircle, label: "Safety Actions", permission: "safety:read" },
      { to: "/safety-kpis", icon: Activity, label: "Safety KPIs", permission: "safety:read" },
    ],
  },
  {
    label: "Flight",
    icon: AlertOctagon,
    items: [
      { to: "/missions", icon: ClipboardList, label: "Missions", permission: "safety:read" },
      { to: "/dangerous-goods", icon: AlertOctagon, label: "Dangerous Goods", permission: "safety:read" },
      { to: "/roc", icon: ClipboardCheck, label: "ROC & OpSpec", permission: "roc:read" },
      { to: "/dg-responsibility-matrix", icon: ClipboardList, label: "DG Responsibilities", permission: "safety:read" },
    ],
  },
  {
    label: "Quality & Compliance",
    icon: ClipboardCheck,
    items: [
      { to: "/quality-audits", icon: ClipboardCheck, label: "Quality Audits", permission: "safety:read" },
      { to: "/corrective-actions", icon: CheckCircle, label: "Corrective Actions", permission: "safety:read" },
      { to: "/audit-trail", icon: ScrollText, label: "Audit Trail", permission: "audit:read" },
      { to: "/distributions", icon: MailOpen, label: "Distributions", permission: "document:read" },
      { to: "/outsourced-functions", icon: ClipboardList, label: "Outsourced Functions", permission: "compliance:read" },
      { to: "/security-reviews", icon: ShieldCheck, label: "Security Reviews", permission: "security:read_sensitive" },
      { to: "/security", icon: ShieldAlert, label: "Security Incidents", permission: "security:read_sensitive" },
    ],
  },
  {
    label: "Personnel",
    icon: Users,
    items: [
      { to: "/personnel-licenses", icon: KeyRound, label: "Personnel Licenses", permission: "personnel:read" },
      { to: "/crew", icon: Users, label: "Crew Management", permission: "personnel:read" },
      { to: "/duties", icon: Clock, label: "Duty Time Tracking", permission: "personnel:read" },
      { to: "/crew-qualifications", icon: Award, label: "Crew Qualifications", permission: "personnel:read" },
      { to: "/training", icon: GraduationCap, label: "Training Management", permission: "personnel:read" },
      { to: "/self-service-upload", icon: Upload, label: "Self-Service Upload", permission: "personnel:view" },
      { to: "/renewal-progress", icon: Activity, label: "Renewal Progress", permission: "personnel:read" },
    ],
  },
  {
    label: "Aircraft",
    icon: Shield,
    items: [
      { to: "/maintenance", icon: Wrench, label: "Maintenance Management", permission: "aircraft:read" },
      { to: "/aircraft-insurance", icon: Shield, label: "Aircraft Insurance", permission: "aircraft:read" },
    ],
  },
  {
    label: "Document Control",
    icon: FileText,
    items: [
      { to: "/documents", icon: FileText, label: "Documents", permission: "document:read" },
      { to: "/change-requests", icon: FileText, label: "Change Requests", permission: "document:read" },
      { to: "/document-proposals", icon: KeyRound, label: "Document Proposals", permission: "document:read" },
      { to: "/version-diff", icon: Activity, label: "Version Diff", permission: "document:read" },
    ],
  },
  {
    label: "Audit",
    icon: FileText,
    items: [
      { to: "/audit-reports", icon: FileText, label: "Audit Reports", permission: "audit_report:read" },
      { to: "/audit-findings", icon: AlertTriangle, label: "Audit Findings", permission: "audit_finding:read" },
      { to: "/audit-dashboard", icon: BarChart3, label: "Audit Dashboard", permission: "audit_finding:read" },
    ],
  },
  {
    label: "Administration",
    icon: Activity,
    items: [{ to: "/admin/observability", icon: Activity, label: "System Observability", role: "system_admin" }],
  },
];

export function AppShell() {
  const navigate = useNavigate();
  const { profile, hasPermission, logout, switchRole } = useAuth();
  const [logoutError, setLogoutError] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);
  const [roleSwitchError, setRoleSwitchError] = useState("");
  const [switchingRole, setSwitchingRole] = useState(false);
  const homeRoute = getPostLoginPath(profile);
  const homeLabel = homeRoute === "/" ? "Go to dashboard" : `Go to ${sections.flatMap((section) => section.items).find((item) => item.to === homeRoute)?.label ?? "account security"}`;
  const { data: unread } = useQuery({
    queryKey: ["unread-notifications"],
    queryFn: () => safetyApi.getUnreadCount(),
    refetchInterval: 60000,
    enabled: hasPermission("safety:read"),
  });

  const unreadCount = unread?.unread_count ?? 0;
  const visibleSections = sections
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => item.role ? item.role === profile?.active_role : !item.permission || hasPermission(item.permission)),
    }))
    .filter((section) => section.items.length > 0);

  async function handleRoleSwitch(activeRole: string) {
    setRoleSwitchError("");
    setSwitchingRole(true);
    try {
      const nextProfile = await switchRole(activeRole);
      const currentPath = `${window.location.pathname}${window.location.search}`;
      const safePath = getPostLoginPath(nextProfile, currentPath);
      if (safePath !== currentPath) navigate(safePath, { replace: true });
    } catch {
      setRoleSwitchError("Role switch was not confirmed. Verify the active role shown before continuing.");
    } finally {
      setSwitchingRole(false);
    }
  }

  async function handleLogout() {
    setLogoutError("");
    setLoggingOut(true);
    try {
      await logout();
      navigate("/login", { replace: true });
    } catch {
      setLogoutError("Sign-out was not confirmed. Your session may still be active; retry before leaving this workstation.");
    } finally {
      setLoggingOut(false);
    }
  }

  return (
    <div className="app-shell flex min-h-screen bg-kfl-canvas">
      <aside className="app-sidebar sticky top-0 flex h-screen w-[264px] shrink-0 flex-col bg-kfl-dark px-4 py-5 text-white shadow-xl">
        <div className="mb-7 flex items-center justify-between gap-3 px-2">
          <button onClick={() => navigate(homeRoute)} className="rounded-md p-1 text-left focus-visible:ring-2 focus-visible:ring-sky-300" aria-label={homeLabel}>
            <img src="/brand/kfl-logo.png" alt="Kenya Flying Labs" className="h-12 w-auto object-contain object-left" />
          </button>
          {hasPermission("safety:read") && (
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
          )}
        </div>

        <div className="space-y-2 px-1">
          {hasPermission("safety:read") && (
            <NavLink
              to="/"
              end
              className={({ isActive }) => `mb-2 flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition ${isActive ? "bg-kfl-blue/20 text-white" : "text-sky-200/80 hover:bg-white/10 hover:text-white"}`}
            >
              <LayoutDashboard size={16} className="shrink-0" />
              <span className="nav-label">Dashboard</span>
            </NavLink>
          )}
          {visibleSections.map((section) => {
            // Single-item sections render as direct nav links instead of collapsible sections
            if (section.items.length === 1) {
              const item = section.items[0];
              if (item.role && item.role !== profile?.active_role) return null;
              if (item.permission && !hasPermission(item.permission)) return null;
              return (
                <NavLink
                  key={section.label}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) => `mb-2 flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition ${isActive ? "bg-kfl-blue/20 text-white" : "text-sky-200/80 hover:bg-white/10 hover:text-white"}`}
                >
                  <item.icon size={16} className="shrink-0" />
                  <span className="nav-label">{item.label}</span>
                </NavLink>
              );
            }
            return <CollapsibleSection key={section.label} {...section} />;
          })}
        </div>

        <div role="region" aria-label="Account and session controls" className="mobile-session-controls mt-auto border-t border-white/10 px-3 pt-4 text-[11px] text-slate-400">
          <div className={`flex items-center gap-2 ${logoutError ? "text-rose-300" : "text-emerald-300"}`}>
            <span className={`h-2 w-2 rounded-full ${logoutError ? "bg-rose-400 shadow-[0_0_0_3px_rgba(251,113,133,0.15)]" : "bg-emerald-400 shadow-[0_0_0_3px_rgba(52,211,153,0.15)]"}`} />
            <span>{logoutError ? "Sign-out not confirmed" : "Secure session active"}</span>
          </div>
          {profile && profile.roles.length > 1 && (
            <div className="mt-3">
              <label htmlFor="active-role" className="mb-1 block text-[10px] font-semibold uppercase tracking-wide text-slate-400">Active role</label>
              <select
                id="active-role"
                name="active-role"
                value={profile.active_role}
                disabled={switchingRole}
                onChange={(event) => void handleRoleSwitch(event.target.value)}
                className="w-full rounded border border-white/10 bg-kfl-dark px-2 py-1.5 text-xs text-slate-100 disabled:opacity-60"
              >
                {profile.roles.map((role) => <option key={role} value={role}>{role.replace(/_/g, " ")}</option>)}
              </select>
              {roleSwitchError && <p role="alert" className="mt-1 text-[10px] text-rose-300">{roleSwitchError}</p>}
            </div>
          )}
          <div className="mt-2 text-slate-300">{profile?.user.full_name} · {profile?.active_role}</div>
          <div className="mt-3 flex items-center justify-between gap-2">
            <NavLink to="/account/security" className="rounded px-2 py-1 text-slate-300 hover:bg-white/10 hover:text-white">Account security</NavLink>
            <NavLink to="/account/profile" className="rounded px-2 py-1 text-slate-300 hover:bg-white/10 hover:text-white">Profile settings</NavLink>
            <button
              type="button"
              disabled={loggingOut}
              onClick={() => void handleLogout()}
              className="flex items-center gap-1 rounded px-2 py-1 text-slate-300 hover:bg-white/10 hover:text-white disabled:opacity-60"
              aria-label={logoutError ? "Retry sign out" : "Sign out"}
            >
              <LogOut size={14} /> {loggingOut ? "Signing out…" : logoutError ? "Retry sign out" : "Sign out"}
            </button>
          </div>
          <div className="mt-2 text-slate-500">KFL Aviation DMS · v1.0</div>
        </div>
      </aside>

      <main className="app-main min-w-0 flex-1 overflow-auto bg-kfl-canvas">
        {logoutError && (
          <div role="alert" className="m-4 flex items-center justify-between gap-4 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
            <p>{logoutError}</p>
            <button type="button" onClick={() => void handleLogout()} disabled={loggingOut} className="rounded px-3 py-2 font-semibold hover:bg-rose-100 disabled:opacity-60">
              {loggingOut ? "Retrying…" : "Retry sign out"}
            </button>
          </div>
        )}
        <Outlet />
      </main>
    </div>
  );
}
