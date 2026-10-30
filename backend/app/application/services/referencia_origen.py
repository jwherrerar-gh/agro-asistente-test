import re
from urllib.parse import urlparse

_RUTA_LOCAL = re.compile(r"^knowledge/[A-Za-z0-9][A-Za-z0-9._-]*\.md$")


def referencia_origen_verificable(ruta: str | None) -> str:
    """Devuelve la ruta guardada solo si es un archivo local conocido o una URL http(s)."""
    valor = (ruta or "").strip()
    if not valor or any(caracter in valor for caracter in ("\n", "\r", "\x00")):
        return ""
    if ".." not in valor and _RUTA_LOCAL.fullmatch(valor):
        return valor
    if _url_http_valida(valor):
        return valor
    return ""


def resolver_referencia_documento(repositorio, documento_id: str) -> str:
    if not (documento_id or "").strip():
        return ""
    try:
        documento = repositorio.buscar_por_id(documento_id)
    except (TypeError, ValueError):
        return ""
    if documento is None:
        return ""
    return referencia_origen_verificable(getattr(documento, "ruta_origen", ""))


def _url_http_valida(valor: str) -> bool:
    if not (valor.startswith("http://") or valor.startswith("https://")):
        return False
    partes = urlparse(valor)
    if partes.scheme not in {"http", "https"}:
        return False
    if not partes.hostname:
        return False
    if partes.username or partes.password:
        return False
    return True
