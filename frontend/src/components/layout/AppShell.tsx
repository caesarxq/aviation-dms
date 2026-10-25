import { Outlet, NavLink, useNavigate } from "react-router-dom";
import {
  Activity,
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
} from "lucide-react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { safetyApi } from "../../api/safety";
import api from "../../api/client";

interface NavItem {
  to: string;
  icon: any;
  label: string;
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
    label: "Safety & Flight",
    icon: AlertTriangle,
    items: [
      { to: "/occurrences", icon: AlertTriangle, label: "Safety Occurrences" },
      { to: "/hazards", icon: AlertTriangle, label: "Hazard Register" },
      { to: "/risk-assessments", icon: ShieldCheck, label: "Risk Assessments" },
      { to: "/investigations", icon: Search, label: "Investigations" },
      { to: "/safety-actions", icon: CheckCircle, label: "Safety Actions" },
      { to: "/missions", icon: ClipboardList, label: "Missions" },
      { to: "/dangerous-goods", icon: AlertOctagon, label: "Dangerous Goods" },
      { to: "/security", icon: ShieldAlert, label: "Security" },
    ],
  },
  {
    label: "Quality & Compliance",
    icon: ClipboardCheck,
    items: [{ to: "/quality-audits", icon: ClipboardCheck, label: "Quality Audits" }],
  },
  {
    label: "Personnel & Aircraft",
    icon: Users,
    items: [
      { to: "/personnel-licenses", icon: KeyRound, label: "Personnel Licenses" },
      { to: "/aircraft-insurance", icon: Shield, label: "Aircraft Insurance" },
      { to: "/self-service-upload", icon: Upload, label: "Self-Service Upload" },
    ],
  },
  {
    label: "Document Control",
    icon: FileText,
    items: [
      { to: "/documents", icon: FileText, label: "Documents" },
      { to: "/document-proposals", icon: KeyRound, label: "Document Proposals" },
      { to: "/version-diff", icon: Activity, label: "Version Diff" },
    ],
  },
  {
    label: "Administration",
    icon: Activity,
    items: [{ to: "/admin/observability", icon: Activity, label: "System Observability" }],
  },
];

export function AppShell() {
  const navigate = useNavigate();
  const { data: unread } = useQuery({
    queryKey: ["unread-notifications"],
    queryFn: () => safetyApi.getUnreadCount(),
    refetchInterval: 60000,
  });
  const { data: authProfile } = useQuery({
    queryKey: ["auth-profile"],
    queryFn: () => api.get("/p0/auth/profile").then((response: any) => response.data),
    staleTime: 300000,
  });

  const unreadCount = unread?.unread_count ?? 0;
  const visibleSections = sections.filter((section) => section.label !== "Administration" || authProfile?.role === "system_admin");

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

        <div className="space-y-2 px-1">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `mb-2 flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition ${isActive ? "bg-kfl-blue/20 text-white" : "text-sky-200/80 hover:bg-white/10 hover:text-white"}`}
          >
            <LayoutDashboard size={16} className="shrink-0" />
            <span className="nav-label">Dashboard</span>
          </NavLink>
          {visibleSections.map((section) => (
            <CollapsibleSection key={section.label} {...section} />
          ))}
        </div>

        <div className="mt-auto border-t border-white/10 px-3 pt-4 text-[11px] text-slate-400">
          <div className="flex items-center gap-2 text-emerald-300">
            <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_0_3px_rgba(52,211,153,0.15)]" />
            <span>Operational control active</span>
          </div>
          <div className="mt-2 text-slate-500">{authProfile?.user?.full_name || "Authenticated user"} · {authProfile?.role || "loading profile"}</div>
          <div className="mt-1 text-slate-500">KFL Aviation DMS · v1.0</div>
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-auto bg-kfl-canvas">
        <Outlet />
      </main>
    </div>
  );
}
