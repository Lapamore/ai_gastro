import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';
const authApi = axios.create({
    baseURL: API_BASE_URL,
    withCredentials: true,
});

export interface AuthUser {
    id: string;
    display_name: string;
    email: string | null;
    avatar_url: string | null;
}

interface AuthPayload {
    access_token: string;
    token_type: string;
    expires_in: number;
    user: AuthUser;
}

interface AuthContextType {
    user: AuthUser | null;
    token: string | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    login: (email: string, password: string) => Promise<void>;
    register: (username: string, email: string, password: string) => Promise<void>;
    refreshSession: () => Promise<string | null>;
    logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<AuthUser | null>(null);
    const [token, setToken] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const refreshPromiseRef = useRef<Promise<string | null> | null>(null);

    const applyAuthPayload = useCallback((payload: AuthPayload): string => {
        setToken(payload.access_token);
        setUser(payload.user);
        return payload.access_token;
    }, []);

    const clearAuth = useCallback(() => {
        setToken(null);
        setUser(null);
    }, []);

    const refreshSession = useCallback(async (): Promise<string | null> => {
        if (refreshPromiseRef.current) {
            return refreshPromiseRef.current;
        }

        const refreshPromise = authApi
            .post<AuthPayload>('/auth/refresh')
            .then((res) => applyAuthPayload(res.data))
            .catch(() => {
                clearAuth();
                return null;
            })
            .finally(() => {
                refreshPromiseRef.current = null;
            });

        refreshPromiseRef.current = refreshPromise;
        return refreshPromise;
    }, [applyAuthPayload, clearAuth]);

    useEffect(() => {
        refreshSession().finally(() => {
            setIsLoading(false);
        });
    }, [refreshSession]);

    const login = useCallback(async (email: string, password: string) => {
        const res = await authApi.post<AuthPayload>('/auth/login', { email, password });
        applyAuthPayload(res.data);
    }, [applyAuthPayload]);

    const register = useCallback(async (username: string, email: string, password: string) => {
        const res = await authApi.post<AuthPayload>('/auth/register', { username, email, password });
        applyAuthPayload(res.data);
    }, [applyAuthPayload]);

    const logout = useCallback(async () => {
        try {
            await authApi.post('/auth/logout');
        } catch {
            // Если сервер недоступен, локально всё равно чистим сессию.
        }
        clearAuth();
    }, [clearAuth]);

    return (
        <AuthContext.Provider value={{
            user,
            token,
            isAuthenticated: !!token && !!user,
            isLoading,
            login,
            register,
            refreshSession,
            logout,
        }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth(): AuthContextType {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within AuthProvider');
    }
    return context;
}
