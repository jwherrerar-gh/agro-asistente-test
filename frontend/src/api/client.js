import axios from "axios";
import { urlBaseApi } from "./baseUrl.js";

export const api = axios.create({
  baseURL: urlBaseApi(import.meta.env),
  timeout: 5000,
});

const ACCESS_TOKEN_KEY = "agro_asistente_access_token";
const PUBLIC_AUTH_PATHS = ["/api/v1/auth/login", "/api/v1/auth/register"];

export function saveAccessToken(token) {
  if (typeof token !== "string" || !token.trim()) {
    return;
  }
  window.localStorage.setItem(ACCESS_TOKEN_KEY, token.trim());
}

export function getAccessToken() {
  const token = window.localStorage.getItem(ACCESS_TOKEN_KEY);
  if (!token || token === "undefined" || token === "null") {
    return null;
  }
  return token;
}

export function clearAccessToken() {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
}

const SESSION_FARMER_KEY = "agro_asistente_session_farmer";

export function saveSessionFarmer(farmer) {
  const names = typeof farmer?.names === "string" ? farmer.names.trim() : "";
  const lastNames = typeof farmer?.last_names === "string" ? farmer.last_names.trim() : "";
  const email = typeof farmer?.email === "string" ? farmer.email.trim() : "";
  const displayName = [names, lastNames].filter(Boolean).join(" ") || email;
  if (!displayName) {
    return;
  }
  window.localStorage.setItem(SESSION_FARMER_KEY, displayName);
}

export function getSessionFarmer() {
  return window.localStorage.getItem(SESSION_FARMER_KEY);
}

export function clearSession() {
  clearAccessToken();
  window.localStorage.removeItem(SESSION_FARMER_KEY);
}

function isPublicAuthRequest(config) {
  const url = `${config.baseURL || ""}${config.url || ""}`;
  return PUBLIC_AUTH_PATHS.some((path) => url.includes(path));
}

api.interceptors.request.use((config) => {
  if (isPublicAuthRequest(config)) {
    return config;
  }
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !isPublicAuthRequest(error.config || {})) {
      clearSession();
      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
    }
    return Promise.reject(error);
  },
);

export function getHealth() {
  return api.get("/health");
}

export function registerFarmer(payload) {
  return api.post("/api/v1/auth/register", payload);
}

export function loginFarmer(payload) {
  return api.post("/api/v1/auth/login", payload);
}

export function listContexts() {
  return api.get("/api/v1/contexts");
}

export function createAgriculturalContext(payload) {
  return api.post("/api/v1/contexts", payload);
}

export function selectContext(contextId) {
  return api.post(`/api/v1/contexts/${contextId}/select`);
}

export function submitAgriculturalQuery(payload) {
  return api.post("/api/v1/queries", payload, { timeout: 120000 });
}

export function predictAgriculturalRisk(payload) {
  return api.post("/api/v1/riesgo", payload, { timeout: 120000 });
}

export function listKnowledgeDocuments() {
  return api.get("/api/v1/knowledge/documents");
}

export function ingestKnowledge(payload) {
  return api.post("/api/v1/knowledge/ingest", payload);
}
