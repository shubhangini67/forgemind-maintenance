"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, Suspense } from "react";
import { clearToken } from "@/lib/api";
import { NavigationProgress } from "@/components/NavigationProgress";
import { BackendStatus } from "@/components/BackendStatus";
import { TataEmblem, TataSteelWordmark } from "@/components/TataBrand";
import { TataFooter } from "@/components/TataFooter";
import { Brain, ChevronRight, Home, LogOut, Menu, Search, X } from "lucide-react";

const AiChatWidget = dynamic(
  () => import("@/components/AiChatWidget").then((m) => ({ default: m.AiChatWidget })),
  { ssr: false, loading: () => null }
);

const NAV = [
  {
    label: "Overview",
    items: [
      { href: "/home", label: "Portal Home" },
      { href: "/dashboard", label: "Dashboard" },
      { href: "/equipment", label: "Equipment" },
      { href: "/monitor", label: "Live Monitor" },
    ],
  },
  {
    label: "AI Assistant",
    items: [
      { href: "/chat", label: "Ask AI" },
      { href: "/diagnose", label: "Diagnose" },
    ],
  },
  {
    label: "Maintenance",
    items: [
      { href: "/simulate", label: "Decision Simulator" },
      { href: "/priority", label: "Priority" },
      { href: "/alerts", label: "Alerts" },
      { href: "/scheduler", label: "Schedule" },
    ],
  },
  {
    label: "Records",
    items: [
      { href: "/logbook", label: "Logbook" },
      { href: "/delays", label: "Delay Logs" },
      { href: "/history", label: "History" },
      { href: "/reports", label: "Reports" },
      { href: "/spares", label: "Inventory" },
      { href: "/knowledge", label: "Documents" },
      { href: "/analytics", label: "Analytics" },
    ],
  },
];

const FOOTER_NAV = [
  { href: "/how-it-works", label: "How It Works" },
  { href: "/credits", label: "Requirements" },
];

const ROUTE_LABELS: Record<string, string> = {
  home: "Portal Home",
  dashboard: "Dashboard",
  equipment: "Equipment",
  monitor: "Live Monitor",
  chat: "Ask AI",
  diagnose: "Diagnose",
  simulate: "Decision Simulator",
  priority: "Priority",
  alerts: "Alerts",
  scheduler: "Schedule",
  logbook: "Logbook",
  delays: "Delay Logs",
  history: "History",
  reports: "Reports",
  spares: "Inventory",
  knowledge: "Documents",
  analytics: "Analytics",
  "how-it-works": "How It Works",
  credits: "Requirements",
};

function Breadcrumb() {
  const pathname = usePathname();
  if (pathname === "/home") return null;

  const segment = pathname.split("/").filter(Boolean)[0] || "";
  const label = ROUTE_LABELS[segment] || segment;

  return (
    <div className="breadcrumb-bar">
      <div className="page-wrap flex items-center gap-2">
        <Link href="/home" className="transition hover:text-tata-blue">
          Home
        </Link>
        <ChevronRight className="h-3 w-3 opacity-40" />
        <span className="font-medium text-tata-ink">{label}</span>
      </div>
    </div>
  );
}

