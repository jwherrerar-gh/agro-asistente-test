export const MENSAJE_CARGA =
  "Generando la respuesta. Todavía no hay un texto.";

export const FUENTE_SIN_TITULO = "Fuente sin título disponible";

export const REFERENCIA_NO_DISPONIBLE = "Referencia original no disponible";

const RUTA_LOCAL = /^knowledge\/[A-Za-z0-9][A-Za-z0-9._-]*\.md$/;

export function referenciaFuente(evidencia) {
  const valor =
    typeof evidencia?.origin_reference === "string" ? evidencia.origin_reference.trim() : "";
  if (valor && !valor.includes("..") && RUTA_LOCAL.test(valor)) {
    return { texto: `Archivo local: ${valor}`, enlace: null };
  }
  if (enlaceHttpSeguro(valor)) {
    return { texto: valor, enlace: valor };
  }
  return { texto: REFERENCIA_NO_DISPONIBLE, enlace: null };
}

function enlaceHttpSeguro(valor) {
  if (!valor.startsWith("http://") && !valor.startsWith("https://")) {
    return false;
  }
  let url;
  try {
    url = new URL(valor);
  } catch {
    return false;
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    return false;
  }
  if (!url.hostname || url.username || url.password) {
    return false;
  }
  return true;
}

export function tituloFuente(evidencia) {
  const titulo = evidencia?.document_title;
  if (typeof titulo !== "string" || titulo.trim() === "") {
    return FUENTE_SIN_TITULO;
  }
  return titulo.trim();
}

export function textoRespuesta(datos) {
  if (!datos || typeof datos.answer !== "string" || datos.answer.trim() === "") {
    return null;
  }
  return datos.answer;
}

export function mensajeErrorConsulta(error) {
  if (!error?.response) {
    return "No se pudo comunicar con el servidor. No se muestra una respuesta generada.";
  }
  const status = error.response.status;
  const detail = error.response.data?.detail;
  if (status === 401) {
    return "La sesión no es válida o venció. No se muestra una respuesta generada.";
  }
  if (status === 409) {
    return typeof detail === "string"
      ? detail
      : "Debes seleccionar un contexto agrícola antes de consultar. No se muestra una respuesta generada.";
  }
  if (status === 400 || status === 422) {
    return typeof detail === "string"
      ? `${detail} No se muestra una respuesta generada.`
      : "Revisa el texto de la consulta. No puede estar vacío ni ser demasiado largo. No se muestra una respuesta generada.";
  }
  if (status === 503) {
    return typeof detail === "string"
      ? `${detail} No se muestra una respuesta generada.`
      : "El servicio de generación no está disponible. No se muestra una respuesta generada.";
  }
  return typeof detail === "string"
    ? `${detail} No se muestra una respuesta generada.`
    : "No se pudo enviar la consulta. No se muestra una respuesta generada.";
}
