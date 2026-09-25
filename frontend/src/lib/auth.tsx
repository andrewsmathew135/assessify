import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { authApi, configApi, getToken, setToken } from "./api";

interface AuthContextValue {
  email: string | null;
  authEnabled: boolean;
  isAuthenticated: boolean;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [email, setEmail] = useState<string | null>(null);
  const [authEnabled, setAuthEnabled] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    configApi
      .get()
      .then((cfg) => {
        if (!active) return;
        setAuthEnabled(cfg.auth_enabled);
        if (!cfg.auth_enabled) {
          setEmail("admin");
          setLoading(false);
          return;
        }
        const token = getToken();
        if (!token) {
          setLoading(false);
          return;
        }
        authApi
          .me()
          .then((me) => active && setEmail(me.email))
          .catch(() => setToken(null))
          .finally(() => active && setLoading(false));
      })
      .catch(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const login = async (emailInput: string, password: string) => {
    const { access_token } = await authApi.login(emailInput, password);
    setToken(access_token);
    const me = await authApi.me();
    setEmail(me.email);
  };

  const logout = () => {
    setToken(null);
    setEmail(null);
  };

  const isAuthenticated = !authEnabled || !!email;

  return (
    <AuthContext.Provider
      value={{ email, authEnabled, isAuthenticated, loading, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