export function Shell({ children, fullWidth = false }: { children: React.ReactNode; fullWidth?: boolean }) {
  const pathname = usePathname();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [aiMounted, setAiMounted] = useState(false);

  const showAiFab = pathname !== "/" && pathname !== "/chat";

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!showAiFab) return;
    let cancelled = false;
    const mount = () => {
      if (!cancelled) setAiMounted(true);
    };
    const timer = window.setTimeout(mount, 1200);
    const idleId =
      typeof window.requestIdleCallback === "function"
        ? window.requestIdleCallback(mount, { timeout: 3000 })
        : null;
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      if (idleId !== null && typeof window.cancelIdleCallback === "function") {
        window.cancelIdleCallback(idleId);
      }
    };
  }, [showAiFab]);

  function openAi() {
    setAiMounted(true);
    setAiOpen(true);
  }

  useEffect(() => {
    if (!menuOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuOpen(false);
    }
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  function logout() {
    clearToken();
    router.push("/");
  }

  return (
    <div className="flex min-h-screen flex-col">
      <NavigationProgress />
      <header className="sticky top-0 z-30 bg-tata-blue shadow-md">
        <div className="flex h-[72px] items-center justify-between px-5 lg:px-10">
          <div className="flex items-center gap-6 lg:gap-10">
            <Link href="/home">
              <TataSteelWordmark light />
            </Link>

            <button
              type="button"
              onClick={() => setMenuOpen(true)}
              className="flex items-center gap-2.5 text-tata-menu transition hover:text-white"
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" strokeWidth={1.75} />
              <span className="text-[13px] font-semibold uppercase tracking-[0.2em]">Menu</span>
            </button>
          </div>

          <div className="flex items-center gap-1 sm:gap-2">
            <Link href="/home" className="hidden p-2.5 text-white/85 transition hover:text-white sm:block" title="Home">
              <Home className="h-[18px] w-[18px]" strokeWidth={1.5} />
            </Link>
            {showAiFab && (
              <button
                type="button"
                onClick={openAi}
                className="hidden items-center gap-2 rounded-lg bg-white/10 px-2.5 py-1.5 text-white ring-1 ring-white/15 transition hover:bg-white/20 sm:flex"
                title="AI"
              >
                <Brain className="h-4 w-4" strokeWidth={1.5} />
                <span className="text-[10px] font-bold uppercase tracking-wider">AI</span>
              </button>
            )}
            <button type="button" className="hidden p-2.5 text-white/85 transition hover:text-white sm:block" aria-label="Search">
              <Search className="h-[18px] w-[18px]" strokeWidth={1.5} />
            </button>
            <div className="hidden sm:block">
              <BackendStatus variant="sidebar" />
            </div>
            <button onClick={logout} className="p-2.5 text-white/85 transition hover:text-white" title="Sign out">
              <LogOut className="h-[18px] w-[18px]" strokeWidth={1.5} />
            </button>
            <div className="ml-1 hidden text-white sm:block">
              <TataEmblem className="h-10 w-10" />
            </div>
          </div>
        </div>
      </header>

      <Breadcrumb />

      <div
        className={`fixed inset-0 z-40 bg-black/55 transition-opacity duration-200 ${
          menuOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={() => setMenuOpen(false)}
      />

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-[min(100vw,360px)] flex-col bg-[#0f1419] will-change-transform transition-transform duration-200 ease-out ${
          menuOpen ? "translate-x-0" : "-translate-x-full pointer-events-none"
        }`}
        aria-hidden={!menuOpen}
      >
        <div className="flex items-start justify-between px-6 py-6">
          <button
            type="button"
            onClick={() => setMenuOpen(false)}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-white/20 text-white transition hover:bg-white/10"
            aria-label="Close menu"
          >
            <X className="h-5 w-5" strokeWidth={1.5} />
          </button>
          <Link href="/home" onClick={() => setMenuOpen(false)} className="pt-1">
            <TataSteelWordmark light />
          </Link>
        </div>

        <nav className="flex-1 overflow-y-auto pb-8">
          {NAV.map((group) => (
            <div key={group.label}>
              <p className="px-6 py-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-white/30">{group.label}</p>
              {group.items.map(({ href, label }) => {
                const active = pathname === href || (href !== "/home" && pathname.startsWith(`${href}/`));
                return (
                  <Link
                    key={href}
                    href={href}
                    prefetch={false}
                    onClick={() => setMenuOpen(false)}
                    className={`block border-b border-white/[0.06] px-6 py-3.5 text-[15px] transition ${
                      active
                        ? "border-l-2 border-l-tata-blue bg-white/[0.05] font-medium text-white"
                        : "font-light text-white/75 hover:bg-white/[0.03] hover:text-white"
                    }`}
                  >
                    {label}
                  </Link>
                );
              })}
            </div>
          ))}

          <div className="mt-2 border-t border-white/10">
            {FOOTER_NAV.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                prefetch={false}
                onClick={() => setMenuOpen(false)}
                className="block border-b border-white/[0.06] px-6 py-3.5 text-[15px] font-light text-white/65 hover:text-white"
              >
                {label}
              </Link>
            ))}
          </div>
        </nav>
      </aside>

      <main className={`flex-1 ${fullWidth ? "" : "page-bg"}`}>
        <div className={fullWidth ? "" : "px-4 py-6 sm:px-6 sm:py-8"}>
          <div className={fullWidth ? "" : "page-wrap"}>{children}</div>
        </div>
      </main>

      <TataFooter />

      {showAiFab && !aiOpen && (
        <button type="button" onClick={openAi} className="ai-fab group" aria-label="AI assistant">
          <span className="ai-fab-icon">
            <Brain className="h-5 w-5" strokeWidth={1.75} />
          </span>
          <span className="text-base font-semibold tracking-tight">AI</span>
          <ChevronRight className="ai-fab-chevron h-4 w-4 shrink-0 text-white/70" strokeWidth={2} />
        </button>
      )}

      {aiMounted && showAiFab && (
        <Suspense fallback={null}>
          <AiChatWidget open={aiOpen} onOpenChange={setAiOpen} hideFab />
        </Suspense>
      )}
    </div>
  );
}
