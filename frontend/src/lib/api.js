import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

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
