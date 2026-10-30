from types import SimpleNamespace

import pytest

from app.application.services.referencia_origen import (
    referencia_origen_verificable,
    resolver_referencia_documento,
)

RUTA = "knowledge/7019602d-f4ac-4153-8cdc-acd18a03fa3a.md"


class RepositorioFalso:
    def __init__(self, documentos: dict[str, str | None]) -> None:
        self.documentos = documentos

    def buscar_por_id(self, documento_id: str):
        if documento_id == "invalido":
            raise ValueError("id")
        ruta = self.documentos.get(documento_id)
        if ruta is None and documento_id not in self.documentos:
            return None
        if ruta is None:
            return None
        return SimpleNamespace(ruta_origen=ruta)


def test_ruta_local_de_conocimiento_se_conserva() -> None:
    assert referencia_origen_verificable(f"  {RUTA}  ") == RUTA


def test_url_http_guardada_se_conserva() -> None:
    assert referencia_origen_verificable("https://ejemplo.gob.pe/guia") == (
        "https://ejemplo.gob.pe/guia"
    )
    assert referencia_origen_verificable("http://ejemplo.gob.pe/guia") == "http://ejemplo.gob.pe/guia"


@pytest.mark.parametrize(
    "ruta",
    [
        "",
        "   ",
        "javascript:alert(1)",
        "data:text/html,hola",
        "file:///C:/secreto.md",
        "http://usuario:clave@ejemplo.gob.pe/guia",
        "knowledge/../secreto.md",
        "https://",
        "nota sin ruta",
    ],
)
def test_referencia_ausente_o_insegura_no_se_publica(ruta: str) -> None:
    assert referencia_origen_verificable(ruta) == ""


def test_resolver_usa_la_ruta_del_documento_y_tolera_ausencia() -> None:
    repositorio = RepositorioFalso({"18": RUTA, "5": "javascript:alert(1)", "9": None})
    assert resolver_referencia_documento(repositorio, "18") == RUTA
    assert resolver_referencia_documento(repositorio, "5") == ""
    assert resolver_referencia_documento(repositorio, "9") == ""
    assert resolver_referencia_documento(repositorio, "invalido") == ""
    assert resolver_referencia_documento(repositorio, "") == ""
