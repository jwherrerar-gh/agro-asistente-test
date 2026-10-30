from pathlib import Path

import httpx
import pytest

from app.domain.exceptions import ErrorGeneracionTexto
from app.domain.ports.output.text_generation_port import PasajeRecuperado, PuertoGeneracionTexto
from app.infrastructure.adapters.output.generation.adaptador_generacion_gemini import (
    AdaptadorGeneracionGemini,
)
from app.infrastructure.adapters.output.generation.adaptador_generacion_ollama import (
    AdaptadorGeneracionOllama,
    construir_prompt_agricola,
)
from app.infrastructure.adapters.output.generation.adaptador_generacion_plantilla import (
    AdaptadorGeneracionPlantilla,
)
from app.infrastructure.composition import CompositionRoot
from app.infrastructure.config.settings import Settings


class _RespuestaFalsa:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, object]:
        return self._payload


class _ClienteFalso:
    def __init__(self, respuesta: _RespuestaFalsa | Exception) -> None:
        self._respuesta = respuesta
        self.llamadas: list[tuple[str, dict[str, object]]] = []

    def post(self, url: str, json: dict[str, object], timeout: int | None = None) -> _RespuestaFalsa:
        self.llamadas.append((url, json))
        if isinstance(self._respuesta, Exception):
            raise self._respuesta
        return self._respuesta


MODELO_CONFIGURADO = "modelo-configurado-via-env"


def _adaptador(
    cliente: _ClienteFalso,
    modelo: str = MODELO_CONFIGURADO,
) -> AdaptadorGeneracionOllama:
    return AdaptadorGeneracionOllama(
        base_url="http://127.0.0.1:11434",
        model=modelo,
        timeout_seconds=5,
        cliente_http=cliente,
    )


def test_prompt_incluye_consulta_contexto_y_fragmentos() -> None:
    prompt = construir_prompt_agricola(
        texto_consulta="¿Cómo riego la papa en floración?",
        cultivo="papa",
        region="Huancayo",
        pasajes=[
            PasajeRecuperado(
                titulo="Riego de papa",
                extracto="La papa en sierra requiere riegos frecuentes en floración.",
            )
        ],
    )
    assert "papa" in prompt
    assert "Huancayo" in prompt
    assert "¿Cómo riego la papa en floración?" in prompt
    assert "Riego de papa" in prompt
    assert "floración" in prompt
    assert "español" in prompt.lower()


def test_prompt_sin_fragmentos_pide_no_inventar() -> None:
    prompt = construir_prompt_agricola("¿Qué hago?", "papa", "Junín", pasajes=[])
    assert "no hay información suficiente" in prompt.lower() or "ningún fragmento" in prompt.lower()


def test_ollama_adapter_returns_model_text_with_method_ollama() -> None:
    cliente = _ClienteFalso(
        _RespuestaFalsa(200, {"response": "Riega con frecuencia y evita el encharcamiento."})
    )
    generated = _adaptador(cliente).generar(
        texto_consulta="¿Cómo riego la papa?",
        cultivo="papa",
        region="Huancayo",
        pasajes=[PasajeRecuperado(titulo="Riego", extracto="Riegos frecuentes en floración.")],
    )
    assert generated.metodo_generacion == "ollama"
    assert "encharcamiento" in generated.texto_respuesta
    assert generated.metodo_generacion != "template"
    url, payload = cliente.llamadas[0]
    assert url.endswith("/api/generate")
    assert payload["model"] == MODELO_CONFIGURADO
    assert payload["stream"] is False
    assert payload["options"]["temperature"] == 0.2
    assert "Junín" in str(payload["system"])
    assert "papa" in str(payload["prompt"])
    assert "floración" in str(payload["prompt"])


