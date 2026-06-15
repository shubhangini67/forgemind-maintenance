"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

export function NavigationProgress() {
  const pathname = usePathname();
  const [pending, setPending] = useState(false);

  useEffect(() => {
    setPending(false);
  }, [pathname]);

  useEffect(() => {
    function onClick(event: MouseEvent) {
      const anchor = (event.target as Element | null)?.closest("a[href]") as HTMLAnchorElement | null;
      if (!anchor || anchor.target === "_blank" || event.defaultPrevented) return;

      const href = anchor.getAttribute("href");
      if (!href || href.startsWith("#") || href.startsWith("mailto:")) return;

      try {
        const next = new URL(href, window.location.href);
        if (next.origin !== window.location.origin) return;
        if (next.pathname === pathname) return;
        setPending(true);
      } catch {
        /* ignore malformed href */
      }
    }

    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [pathname]);

  if (!pending) return null;

  return (
    <>
      <div className="pointer-events-none fixed inset-0 z-[100] cursor-wait bg-black/[0.03]" aria-hidden />
      <div className="fixed left-0 right-0 top-0 z-[101] h-1 overflow-hidden bg-tata-blue/15">
        <div className="nav-progress-bar h-full w-1/3 bg-gradient-to-r from-tata-blue to-tata-blue-light" />
      </div>
      <div className="pointer-events-none fixed inset-x-0 top-20 z-[100] flex justify-center">
        <div className="rounded-full bg-white px-4 py-2 text-sm font-medium text-tata-ink shadow-panel ring-1 ring-tata-border/80">
          Opening page…
        </div>
      </div>
    </>
  );
}
