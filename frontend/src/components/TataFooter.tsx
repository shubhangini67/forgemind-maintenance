import Link from "next/link";
import { TataSteelWordmark } from "@/components/TataBrand";

export function TataFooter() {
  return (
    <footer className="mt-auto border-t border-tata-border bg-[#0f1419] text-white">
      <div className="mx-auto grid max-w-6xl gap-10 px-6 py-12 sm:grid-cols-3 sm:px-10">
        <div>
          <TataSteelWordmark light />
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-white/50">
            Predictive maintenance portal for the steel plant fleet — C-MAPSS FD001 integration.
          </p>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-white/40">Quick links</p>
          <ul className="mt-4 space-y-2 text-sm text-white/65">
            <li><Link href="/dashboard" className="hover:text-white">Dashboard</Link></li>
            <li><Link href="/monitor" className="hover:text-white">Live Monitor</Link></li>
            <li><Link href="/alerts" className="hover:text-white">Alerts</Link></li>
            <li><Link href="/how-it-works" className="hover:text-white">How It Works</Link></li>
          </ul>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.25em] text-white/40">Plant assets</p>
          <p className="mt-4 text-sm text-white/65">BF-001 · RM-002 · CP-003 · CW-004 · CN-005</p>
          <p className="mt-3 text-[11px] text-white/35">Demo environment · Not for production use</p>
        </div>
      </div>
      <div className="border-t border-white/10 px-6 py-4 text-center text-[11px] text-white/35 sm:px-10">
        © {new Date().getFullYear()} Tata Steel Maintenance Wizard · Engineer Portal
      </div>
    </footer>
  );
}
