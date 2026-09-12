import axios from "axios";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
export const MEDIA = `${process.env.REACT_APP_BACKEND_URL}`;

export const api = axios.create({ baseURL: API, withCredentials: true });

// Any 401 outside the auth endpoints bounces the browser back to the login screen
// (skipped when already on /login, otherwise the channel fetch would reload-loop the login page)
api.interceptors.response.use(
  (r) => r,
  (error) => {
    const url = String(error?.config?.url || "");
    const onLogin = window.location.pathname === "/login";
    if (error?.response?.status === 401 && !url.includes("/auth/") && !onLogin) {
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

export function usePoll(url, ms = 4000) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const urlRef = useRef(url);
  urlRef.current = url;

  const load = useCallback(async () => {
    try {
      const r = await api.get(urlRef.current);
      setData(r.data);
      setError(null);
    } catch (e) {
      setError(e);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, ms);
    return () => clearInterval(t);
  }, [load, ms, url]);

  return [data, load, error];
}

export const ChannelContext = createContext({ channels: [], selected: "all", setSelected: () => {} });
export const useChannels = () => useContext(ChannelContext);

export const ChannelProvider = ({ children }) => {
  const [channels, setChannels] = useState([]);
  const [selected, setSelected] = useState(localStorage.getItem("sf_channel") || "all");

  useEffect(() => {
    api.get("/channels").then((r) => setChannels(r.data)).catch(() => {});
  }, []);

  const setSel = (v) => {
    setSelected(v);
    localStorage.setItem("sf_channel", v);
  };

  return (
    <ChannelContext.Provider value={{ channels, selected, setSelected: setSel }}>
      {children}
    </ChannelContext.Provider>
  );
};

export const channelQ = (selected) => (selected && selected !== "all" ? `?channel_id=${selected}` : "");
