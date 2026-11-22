import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import * as SecureStore from 'expo-secure-store';
import * as Api from './ApiService';
import { clearDrafts } from './drafts';

const TOKEN_KEY = 'sakitkepala_token';
const USER_KEY = 'sakitkepala_user';

const AuthContext = createContext(null);

async function saveSession(token, user) {
  await SecureStore.setItemAsync(TOKEN_KEY, token);
  await SecureStore.setItemAsync(USER_KEY, JSON.stringify(user));
}

async function clearStoredSession() {
  await Promise.all([
    SecureStore.deleteItemAsync(TOKEN_KEY).catch(() => {}),
    SecureStore.deleteItemAsync(USER_KEY).catch(() => {}),
  ]);
}

export function AuthProvider({ children }) {
  // status: 'restoring' (layar Pemulihan) | 'signedOut' | 'signedIn'
  const [status, setStatus] = useState('restoring');
  const [user, setUser] = useState(null);
  const [notice, setNotice] = useState(null);

  const expire = useCallback(() => {
    Api.setToken(null);
    clearStoredSession();
    setUser(null);
    setNotice('Sesi berakhir, silakan masuk lagi. Draft intisarimu tetap tersimpan.');
    setStatus('signedOut');
  }, []);

  useEffect(() => {
    Api.setUnauthorizedHandler(expire);
    return () => Api.setUnauthorizedHandler(null);
  }, [expire]);

  // Pemulihan sesi saat aplikasi dibuka ulang: token diperiksa lewat /auth/me.
  useEffect(() => {
    let alive = true;
    (async () => {
      let token = null;
      try {
        token = await SecureStore.getItemAsync(TOKEN_KEY);
      } catch {
        token = null;
      }
      if (!token) {
        if (alive) setStatus('signedOut');
        return;
      }
      Api.setToken(token);
      try {
        const me = await Api.getMe();
        await SecureStore.setItemAsync(USER_KEY, JSON.stringify(me));
        if (alive) {
          setUser(me);
          setStatus('signedIn');
        }
      } catch (err) {
        if (!alive) return;
        if (err.status === 401) return; // expire() sudah dipanggil oleh ApiService
        // Server tidak terjangkau: pakai profil terakhir, layar menampilkan error + coba lagi.
        let cached = null;
        try {
          cached = JSON.parse((await SecureStore.getItemAsync(USER_KEY)) || 'null');
        } catch {
          cached = null;
        }
        setUser(cached);
        setStatus('signedIn');
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const login = useCallback(async (email, password) => {
    const { access_token: token } = await Api.login(email.trim(), password);
    Api.setToken(token);
    try {
      const me = await Api.getMe();
      await saveSession(token, me);
      setUser(me);
      setNotice(null);
      setStatus('signedIn');
    } catch (err) {
      Api.setToken(null);
      throw err;
    }
  }, []);

  const logout = useCallback(async () => {
    Api.setToken(null);
    clearDrafts();
    await clearStoredSession();
    setUser(null);
    setNotice(null);
    setStatus('signedOut');
  }, []);

  const refreshUser = useCallback(async () => {
    const me = await Api.getMe();
    setUser(me);
    SecureStore.setItemAsync(USER_KEY, JSON.stringify(me)).catch(() => {});
    return me;
  }, []);

  const value = useMemo(
    () => ({ status, user, notice, clearNotice: () => setNotice(null), login, logout, refreshUser }),
    [status, user, notice, login, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth harus dipakai di dalam AuthProvider');
  return ctx;
}
