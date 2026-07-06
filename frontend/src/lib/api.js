import axios from "axios";

const BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
export const API = `${BACKEND_URL}/api`;
export { BACKEND_URL };

if (
  typeof window !== "undefined" &&
  window.location.protocol === "https:" &&
  /localhost|127\.0\.0\.1/.test(BACKEND_URL)
) {
  // Helps catch production builds that were created with a local API URL.
  console.warn("SynCoop frontend is using a localhost backend URL on a public HTTPS domain.");
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
