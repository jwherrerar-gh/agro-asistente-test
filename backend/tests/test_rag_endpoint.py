from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.application.services.fragmentador_documentos import FragmentadorDocumentos
from app.application.services.servicio_recuperacion_rag import ServicioRecuperacionRag
from app.application.useCases.indexar_conocimiento import IndexarConocimiento
from app.application.useCases.registrar_consulta import RegistrarConsulta
from app.infrastructure.adapters.output.chroma.chroma_vector_store_adapter import (
    ChromaVectorStoreAdapter,
)
from app.infrastructure.adapters.output.embedding.local_lexical_embedding_adapter import (
    LocalLexicalEmbeddingAdapter,
)
from app.infrastructure.adapters.output.mysql.connection import create_mysql_engine
from app.main import app, container

client = TestClient(app)
REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
CONTEXTS_URL = "/api/v1/contexts"
QUERIES_URL = "/api/v1/queries"
INGEST_URL = "/api/v1/knowledge/ingest"
INDEX_URL = "/api/v1/knowledge/index"
QUESTION = "¿Cómo riego la papa en floración para evitar encharcamiento?"


def _register_and_login() -> dict[str, str]:
    payload = {
        "names": "Luis",
        "last_names": "Mamani",
        "email": f"hu06-{uuid4()}@example.com",
        "password": "Password123!",
    }
    register = client.post(REGISTER_URL, json=payload)
    assert register.status_code == 201
    login = client.post(
        LOGIN_URL,
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 200
    return {
        "token": login.json()["access_token"],
        "farmer_id": login.json()["farmer"]["id"],
    }


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_and_select_context(token: str) -> dict:
    created = client.post(
        CONTEXTS_URL,
        json={
            "plot_name": "Parcela RAG",
            "crop": "papa",
            "region": "Huancayo",
            "notes": "Prueba HU-06",
        },
        headers=_auth(token),
    )
    assert created.status_code == 201
    selected = client.post(
        f"{CONTEXTS_URL}/{created.json()['id']}/select",
        headers=_auth(token),
    )
    assert selected.status_code == 200
    return selected.json()


def _payload() -> dict[str, str]:
    unique = str(uuid4())
    return {
        "title": f"Riego de papa {unique}",
        "topic": "papa",
        "content": (
            f"# Riego de papa (material de prueba HU-06)\n\n"
            f"Identificador: {unique}.\n\n"
            "La papa en sierra requiere riegos frecuentes en floración.\n\n"
            "Evitar encharcamiento para reducir riesgo de lancha.\n"
        ),
    }


def _cleanup(source_path: str) -> None:
    knowledge_dir = Path(container.settings.knowledge_dir).resolve()
    path = knowledge_dir / Path(source_path).name
    path.unlink(missing_ok=True)
    path.with_suffix(".meta.json").unlink(missing_ok=True)


def _rewire_isolated_chroma(tmp_path: Path) -> tuple[object, object, object]:
    original = (
        container.puerto_almacen_vectores,
        container.servicio_recuperacion_rag,
        container.puerto_registrar_consulta,
        container.puerto_indexar_conocimiento,
        container.embedding_port,
    )
    embedding = LocalLexicalEmbeddingAdapter(
        dimension=container.settings.embedding_dimension
    )
    store = ChromaVectorStoreAdapter(
        persist_dir=str(tmp_path / "chroma_http"),
        collection_name="agro_knowledge_pmv1_http_test",
    )
    retrieval = ServicioRecuperacionRag(
        embedding_port=embedding,
        almacen_vectores=store,
        top_k=container.settings.rag_top_k,
        similitud_minima=container.settings.rag_min_similarity,
    )
    container.embedding_port = embedding
    container.puerto_almacen_vectores = store
    container.servicio_recuperacion_rag = retrieval
    container.puerto_registrar_consulta = RegistrarConsulta(
        repositorio_consulta=container.puerto_repositorio_consulta,
        generacion_texto=container.puerto_generacion_texto,
        recuperacion_rag=retrieval,
        repositorio_evidencia=container.puerto_repositorio_evidencia,
        clasificar_consulta=container.puerto_clasificar_consulta,
    )
    container.puerto_indexar_conocimiento = IndexarConocimiento(
        repositorio_conocimiento=container.puerto_repositorio_documento_conocimiento,
        embedding_port=embedding,
        almacen_vectores=store,
        fragmentador=FragmentadorDocumentos(max_chars=container.settings.chunk_size),
    )
    return original


def _restore_chroma(original: tuple) -> None:
    (
        container.puerto_almacen_vectores,
        container.servicio_recuperacion_rag,
        container.puerto_registrar_consulta,
        container.puerto_indexar_conocimiento,
        container.embedding_port,
    ) = original


def test_index_knowledge_requires_auth() -> None:
    response = client.post(INDEX_URL)
    assert response.status_code == 401


def test_submit_query_without_results_returns_controlled_answer(tmp_path: Path) -> None:
    original = _rewire_isolated_chroma(tmp_path)
    try:
        user = _register_and_login()
        context = _create_and_select_context(user["token"])
        response = client.post(
            QUERIES_URL,
            json={"text": QUESTION},
            headers=_auth(user["token"]),
        )
        assert response.status_code == 201
        body = response.json()
        assert body["context"]["id"] == context["id"]
        assert body["evidences"] == []
        assert "información suficiente" in body["answer"].lower()
        assert "papa" in body["answer"]
        assert "Huancayo" in body["answer"]
        assert body["generation_method"] == "template"
    finally:
        _restore_chroma(original)


def test_submit_query_with_indexed_knowledge_returns_evidences(tmp_path: Path) -> None:
    original = _rewire_isolated_chroma(tmp_path)
    source_path = ""
    query_id = ""
    try:
        user = _register_and_login()
        _create_and_select_context(user["token"])
        payload = _payload()
        ingested = client.post(INGEST_URL, json=payload, headers=_auth(user["token"]))
        assert ingested.status_code == 201
        source_path = ingested.json()["source_path"]
        document_id = ingested.json()["id"]
        unique_marker = payload["title"].split()[-1]

        indexed = client.post(INDEX_URL, headers=_auth(user["token"]))
        assert indexed.status_code == 200
        body_index = indexed.json()
        assert body_index["indexed_documents"] >= 1
        assert body_index["total_chunks"] >= 1
        assert body_index["collection"]

        response = client.post(
            QUERIES_URL,
            json={"text": f"{QUESTION} {unique_marker}"},
            headers=_auth(user["token"]),
        )
        assert response.status_code == 201
        body = response.json()
        query_id = body["id"]
        assert body["evidences"]
        top = body["evidences"][0]
        assert top["document_id"] == document_id
        assert top["origin_reference"] == source_path
        assert top["excerpt"]
        assert top["similarity_score"] > 0
        assert "base de conocimiento" in body["answer"].lower()
        assert "floración" in body["answer"].lower() or "encharcamiento" in body["answer"].lower()

        engine = create_mysql_engine(container.settings)
        with engine.connect() as connection:
            evidence_row = connection.execute(
                text(
                    "SELECT documento_id, texto_fragmento, titulo_documento FROM evidencias "
                    "WHERE consulta_id = :id ORDER BY id ASC"
                ),
                {"id": query_id},
            ).first()
            response_row = connection.execute(
                text("SELECT metodo_generacion FROM respuestas WHERE consulta_id = :id"),
                {"id": query_id},
            ).first()
        assert evidence_row is not None
        assert str(evidence_row[0]) == str(document_id)
        assert evidence_row[1]
        assert ":chunk:" in evidence_row[1]
        assert evidence_row[2] == payload["title"]
        assert response_row[0] == "template"
    finally:
        if source_path:
            _cleanup(source_path)
        _restore_chroma(original)
