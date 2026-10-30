import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { urlBaseApi } from "../api/baseUrl.js";
import { getHealth } from "../api/client";
import PublicShell from "../components/PublicShell.jsx";

export default function HomePage() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getHealth()
      .then((response) => {
        setHealth(response.data);
        setError("");
      })
      .catch(() => {
        const base = urlBaseApi(import.meta.env);
        const destino = base ? `${base}/health` : "/health";
        setError(`No se pudo conectar con el backend en ${destino}`);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <PublicShell>
      <section className="card">
        <h1>Agro-Asistente</h1>
        <p className="lead">Plataforma de asistencia técnica agrícola</p>
        <p className="lead">
          Permite registrar un contexto de cultivo, consultar asistencia técnica
          y revisar la base de conocimiento disponible.
        </p>

        <div className="hero-actions">
          <Link className="button" to="/login">Iniciar sesión</Link>
          <Link className="button button-secondary" to="/register">Crear cuenta</Link>
        </div>

        <div className={`status tech-status ${error ? "status-error" : "status-ok"}`}>
          {loading && <p>Comprobando GET /health…</p>}
          {!loading && error && <p>{error}</p>}
          {!loading && health && (
            <dl>
              <dt>Estado</dt>
              <dd>{health.status}</dd>
              <dt>Servicio</dt>
              <dd>{health.service}</dd>
              <dt>Fase</dt>
              <dd>{health.phase}</dd>
              <dt>Arquitectura</dt>
              <dd>{health.architecture}</dd>
              <dt>MySQL</dt>
              <dd>{health.mysql}</dd>
            </dl>
          )}
        </div>
      </section>
    </PublicShell>
  );
}
