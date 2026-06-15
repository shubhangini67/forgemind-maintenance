"use client";

import { useCallback, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { ChevronRight, UserCog, Users, Wrench } from "lucide-react";
import { api, setToken } from "@/lib/api";
import { TataEmblem, TataSteelWordmark } from "@/components/TataBrand";

const HERO_IMAGE =
  "https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?w=2400&q=85";

const DEMO_ROLES = [
  {
    title: "Maintenance Engineer",
    email: "engineer@steelplant.com",
    password: "demo1234",
    icon: Wrench,
  },
  {
    title: "Supervisor",
    email: "supervisor@steelplant.com",
    password: "demo1234",
    icon: Users,
  },
  {
    title: "Administrator",
    email: "admin@steelplant.com",
    password: "demo1234",
    icon: UserCog,
  },
] as const;

export function LoginExperience() {
  const router = useRouter();
  const [email, setEmail] = useState("engineer@steelplant.com");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const applyRole = useCallback((roleEmail: string, rolePassword: string) => {
    setEmail(roleEmail);
    setPassword(rolePassword);
    setError("");
  }, []);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await api.login(email, password);
      setToken(data.access_token);
      router.push("/home");
    } catch {
      setError("Authentication failed — verify credentials or start the backend service.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen flex-col bg-[#0a1628] text-white">
      <Image
        src={HERO_IMAGE}
        alt=""
        fill
        priority
        className="object-cover object-center"
        sizes="100vw"
      />
      <div className="absolute inset-0 bg-gradient-to-b from-[#001a33]/90 via-[#0a1628]/85 to-black/90" />

      <header className="relative z-20 border-b border-white/10 bg-[#005da4]/90 backdrop-blur-md">
        <div className="mx-auto flex h-[68px] max-w-lg items-center justify-between px-6">
          <TataSteelWordmark light />
          <TataEmblem className="h-9 w-9 text-white" />
        </div>
      </header>

      <main className="relative z-10 flex flex-1 items-center justify-center px-4 py-10">
        <section
          className="login-fade-in w-full max-w-md"
          aria-labelledby="login-form-title"
        >
          <div className="login-glass-panel rounded-2xl border border-white/15 p-6 shadow-2xl sm:p-8">
            <div className="mb-6 text-center">
              <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-sky-200/70">
                Maintenance Command Center
              </p>
              <h1 id="login-form-title" className="mt-2 text-xl font-light tracking-tight text-white sm:text-2xl">
                Sign in to continue
              </h1>
            </div>

            <form onSubmit={handleLogin} className="space-y-4" noValidate>
              <div>
                <label htmlFor="engineer-id" className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/55">
                  Engineer ID
                </label>
                <input
                  id="engineer-id"
                  className="login-input mt-1.5"
                  type="email"
                  autoComplete="username"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  aria-describedby={error ? "login-error" : undefined}
                />
              </div>
              <div>
                <label htmlFor="password" className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/55">
                  Password
                </label>
                <input
                  id="password"
                  className="login-input mt-1.5"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  aria-describedby={error ? "login-error" : undefined}
                />
              </div>

              {error && (
                <p id="login-error" className="rounded-lg border border-red-400/30 bg-red-950/40 px-3 py-2 text-center text-sm text-red-200" role="alert">
                  {error}
                </p>
              )}

              <button
                type="submit"
                className="login-submit-btn group flex w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-[#005da4] to-[#006bb8] px-5 py-3.5 text-xs font-semibold uppercase tracking-[0.14em] text-white shadow-lg transition hover:from-[#004a85] hover:to-[#005da4] disabled:opacity-50"
                disabled={loading}
              >
                {loading ? "Authenticating…" : "Enter Maintenance Command Center"}
                {!loading && (
                  <ChevronRight className="h-4 w-4 transition group-hover:translate-x-0.5" strokeWidth={2} aria-hidden="true" />
                )}
              </button>
            </form>

            <div className="mt-7">
              <p className="mb-3 text-center text-[10px] font-semibold uppercase tracking-[0.2em] text-white/45">
                Demo Access
              </p>
              <div className="grid gap-2" role="list" aria-label="Demo role credentials">
                {DEMO_ROLES.map(({ title, email: roleEmail, password: rolePassword, icon: Icon }) => (
                  <button
                    key={title}
                    type="button"
                    role="listitem"
                    onClick={() => applyRole(roleEmail, rolePassword)}
                    className="login-role-card group flex w-full items-center gap-3 rounded-lg border border-white/10 bg-white/[0.04] px-3.5 py-2.5 text-left transition hover:border-sky-400/35 hover:bg-white/[0.08] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400"
                    aria-label={`Use ${title} demo credentials: ${roleEmail}`}
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[#005da4]/35 text-sky-200">
                      <Icon className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden="true" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium text-white">{title}</span>
                      <span className="block truncate font-mono text-[10px] text-white/45">
                        {roleEmail} · {rolePassword}
                      </span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
