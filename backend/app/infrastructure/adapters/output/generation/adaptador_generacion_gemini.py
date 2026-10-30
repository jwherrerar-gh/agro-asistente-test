import httpx

from app.domain.exceptions import ErrorGeneracionTexto
from app.domain.ports.output.text_generation_port import (
    PasajeRecuperado,
    PuertoGeneracionTexto,
    RespuestaGenerada,
)
from app.infrastructure.adapters.output.generation.adaptador_generacion_ollama import (
    INSTRUCCION_SISTEMA,
    construir_prompt_agricola,
)


class AdaptadorGeneracionGemini(PuertoGeneracionTexto):
    """Adaptador de infraestructura hacia Gemini API."""

    METHOD = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: int = 90,
        cliente_http: object | None = None,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._model = (model or "").strip()
        self._timeout_seconds = timeout_seconds
        self._cliente = cliente_http

    def generar(
        self,
        texto_consulta: str,
        cultivo: str,
        region: str,
        pasajes: list[PasajeRecuperado] | None = None,
    ) -> RespuestaGenerada:
        if not self._api_key:
            raise ErrorGeneracionTexto(
                "No se pudo generar la respuesta: falta la API key de Gemini (GEMINI_API_KEY)."
            )
        if not self._model:
            raise ErrorGeneracionTexto(
                "No se pudo generar la respuesta: falta configurar el modelo de Gemini (GEMINI_MODEL)."
            )

        prompt = construir_prompt_agricola(texto_consulta, cultivo, region, pasajes)
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": INSTRUCCION_SISTEMA}]},
            "generationConfig": {"temperature": 0.2},
        }
        try:
            respuesta_http = self._post(payload)
        except httpx.TimeoutException as error:
            raise ErrorGeneracionTexto(
                "No se pudo generar la respuesta: el servicio de Gemini excedió el tiempo de espera."
            ) from error
        except httpx.RequestError as error:
            raise ErrorGeneracionTexto(
                "No se pudo generar la respuesta: el servicio de Gemini no está disponible. "
                "Comprueba GEMINI_API_KEY y la conectividad."
            ) from error

        return RespuestaGenerada(
            texto_respuesta=_texto_desde_respuesta(respuesta_http, self._model),
            metodo_generacion=self.METHOD,
        )

    def _post(self, payload: dict[str, object]) -> object:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}"
            f":generateContent?key={self._api_key}"
        )
        if self._cliente is not None:
            return self._cliente.post(url, json=payload, timeout=self._timeout_seconds)
        with httpx.Client(timeout=self._timeout_seconds) as cliente:
            return cliente.post(url, json=payload)


def _texto_desde_respuesta(respuesta_http: object, modelo: str) -> str:
    status_code = int(getattr(respuesta_http, "status_code", 0) or 0)
    cuerpo, json_valido = _json_intento(respuesta_http)

    if status_code >= 400:
        detalle = _error_remoto(cuerpo, status_code)
        raise ErrorGeneracionTexto(f"No se pudo generar la respuesta: {detalle}.")

    if not json_valido or not isinstance(cuerpo, dict):
        raise ErrorGeneracionTexto(
            "No se pudo generar la respuesta: el servicio devolvió un formato inválido."
        )

    candidates = cuerpo.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ErrorGeneracionTexto(
            "No se pudo generar la respuesta: Gemini no devolvió contenido útil."
        )

    texto = ""
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if isinstance(part, dict):
                chunk = str(part.get("text") or "").strip()
                if chunk:
                    texto = f"{texto} {chunk}".strip()
    if not texto:
        raise ErrorGeneracionTexto(
            "No se pudo generar la respuesta: el modelo devolvió un texto vacío."
        )
    return texto


def _json_intento(respuesta_http: object) -> tuple[object, bool]:
    lector = getattr(respuesta_http, "json", None)
    if not callable(lector):
        return {}, False
    try:
        return lector(), True
    except (ValueError, TypeError):
        return {}, False


def _error_remoto(cuerpo: object, status_code: int) -> str:
    if isinstance(cuerpo, dict):
        error = cuerpo.get("error")
        if isinstance(error, dict):
            detalle = str(error.get("message") or error.get("status") or "error del servicio").strip()
            if detalle:
                return detalle
        if "message" in cuerpo:
            detalle = str(cuerpo["message"]).strip()
            if detalle:
                return detalle
    if status_code:
        return f"el servicio respondió HTTP {status_code}"
    return "el servicio de Gemini respondió con un error"
