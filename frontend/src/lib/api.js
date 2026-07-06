import axios from "axios";

const CONFIGURED_BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
const PRODUCTION_BACKEND_URL = "https://syncoop-api.onrender.com";
const isBrowser = typeof window !== "undefined";
const isPublicHttps =
  isBrowser &&
  window.location.protocol === "https:" &&
  !["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
const isLocalBackend = /localhost|127\.0\.0\.1/.test(CONFIGURED_BACKEND_URL);

const BACKEND_URL =
  isPublicHttps && isLocalBackend
    ? PRODUCTION_BACKEND_URL
    : CONFIGURED_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;
export { BACKEND_URL };

if (isPublicHttps && isLocalBackend) {
  // Helps catch production builds that were created with a local API URL.
  console.warn("SynCoop frontend ignored a localhost backend URL on a public HTTPS domain.");
}

const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

export default api;

export const fmtRp = (n) =>
  "Rp" + (Number(n) || 0).toLocaleString("id-ID", { maximumFractionDigits: 0 });

export const ROLE_LABELS = {
  NELAYAN: "Nelayan / Anggota",
  PETUGAS_LAPANG: "Petugas Lapang",
  ADMIN: "Admin Koperasi",
  PETUGAS_DINAS: "Petugas Kab/Kota",
};
