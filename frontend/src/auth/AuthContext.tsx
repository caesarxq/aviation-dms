import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { hasPermission as profileHasPermission } from "./permissions";
import { clearLegacyIdentity } from "./identity";

export type AuthUser = {
  user_id: string;
  username: string;
  email: string;
  full_name: string;
  role: string;
  active_role: string;
  roles: string[];
  department?: string | null;
};

export type AuthProfile = {
  user: AuthUser;
  role: string;
  active_role: string;
  roles: string[];
  authenticated_via: string;
  permissions: string[];
  onboarding_completed: boolean;
};

type AuthState = "loading" | "authenticated" | "unauthenticated";
type AuthContextValue = {
  profile: AuthProfile | null;
  state: AuthState;
  login: (username: string, password: string) => Promise<AuthProfile>;
  switchRole: (activeRole: string) => Promise<AuthProfile>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<AuthProfile>;
  hasPermission: (permission: string) => boolean;
};

const AuthContextObj = createContext<AuthContextValue | null>(null);

export const AuthContext = AuthContextObj;

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [profile, setProfile] = useState<AuthProfile | null>(null);
  const [state, setState] = useState<AuthState>("loading");
  const queryClient = useQueryClient();

  const refreshProfile = useCallback(async () => {
    const response = await api.get("/p0/auth/profile");
    if (response.status !== 200) throw new Error("Authentication failed");
    const nextProfile = response.data as AuthProfile;
    try {
      const onboardingResponse = await api.get("/p0/auth/me/onboarding");
      if (onboardingResponse.status !== 200) throw new Error("Authentication failed");
      nextProfile.onboarding_completed = onboardingResponse.data.onboarding_completed;
    } catch {
      nextProfile.onboarding_completed = true;
    }
    setProfile(nextProfile);
    setState("authenticated");
    return nextProfile;
  }, []);

  const clearAuthentication = useCallback(() => {
    setProfile(null);
    setState("unauthenticated");
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    clearLegacyIdentity();
    let active = true;
    const load = async () => {
      try {
        const response = await api.get("/p0/auth/profile");
        if (response.status !== 200) throw new Error("Authentication failed");
        let nextProfile = response.data as AuthProfile;
        try {
          const onboardingResponse = await api.get("/p0/auth/me/onboarding");
          if (onboardingResponse.status !== 200) throw new Error("Authentication failed");
          nextProfile.onboarding_completed = onboardingResponse.data.onboarding_completed;
        } catch {
          nextProfile.onboarding_completed = true;
        }
        if (active) {
          setProfile(nextProfile);
          setState("authenticated");
        }
      } catch {
        if (active) clearAuthentication();
      }
    };
    const onExpired = () => clearAuthentication();
    window.addEventListener("kfl:session-expired", onExpired);
    void load();
    return () => {
      active = false;
      window.removeEventListener("kfl:session-expired", onExpired);
    };
  }, [clearAuthentication]);

  const login = useCallback(async (username: string, password: string) => {
    queryClient.clear();
    await api.post("/p0/auth/login", { username, password });
    try {
      return await refreshProfile();
    } catch (error) {
      try { await api.post("/p0/auth/logout"); } catch { /* session may already be invalid */ }
      clearAuthentication();
      throw error;
    }
  }, [clearAuthentication, queryClient, refreshProfile]);

  const switchRole = useCallback(async (activeRole: string) => {
    try {
      const response = await api.post("/p0/auth/active-role", { active_role: activeRole });
      const nextProfile = response.data as AuthProfile;
      queryClient.clear();
      setProfile(nextProfile);
      setState("authenticated");
      return nextProfile;
    } catch (error) {
      try {
        await refreshProfile();
      } catch {
        clearAuthentication();
      }
      throw error;
    }
  }, [clearAuthentication, queryClient, refreshProfile]);

  const logout = useCallback(async () => {
    await api.post("/p0/auth/logout");
    clearAuthentication();
  }, [clearAuthentication]);

  const value = useMemo<AuthContextValue>(() => ({
    profile,
    state,
    login,
    switchRole,
    logout,
    refreshProfile,
    hasPermission: (permission) => profileHasPermission(profile, permission),
  }), [profile, state, login, switchRole, logout, refreshProfile]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
