import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listContexts, submitAgriculturalQuery } from "../api/client";
import {
  MENSAJE_CARGA,
  mensajeErrorConsulta,
  referenciaFuente,
  textoRespuesta,
  tituloFuente,
} from "../consulta/presentacion.js";
import AuthFooter from "../components/AuthFooter.jsx";
import AuthenticatedShell from "../components/AuthenticatedShell.jsx";

export default function QueryPage() {
  const [text, setText] = useState("");
  const [selectedContext, setSelectedContext] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingContext, setLoadingContext] = useState(false);
  const [error, setError] = useState("");

  function loadSelectedContext() {
    setLoadingContext(true);
    listContexts()
      .then((response) => {
        const current = response.data.find((item) => item.is_selected) || null;
        setSelectedContext(current);
      })
      .catch(() => {})
      .finally(() => setLoadingContext(false));
  }

  useEffect(() => {
    loadSelectedContext();
  }, []);

  function handleSubmit(event) {
    event.preventDefault();
    if (loading) {
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);

    submitAgriculturalQuery({ text })
      .then((response) => {
        const texto = textoRespuesta(response.data);
        if (!texto) {
          setError("La respuesta no incluye un texto generado. No se muestra una respuesta inventada.");
          return;
        }
        setResult({ ...response.data, answer: texto });
        setText("");
      })
      .catch((err) => {
        setError(mensajeErrorConsulta(err));
      })
      .finally(() => setLoading(false));
  }

  return (
    <AuthenticatedShell>
      <section className="card card-wide">
        <p className="eyebrow">HU-04 / HU-06</p>
        <h1>Consulta agrícola</h1>
        <p className="lead">
          Escribe tu consulta en lenguaje natural. El sistema recupera fragmentos de la
          base de conocimiento (RAG básico) y genera la respuesta con el SLM local
          (Ollama + Qwen2.5), sin fine-tuning.
        </p>

        <section className="context-banner">
          <h2>Contexto actual</h2>
          {loadingContext && <p>Cargando contexto seleccionado…</p>}
          {!loadingContext && selectedContext && (
            <p>
              <strong>{selectedContext.crop}</strong> · {selectedContext.region}
              {selectedContext.plot_name ? ` · ${selectedContext.plot_name}` : ""}
            </p>
          )}
          {!loadingContext && !selectedContext && (
            <p>
              No hay un contexto agrícola seleccionado.{" "}
              <Link to="/context">Crear o seleccionar contexto</Link>
            </p>
          )}
        </section>

        <section className="query-box">
          <h2>¿Qué deseas consultar?</h2>
          <form className="form" onSubmit={handleSubmit}>
            <label>
              Consulta
              <textarea
                name="text"
                value={text}
                onChange={(event) => setText(event.target.value)}
                required
                disabled={loading}
                maxLength={2000}
                placeholder="¿Qué puedo hacer para mejorar el cultivo de papa?"
              />
            </label>
            <button type="submit" disabled={loading}>
              {loading ? "Consultando…" : "Consultar"}
            </button>
          </form>
        </section>

        {loading && (
          <p className="status" role="status">
            {MENSAJE_CARGA}
          </p>
        )}
        {error && (
          <div className="status status-error" role="alert">
            <p>{error}</p>
          </div>
        )}

        {!loading && result && (
          <>
            <section className="answer-panel" aria-live="polite">
              <h2>Respuesta</h2>
              <p className="answer-text">{result.answer}</p>
              <dl>
                <dt>Consulta</dt>
                <dd>{result.text}</dd>
                <dt>Contexto</dt>
                <dd>
                  {result.context.crop} · {result.context.region}
                  {result.context.plot_name ? ` · ${result.context.plot_name}` : ""}
                </dd>
                <dt>Método</dt>
                <dd>
                  {result.generation_method === "ollama"
                    ? "Ollama / Qwen2.5 (PMV1)"
                    : result.generation_method === "template"
                    ? "Plantilla (pruebas / fallback explícito)"
                    : result.generation_method}
                </dd>
                <dt>Categoría</dt>
                <dd>
                  {result.classification?.available
                    ? result.classification.category
                    : "No disponible"}
                  {result.classification?.abstained ? " (abstención experimental)" : ""}
                  {result.classification && !result.classification.available && result.classification.error
                    ? ` — ${result.classification.error}`
                    : ""}
                </dd>
                <dt>Fecha</dt>
                <dd>{result.created_at}</dd>
              </dl>
            </section>

            <section className="evidence-panel">
              <h2>Evidencias</h2>
              {(!result.evidences || result.evidences.length === 0) && (
                <p className="lead">
                  No se recuperó evidencia. No se encontró información suficiente en la
                  base de conocimiento.
                </p>
              )}
              {result.evidences && result.evidences.length > 0 && (
                <ul className="context-list">
                  {result.evidences.map((item) => {
                    const referencia = referenciaFuente(item);
                    return (
                      <li key={`${item.chunk_id}-${item.rank_order}`}>
                        <p className="evidence-title">{tituloFuente(item)}</p>
                        <p>{item.excerpt}</p>
                        <p className="document-meta">
                          Relevancia: {Number(item.similarity_score).toFixed(3)}
                          {" · "}
                          Documento: {item.document_id}
                        </p>
                        <p className="document-meta">
                          {referencia.enlace ? (
                            <a href={referencia.enlace} rel="noopener noreferrer" target="_blank">
                              {referencia.texto}
                            </a>
                          ) : (
                            referencia.texto
                          )}
                        </p>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          </>
        )}

        <AuthFooter />
      </section>
    </AuthenticatedShell>
  );
}
