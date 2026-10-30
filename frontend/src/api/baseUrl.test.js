import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { urlBaseApi } from "./baseUrl.js";

test("sin variable la base queda vacía y no apunta a una dirección fija", () => {
  assert.equal(urlBaseApi({}), "");
  assert.equal(urlBaseApi({ VITE_API_BASE_URL: "   " }), "");
  assert.equal(urlBaseApi(undefined), "");
});

test("la URL configurada se usa sin barra final", () => {
  assert.equal(
    urlBaseApi({ VITE_API_BASE_URL: "https://api.ejemplo.test/" }),
    "https://api.ejemplo.test",
  );
});

test("el cliente y el proxy local no fijan el backend de producción", () => {
  const cliente = readFileSync(new URL("./client.js", import.meta.url), "utf8");
  const vite = readFileSync(new URL("../../vite.config.js", import.meta.url), "utf8");
  assert.match(cliente, /urlBaseApi\(import\.meta\.env\)/);
  assert.doesNotMatch(cliente, /127\.0\.0\.1:8000/);
  assert.match(vite, /\/health/);
  assert.match(vite, /127\.0\.0\.1:8000/);
});
