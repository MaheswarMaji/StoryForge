import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Flame, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

export default function AuthCallback() {
  const processed = useRef(false);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;
    const sessionId = (location.hash.match(/session_id=([^&]+)/) || [])[1];
    if (!sessionId) {
      navigate("/login", { replace: true });
      return;
    }
    api.post("/auth/session", { session_id: sessionId })
      .then((r) => {
        window.history.replaceState(null, "", window.location.pathname);
        navigate("/dashboard", { replace: true, state: { user: r.data.user } });
      })
      .catch(() => navigate("/login", { replace: true }));
  }, [location.hash, navigate]);

  return (
    <div className="grain flex min-h-screen items-center justify-center" style={{ background: "#090A0F" }}>
      <div className="flex items-center gap-3 text-sm text-slate-300">
        <Flame className="h-5 w-5 text-amber-400" />
        Signing you in
        <Loader2 className="h-4 w-4 animate-spin text-amber-400" />
      </div>
    </div>
  );
}
