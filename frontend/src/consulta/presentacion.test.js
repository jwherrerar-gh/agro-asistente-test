import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
  FUENTE_SIN_TITULO,
  MENSAJE_CARGA,
  REFERENCIA_NO_DISPONIBLE,
  mensajeErrorConsulta,
  referenciaFuente,
  textoRespuesta,
  tituloFuente,
} from "./presentacion.js";

const respuesta = {
  answer: "El riego debe evitar el encharcamiento.\nNo agregues más agua.",
  text: "¿Cómo riego la papa?",
  generation_method: "ollama",
};

test("una respuesta satisfactoria conserva tildes y saltos de línea", () => {
  const texto = "La región de Junín necesita riego.\nEvita el encharcamiento.";
  assert.equal(textoRespuesta({ answer: texto }), texto);
  assert.match(textoRespuesta(respuesta), /encharcamiento\.\nNo agregues/);
});

test("un texto vacío o ausente no se reemplaza por una respuesta inventada", () => {
  assert.equal(textoRespuesta({ answer: "   " }), null);
  assert.equal(textoRespuesta({}), null);
  assert.equal(textoRespuesta(null), null);
});

test("los errores no fabrican una respuesta y el 503 se distingue de la carga", () => {
  assert.match(mensajeErrorConsulta({ response: { status: 503, data: { detail: "Ollama no está disponible." } } }), /Ollama no está disponible/);
  assert.match(mensajeErrorConsulta({ response: { status: 422, data: {} } }), /No se muestra una respuesta generada/);
  assert.match(mensajeErrorConsulta({ response: { status: 401, data: {} } }), /sesión/i);
  assert.match(mensajeErrorConsulta({}), /comunicar con el servidor/);
  assert.doesNotMatch(mensajeErrorConsulta({ response: { status: 503, data: {} } }), /encharcamiento/);
  assert.match(MENSAJE_CARGA, /Todavía no hay un texto/);
});

test("cada fuente muestra su título y un texto neutro si no lo tiene", () => {
  const fuentes = [
    { document_title: "Prueba de riego de papa", excerpt: "Vigilar la humedad.", similarity_score: 0.4 },
    { document_title: "Manejo de heladas en el cultivo de papa", excerpt: "Vigilar la temperatura.", similarity_score: 0.41 },
  ];
  assert.deepEqual(fuentes.map(tituloFuente), [
    "Prueba de riego de papa",
    "Manejo de heladas en el cultivo de papa",
  ]);
  assert.equal(tituloFuente({ document_title: "" }), FUENTE_SIN_TITULO);
  assert.equal(tituloFuente({ document_title: "   " }), FUENTE_SIN_TITULO);
  assert.equal(tituloFuente({}), FUENTE_SIN_TITULO);
  assert.equal(tituloFuente(null), FUENTE_SIN_TITULO);
  assert.equal(FUENTE_SIN_TITULO, "Fuente sin título disponible");
});

test("la referencia local no es un enlace y la ausente o insegura queda neutra", () => {
  const local = referenciaFuente({
    origin_reference: "knowledge/7019602d-f4ac-4153-8cdc-acd18a03fa3a.md",
  });
  assert.equal(local.enlace, null);
  assert.match(local.texto, /Archivo local: knowledge\/7019602d-f4ac-4153-8cdc-acd18a03fa3a\.md/);

  const web = referenciaFuente({ origin_reference: "https://ejemplo.gob.pe/guia" });
  assert.equal(web.enlace, "https://ejemplo.gob.pe/guia");
  assert.equal(web.texto, "https://ejemplo.gob.pe/guia");

  for (const origen of ["", "   ", "javascript:alert(1)", "file:///C:/secreto.md", "data:text/html,hola"]) {
    const referencia = referenciaFuente({ origin_reference: origen });
    assert.equal(referencia.enlace, null);
    assert.equal(referencia.texto, REFERENCIA_NO_DISPONIBLE);
  }
  assert.equal(referenciaFuente({}).texto, REFERENCIA_NO_DISPONIBLE);
  assert.equal(REFERENCIA_NO_DISPONIBLE, "Referencia original no disponible");
});

test("la página separa las fuentes de la respuesta y conserva extracto y similitud", () => {
  const pagina = readFileSync(new URL("../pages/QueryPage.jsx", import.meta.url), "utf8");
  const respuesta = pagina.indexOf('className="answer-text"');
  const evidencias = pagina.indexOf('className="evidence-panel"');
  assert.ok(respuesta !== -1 && evidencias > respuesta);
  assert.match(pagina, /tituloFuente\(item\)/);
  assert.match(pagina, /referenciaFuente\(item\)/);
  assert.match(pagina, /href=\{referencia\.enlace\}/);
  assert.match(pagina, /rel="noopener noreferrer"/);
  assert.match(pagina, /\{item\.excerpt\}/);
  assert.match(pagina, /similarity_score/);
  assert.match(pagina, /No se recuperó evidencia/);
  assert.match(pagina, /\{!loading && result &&/);
  assert.doesNotMatch(pagina, /Documento agrícola/);
});

test("la página limpia el resultado anterior y muestra el texto sin alterar", () => {
  const pagina = readFileSync(new URL("../pages/QueryPage.jsx", import.meta.url), "utf8");
  const inicio = pagina.indexOf("function handleSubmit");
  const peticion = pagina.indexOf("submitAgriculturalQuery", inicio);
  const limpia = pagina.indexOf("setResult(null)", inicio);
  assert.ok(limpia !== -1 && limpia < peticion);
  assert.match(pagina, /textoRespuesta\(response\.data\)/);
  assert.match(pagina, /MENSAJE_CARGA/);
  assert.match(pagina, /className="answer-text"/);
  assert.doesNotMatch(pagina, /predictAgriculturalRisk|\/api\/v1\/riesgo/);
});