def test_gemini_adapter_returns_model_text_with_method_gemini() -> None:
    cliente = _ClienteFalso(
        _RespuestaFalsa(
            200,
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "Riega con frecuencia y evita el encharcamiento."}]
                        }
                    }
                ]
            },
        )
    )
    adapter = AdaptadorGeneracionGemini(
        api_key="test-key",
        model="gemini-3.8-flash",
        timeout_seconds=5,
        cliente_http=cliente,
    )
    generated = adapter.generar(
        texto_consulta="¿Cómo riego la papa?",
        cultivo="papa",
        region="Huancayo",
        pasajes=[PasajeRecuperado(titulo="Riego", extracto="Riegos frecuentes en floración.")],
    )
    assert generated.metodo_generacion == "gemini"
    assert "encharcamiento" in generated.texto_respuesta
    url, payload = cliente.llamadas[0]
    assert "generateContent" in url
    assert payload["generationConfig"]["temperature"] == 0.2
    assert "papa" in str(payload["contents"][0]["parts"][0]["text"])


def test_ollama_connection_error_is_controlled() -> None:
    request = httpx.Request("POST", "http://127.0.0.1:11434/api/generate")
    cliente = _ClienteFalso(httpx.ConnectError("connection refused", request=request))
    with pytest.raises(ErrorGeneracionTexto, match="no está disponible"):
        _adaptador(cliente).generar("¿Cómo riego?", "papa", "Huancayo")


def test_ollama_timeout_is_controlled() -> None:
    request = httpx.Request("POST", "http://127.0.0.1:11434/api/generate")
    cliente = _ClienteFalso(httpx.TimeoutException("timed out", request=request))
    with pytest.raises(ErrorGeneracionTexto, match="tiempo de espera"):
        _adaptador(cliente).generar("¿Cómo riego?", "papa", "Huancayo")


def test_ollama_sends_whatever_model_was_configured() -> None:
    cliente = _ClienteFalso(_RespuestaFalsa(200, {"response": "Respuesta de prueba."}))
    _adaptador(cliente, modelo="otro-tag-local").generar("¿Cómo riego?", "papa", "Huancayo")
    _url, payload = cliente.llamadas[0]
    assert payload["model"] == "otro-tag-local"


def test_ollama_model_missing_is_controlled() -> None:
    cliente = _ClienteFalso(
        _RespuestaFalsa(404, {"error": f"model '{MODELO_CONFIGURADO}' not found"})
    )
    with pytest.raises(ErrorGeneracionTexto, match="no está disponible"):
        _adaptador(cliente).generar("¿Cómo riego?", "papa", "Huancayo")


def test_ollama_http_error_is_controlled() -> None:
    cliente = _ClienteFalso(_RespuestaFalsa(500, {"error": "internal server error"}))
    with pytest.raises(ErrorGeneracionTexto, match="internal server error"):
        _adaptador(cliente).generar("¿Cómo riego?", "papa", "Huancayo")


def test_ollama_empty_response_is_controlled() -> None:
    cliente = _ClienteFalso(_RespuestaFalsa(200, {"response": "  "}))
    with pytest.raises(ErrorGeneracionTexto, match="vacío"):
        _adaptador(cliente).generar("¿Cómo riego?", "papa", "Huancayo")


def test_ollama_invalid_json_is_controlled() -> None:
    class _RespuestaSinJson:
        status_code = 200

        def json(self) -> dict[str, object]:
            raise ValueError("Expecting value")

    cliente = _ClienteFalso(_RespuestaSinJson())  # type: ignore[arg-type]
    with pytest.raises(ErrorGeneracionTexto, match="formato inválido"):
        _adaptador(cliente).generar("¿Cómo riego?", "papa", "Huancayo")


def test_ollama_non_object_json_is_controlled() -> None:
    class _RespuestaLista:
        status_code = 200

        def json(self) -> list[str]:
            return ["texto"]

    cliente = _ClienteFalso(_RespuestaLista())  # type: ignore[arg-type]
    with pytest.raises(ErrorGeneracionTexto, match="formato inválido"):
        _adaptador(cliente).generar("¿Cómo riego?", "papa", "Huancayo")


