import * as Dialog from "@radix-ui/react-dialog";
import * as Tooltip from "@radix-ui/react-tooltip";
import {
  BarChart3,
  Database,
  FileText,
  LogOut,
  Menu,
  Upload,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { useCompany } from "../hooks/useCompany";
import { signOut } from "../lib/auth";
import { cn } from "../lib/utils";
import { useToast } from "./ToastProvider";

/**
 * AppShell — two-column desktop / top-bar-drawer mobile, per docs/design.md.
 *
 * Breakpoints (Tailwind):
 *   lg (≥1024px):  fixed 240-px left SideNav + main content offset with lg:pl-60
 *   <lg:           sticky top bar with hamburger + Radix Dialog drawer from left
 *
 * Nav items: Upload (active), Reports + Dashboard (dimmed with "Coming soon"
 * tooltip — destination pages are post-MVP; the shell is ready when they ship).
 */

type NavItem = {
  to: string;
  label: string;
  icon: typeof Upload;
  enabled: boolean;
  tooltip?: string;
};

const NAV_ITEMS: NavItem[] = [
  {
    to: "/dashboard",
    label: "Dashboard",
    icon: BarChart3,
    enabled: true,
  },
  { to: "/upload", label: "Upload", icon: Upload, enabled: true },
  {
    to: "/data",
    label: "Data",
    icon: Database,
    enabled: true,
  },
  {
    to: "/reports",
    label: "Reports",
    icon: FileText,
    enabled: true,
  },
];

function isRouteActive(pathname: string, to: string): boolean {
  if (pathname === to) return true;
  // Report pages belong to the Upload flow — highlight Upload while reading a report.
  if (to === "/upload" && pathname.startsWith("/report")) return true;
  return false;
}

interface NavItemLinkProps {
  item: NavItem;
  onNavigate?: () => void;
}

function NavItemLink({ item, onNavigate }: NavItemLinkProps) {
  const location = useLocation();
  const active = isRouteActive(location.pathname, item.to);

  const base =
    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors min-h-[44px] lg:min-h-[40px]";

  if (!item.enabled) {
    return (
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <div
            className={cn(
              base,
              "text-text-secondary opacity-50 cursor-not-allowed select-none"
            )}
            aria-disabled="true"
            tabIndex={0}
          >
            <item.icon className="h-4 w-4 shrink-0" aria-hidden />
            <span>{item.label}</span>
          </div>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            side="right"
            sideOffset={8}
            className="rounded bg-text-primary px-2 py-1 text-xs text-white shadow-md z-[60]"
          >
            {item.tooltip ?? "Coming soon"}
            <Tooltip.Arrow className="fill-text-primary" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    );
  }

  return (
    <Link
      to={item.to}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        base,
        active
          ? "bg-amber-50 text-amber-700 font-medium border-l-2 border-amber-500 pl-[10px]"
          : "text-text-secondary hover:text-text-primary hover:bg-canvas focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      )}
    >
      <item.icon className="h-4 w-4 shrink-0" aria-hidden />
      <span>{item.label}</span>
    </Link>
  );
}

function NavItemList({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav
      aria-label="Main"
      className="flex-1 px-3 py-3 space-y-1 overflow-y-auto"
    >
      <Tooltip.Provider delayDuration={150}>
        {NAV_ITEMS.map((item) => (
          <NavItemLink key={item.to} item={item} onNavigate={onNavigate} />
        ))}
      </Tooltip.Provider>
    </nav>
  );
}

function NavHeader({
  showClose,
  onClose,
}: {
  showClose?: boolean;
  onClose?: () => void;
}) {
  return (
    <div className="flex items-center justify-between px-4 h-14 border-b border-border shrink-0">
      <div className="flex items-baseline gap-2 min-w-0">
        <span className="text-base font-semibold text-text-primary tracking-tight">
          IronLedger
        </span>
        <span className="text-xs text-text-secondary hidden xl:inline">
          Month-end close
        </span>
      </div>
      {showClose && (
        <button
          type="button"
          onClick={onClose}
          aria-label="Close navigation"
          className="flex items-center justify-center h-11 w-11 -mr-2 rounded-md text-text-secondary hover:text-text-primary hover:bg-canvas"
        >
          <X className="h-5 w-5" aria-hidden />
        </button>
      )}
    </div>
  );
}

function NavFooter({
  onSignOut,
  onNavigate,
}: {
  onSignOut: () => void;
  onNavigate?: () => void;
}) {
  const { user } = useAuth();
  const { data: company } = useCompany();
  const location = useLocation();
  const profileActive = location.pathname === "/profile";

  return (
    <div className="border-t border-border px-3 py-3 space-y-2 shrink-0">
      <Link
        to="/profile"
        onClick={onNavigate}
        aria-current={profileActive ? "page" : undefined}
        aria-label="View profile"
        className={cn(
          "block rounded-md px-2 py-1.5 min-w-0 min-h-[44px] lg:min-h-[40px] transition-colors [transition-duration:var(--duration-base)] focus:outline-none focus-visible:ring-2 focus-visible:ring-accent",
          profileActive
            ? "bg-amber-50 border-l-2 border-amber-500 pl-[6px]"
            : "hover:bg-canvas"
        )}
      >
        {company?.name && (
          <div className="text-sm font-medium text-text-primary truncate">
            {company.name}
          </div>
        )}
        {user?.email && (
          <div className="text-xs text-text-secondary truncate">
            {user.email}
          </div>
        )}
      </Link>
      <button
        type="button"
        onClick={onSignOut}
        className="w-full flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-text-secondary hover:text-text-primary hover:bg-canvas transition-colors [transition-duration:var(--duration-base)] min-h-[44px] lg:min-h-[40px] focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        <LogOut className="h-4 w-4 shrink-0" aria-hidden />
        <span>Sign out</span>
      </button>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const toast = useToast();

  // Auto-close drawer on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  // Mobile deep-link guard: design.md §Responsive says /dashboard on mobile
  // must redirect to / with an info toast.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const isMobile = window.matchMedia("(max-width: 767px)").matches;
    if (isMobile && location.pathname.startsWith("/dashboard")) {
      toast.info("Dashboard is available on larger screens.");
      navigate("/upload", { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  async function handleSignOut() {
    setMobileOpen(false);
    await signOut();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-canvas">
      {/* Desktop SideNav — fixed left column ≥1024px */}
      <aside
        aria-label="Sidebar"
        className="hidden lg:flex fixed inset-y-0 left-0 w-60 flex-col bg-surface border-r border-border z-30"
      >
        <NavHeader />
        <NavItemList />
        <NavFooter onSignOut={handleSignOut} />
      </aside>

      {/* Mobile/tablet top bar + drawer — <1024px */}
      <header className="lg:hidden sticky top-0 z-30 bg-surface border-b border-border">
        <div className="flex items-center gap-2 px-2 sm:px-3 h-14">
          <Dialog.Root open={mobileOpen} onOpenChange={setMobileOpen}>
            <Dialog.Trigger asChild>
              <button
                type="button"
                aria-label="Open navigation"
                aria-expanded={mobileOpen}
                className="flex items-center justify-center h-11 w-11 rounded-md text-text-primary hover:bg-canvas focus:outline-none focus:ring-2 focus:ring-accent"
              >
                <Menu className="h-5 w-5" aria-hidden />
              </button>
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 z-40 bg-black/30 drawer-overlay" />
              <Dialog.Content
                aria-describedby={undefined}
                className="fixed inset-y-0 left-0 z-50 flex w-[80vw] max-w-[320px] flex-col bg-surface shadow-xl focus:outline-none drawer-content"
              >
                <Dialog.Title className="sr-only">Navigation</Dialog.Title>
                <NavHeader
                  showClose
                  onClose={() => setMobileOpen(false)}
                />
                <NavItemList onNavigate={() => setMobileOpen(false)} />
                <NavFooter
                  onSignOut={handleSignOut}
                  onNavigate={() => setMobileOpen(false)}
                />
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>

          <span className="text-base font-semibold text-text-primary tracking-tight">
            IronLedger
          </span>
        </div>
      </header>

      {/* Main content — offset right of SideNav on desktop */}
      <main className="lg:pl-60">{children}</main>
    </div>
  );
}
