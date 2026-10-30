from app.application.services.servicio_recuperacion_rag import FragmentoRecuperado
from app.application.services.suficiencia_contexto import (
    TEXTO_INSUFICIENTE,
    fragmentos_con_respaldo,
    normalizar,
    pasajes_con_respaldo,
    texto_con_cantidades_controladas,
)
from app.domain.ports.output.text_generation_port import PasajeRecuperado

EXTRACTO_RIEGO = (
    "# Riego del cultivo de papa\n\n"
    "El riego debe realizarse considerando las condiciones del suelo y del cultivo.\n\n"
    "## Recomendaciones\n\n"
    "- Vigilar la humedad del suelo.\n"
    "- Evitar el exceso de agua.\n"
    "- Ajustar el riego según las condiciones del cultivo."
)
EXTRACTO_HELADAS = (
    "# Manejo de heladas en papa\n\n"
    "Las heladas pueden afectar el desarrollo del cultivo de papa.\n\n"
    "## Recomendaciones\n\n"
    "- Utilizar métodos de protección del cultivo.\n"
    "- Vigilar las condiciones de temperatura.\n"
    "- Considerar las condiciones de la zona agrícola."
)


def _fragmento(titulo: str, extracto: str, documento_id: str) -> FragmentoRecuperado:
    return FragmentoRecuperado(
        documento_id=documento_id,
        titulo_documento=titulo,
        fragmento_id=f"{documento_id}:chunk:0000",
        extracto=extracto,
        puntaje_similitud=0.4,
    )


def test_normalizar_quita_tildes_y_conserva_grados() -> None:
    assert normalizar("Días y hectáreas a 15 °C") == "dias y hectareas a 15 °c"


def test_consulta_de_riego_conserva_el_fragmento_pertinente() -> None:
    riego = _fragmento("Prueba de riego de papa", EXTRACTO_RIEGO, "18")
    heladas = _fragmento("Manejo de heladas en el cultivo de papa", EXTRACTO_HELADAS, "5")

    conservados = fragmentos_con_respaldo(
        "¿Cómo debo regar el cultivo de papa para no encharcar el suelo?",
        [riego, heladas],
    )

    assert conservados == [riego]


def test_consulta_de_heladas_conserva_el_fragmento_pertinente() -> None:
    riego = _fragmento("Prueba de riego de papa", EXTRACTO_RIEGO, "18")
    heladas = _fragmento("Manejo de heladas en el cultivo de papa", EXTRACTO_HELADAS, "5")

    conservados = fragmentos_con_respaldo(
        "¿Qué hago si hay heladas en el cultivo de papa?",
        [heladas, riego],
    )

    assert conservados == [heladas]


def test_consulta_de_urea_descarta_riego_y_heladas() -> None:
    fragmentos = [
        _fragmento("Manejo de heladas en el cultivo de papa", EXTRACTO_HELADAS, "5"),
        _fragmento("Prueba de riego de papa", EXTRACTO_RIEGO, "18"),
    ]

    assert (
        fragmentos_con_respaldo(
            "¿Cuántos kilos de urea por hectárea debo aplicar al cultivo de papa?",
            fragmentos,
        )
        == []
    )


def test_el_filtro_de_pasajes_usa_el_mismo_criterio() -> None:
    pasaje = PasajeRecuperado(titulo="Riego", extracto=EXTRACTO_RIEGO)

    assert pasajes_con_respaldo("¿Cómo regar sin exceso de agua?", [pasaje]) == [pasaje]
    assert pasajes_con_respaldo("¿Cuántos kilos de urea?", [pasaje]) == []


def test_dosis_numerica_ausente_se_sustituye() -> None:
    respuesta = texto_con_cantidades_controladas(
        "Se recomienda aplicar entre 150 y 200 kg de urea por hectárea.",
        [EXTRACTO_RIEGO, EXTRACTO_HELADAS],
    )

    assert respuesta == TEXTO_INSUFICIENTE


def test_decimal_y_rango_respaldados_se_conservan() -> None:
    extracto = "Aplicar 1,5 litros. La profundidad va de 10 a 15 cm. Vigilar 8 °C."

    assert (
        texto_con_cantidades_controladas("Use 1.5 litros por planta.", [extracto])
        == "Use 1.5 litros por planta."
    )
    assert (
        texto_con_cantidades_controladas("Siembre a 10-15 cm.", [extracto])
        == "Siembre a 10-15 cm."
    )
    assert (
        texto_con_cantidades_controladas("Proteja el cultivo bajo 8 °C.", [extracto])
        == "Proteja el cultivo bajo 8 °C."
    )


def test_unidad_distinta_con_el_mismo_numero_se_sustituye() -> None:
    assert (
        texto_con_cantidades_controladas("Aplique 10 kg.", ["El plazo es de 10 días."])
        == TEXTO_INSUFICIENTE
    )


def test_respuesta_sin_cantidades_nuevas_se_conserva() -> None:
    respuesta = "Vigilar la humedad del suelo y evitar el exceso de agua."

    assert texto_con_cantidades_controladas(respuesta, [EXTRACTO_RIEGO]) == respuesta


def test_recomendaciones_sin_cifras_no_las_detecta_esta_comprobacion() -> None:
    respuesta = "Coloque capas de tierra y barreras de hierba. Use ciento cincuenta kilos."

    assert texto_con_cantidades_controladas(respuesta, [EXTRACTO_HELADAS]) == respuesta