def test_composition_wires_ollama_from_settings() -> None:
    settings = Settings(
        _env_file=None,
        generation_provider="ollama",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model=MODELO_CONFIGURADO,
        ollama_timeout_seconds=12,
    )
    container = CompositionRoot(settings)
    assert isinstance(container.puerto_generacion_texto, PuertoGeneracionTexto)
    adapter = container.puerto_generacion_texto
    assert isinstance(adapter, AdaptadorGeneracionOllama)
    assert adapter._model == MODELO_CONFIGURADO
    assert adapter._base_url == "http://127.0.0.1:11434"
    assert adapter._timeout_seconds == 12


def test_composition_can_wire_template_fallback() -> None:
    container = CompositionRoot(Settings(_env_file=None, generation_provider="template"))
    assert isinstance(container.puerto_generacion_texto, AdaptadorGeneracionPlantilla)


def test_composition_wires_gemini_from_settings() -> None:
    settings = Settings(
        _env_file=None,
        generation_provider="gemini",
        gemini_api_key="test-key",
        gemini_model="gemini-3.8-flash",
        gemini_timeout_seconds=15,
    )
    container = CompositionRoot(settings)
    adapter = container.puerto_generacion_texto
    assert isinstance(adapter, AdaptadorGeneracionGemini)
    assert adapter._model == "gemini-3.8-flash"
    assert adapter._timeout_seconds == 15


def test_adapter_source_does_not_hardcode_qwen_tag() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "infrastructure"
        / "adapters"
        / "output"
        / "generation"
        / "adaptador_generacion_ollama.py"
    ).read_text(encoding="utf-8").lower()
    assert "qwen" not in source
    assert "1.8b" not in source
    assert "1.5b" not in source
    backend = Path(__file__).resolve().parents[1]
    for relative in (
        "app/domain",
        "app/application/useCases/registrar_consulta.py",
    ):
        target = backend / relative
        files = [target] if target.is_file() else list(target.rglob("*.py"))
        for python_file in files:
            lowered = python_file.read_text(encoding="utf-8").lower()
            assert "import ollama" not in lowered
            assert "from ollama" not in lowered
            assert "11434" not in python_file.read_text(encoding="utf-8")


def test_real_http_call_without_ollama_is_controlled_error() -> None:
    """Llama de verdad a la API HTTP. No finge éxito de Qwen."""
    adapter = AdaptadorGeneracionOllama(
        base_url="http://127.0.0.1:9",
        model=MODELO_CONFIGURADO,
        timeout_seconds=1,
    )
    with pytest.raises(ErrorGeneracionTexto, match="tiempo de espera|no está disponible"):
        adapter.generar("¿Cómo riego?", "papa", "Huancayo")


def _integracion_ollama_habilitada() -> bool:
    valor = (
        __import__("os").environ.get("RUN_OLLAMA_INTEGRATION_TESTS")
        or __import__("os").environ.get("OLLAMA_INTEGRATION")
        or ""
    ).strip().lower()
    return valor in {"1", "true", "yes"}


@pytest.mark.integration
@pytest.mark.skipif(
    not _integracion_ollama_habilitada(),
    reason="Requiere Ollama en ejecución. Active RUN_OLLAMA_INTEGRATION_TESTS=true; no se inventa un resultado de Qwen.",
)
def test_ollama_real_generate_requires_local_server() -> None:
    settings = Settings(_env_file=None)
    adapter = AdaptadorGeneracionOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout_seconds=settings.ollama_timeout_seconds,
    )
    generated = adapter.generar(
        texto_consulta="¿Cómo riego la papa en floración?",
        cultivo="papa",
        region="Huancayo",
        pasajes=[
            PasajeRecuperado(
                titulo="Riego de papa",
                extracto="La papa en sierra requiere riegos frecuentes en floración.",
            )
        ],
    )
    assert generated.metodo_generacion == "ollama"
    assert generated.texto_respuesta.strip()
