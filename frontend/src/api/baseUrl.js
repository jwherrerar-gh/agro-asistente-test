export function urlBaseApi(viteEnv) {
  const configured = viteEnv?.VITE_API_BASE_URL;
  if (typeof configured !== "string") {
    return "";
  }
  return configured.trim().replace(/\/+$/, "");
}
