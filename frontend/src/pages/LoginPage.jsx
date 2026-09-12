import { useState } from "react";
import { Flame, Loader2 } from "lucide-react";

const GoogleIcon = () => (
  <svg viewBox="0 0 24 24" className="h-4 w-4">
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z" />
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
    <path fill="#FBBC05" d="M5.84 14.1c-.22-.66-.35-1.36-.35-2.1s.13-1.44.35-2.1V7.06H2.18A10.96 10.96 0 0 0 1 12c0 1.77.43 3.45 1.18 4.94l3.66-2.84z" />
    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
  </svg>
);

export default function LoginPage() {
  const [going, setGoing] = useState(false);

  const login = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    setGoing(true);
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="grain flex min-h-screen items-center justify-center px-6" style={{ background: "#090A0F" }}>
      <div className="rise w-full max-w-md rounded-3xl border border-amber-500/15 bg-[#0B0D16]/85 p-10 text-center shadow-[0_30px_80px_rgba(0,0,0,0.6)] backdrop-blur-xl">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-500/15 ring-1 ring-amber-500/40">
          <Flame className="h-8 w-8 text-amber-400" />
        </div>
        <h1 data-testid="login-heading" className="font-display text-3xl font-extrabold tracking-tight text-amber-100">StoryForge</h1>
        <p className="mt-2 text-sm text-slate-400">Mythology, folk tales &amp; public-interest news — your AI video factory.</p>
        <button
          data-testid="google-login-button"
          onClick={login}
          disabled={going}
          className="mt-8 flex w-full items-center justify-center gap-3 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-[#1a1a1a] transition-colors hover:bg-slate-100 disabled:opacity-60"
        >
          {going ? <Loader2 className="h-4 w-4 animate-spin" /> : <GoogleIcon />} Sign in with Google
        </button>
        <p className="mt-6 text-[11px] leading-relaxed text-slate-600">
          Google sign-in is the only way into the studio. Your session stays valid for 7 days.
        </p>
      </div>
    </div>
  );
}
