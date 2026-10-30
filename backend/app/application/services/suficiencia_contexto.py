"""Filtro léxico de respaldo y revisión de cantidades.

No interpreta el significado de la consulta. Solo compara términos normalizados
del texto de la pregunta con los extractos ya recuperados. Un fragmento puede
superar el umbral de similitud y, aun así, quedar fuera de este filtro.

Limitaciones:

- No reconoce sinónimos ni paráfrasis. «Encharcar» no equivale a «exceso de agua»
  salvo que otro término de contenido sí coincida.
- Las equivalencias son una lista cerrada: formas de «riego» y de «helada».
- Ignora palabras vacías y unos pocos términos generales de este dominio
  (papa, cultivo, agrícola, condiciones, zona, región, Junín). En otro índice,
  un término que aquí se conserva, como «suelo», podría coincidir de más.
- La revisión de cantidades solo ve cifras con una unidad cercana (kg, litros,
  cm, días o grados Celsius), incluidos decimales y rangos. No detecta
  recomendaciones sin cifras ni cantidades escritas con palabras, como
  «ciento cincuenta kilos» o «capas de tierra».
"""

from __future__ import annotations

import re
import unicodedata

from app.application.services.servicio_recuperacion_rag import FragmentoRecuperado
from app.domain.ports.output.text_generation_port import PasajeRecuperado

TEXTO_INSUFICIENTE = "La base de conocimiento no alcanza para responder."

_EQUIVALENCIAS = {
    "regar": "riego",
    "riego": "riego",
    "riegos": "riego",
    "riegue": "riego",
    "helada": "helada",
    "heladas": "helada",
}

_GENERALES = {
    "papa",
    "papas",
    "cultivo",
    "cultivos",
    "agricola",
    "agricolas",
    "condicion",
    "condiciones",
    "zona",
    "zonas",
    "region",
    "regiones",
    "junin",
}

_VACIAS = {
    "a",
    "al",
    "algo",
    "ante",
    "con",
    "como",
    "cual",
    "cuales",
    "cuando",
    "cuanta",
    "cuantas",
    "cuanto",
    "cuantos",
    "de",
    "debo",
    "debe",
    "deben",
    "del",
    "desde",
    "donde",
    "el",
    "ella",
    "ellas",
    "ellos",
    "en",
    "entre",
    "es",
    "esa",
    "esas",
    "ese",
    "eso",
    "esos",
    "esta",
    "estas",
    "este",
    "esto",
    "estos",
    "ha",
    "hacer",
    "hago",
    "han",
    "hay",
    "la",
    "las",
    "le",
    "les",
    "lo",
    "los",
    "mas",
    "me",
    "mi",
    "mis",
    "muy",
    "no",
    "nos",
    "o",
    "para",
    "pero",
    "por",
    "puedo",
    "puede",
    "pueden",
    "que",
    "se",
    "ser",
    "si",
    "sin",
    "son",
    "su",
    "sus",
    "te",
    "tu",
    "tus",
    "un",
    "una",
    "unas",
    "uno",
    "unos",
    "y",
    "ya",
    "yo",
}

_NUMERO = r"\d+(?:[.,]\d+)?"
_UNIDAD = (
    r"kg|kilos?|kilogramos?|litros?|mililitros?|ml|"
    r"cm|centimetros?|dias?|°\s*c|º\s*c|grados\s+celsius"
)
_CANTIDAD = re.compile(
    rf"(?P<n1>{_NUMERO})(?:\s*(?:a|y|-|–|—)\s*(?P<n2>{_NUMERO}))?\s*(?P<unidad>{_UNIDAD})\b",
    re.IGNORECASE,
)
_NUMEROS = re.compile(_NUMERO)
_UNIDADES_PRESENTES = re.compile(_UNIDAD, re.IGNORECASE)


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes. Conserva dígitos y los signos de grado."""
    base = (texto or "").replace("º", "°").lower()
    descompuesto = unicodedata.normalize("NFD", base)
    sin_tildes = "".join(
        caracter for caracter in descompuesto if unicodedata.category(caracter) != "Mn"
    )
    return unicodedata.normalize("NFC", sin_tildes)


def tokenizar(texto: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalizar(texto))


def terminos_de_contenido(texto: str) -> set[str]:
    terminos: set[str] = set()
    for token in tokenizar(texto):
        canonico = _EQUIVALENCIAS.get(token, token)
        if len(canonico) < 3 or canonico in _VACIAS or canonico in _GENERALES:
            continue
        terminos.add(canonico)
    return terminos


def extracto_respalda_consulta(consulta: str, extracto: str) -> bool:
    consulta_terminos = terminos_de_contenido(consulta)
    if not consulta_terminos:
        return False
    return bool(consulta_terminos & terminos_de_contenido(extracto))


def fragmentos_con_respaldo(
    consulta: str,
    fragmentos: list[FragmentoRecuperado],
) -> list[FragmentoRecuperado]:
    return [
        fragmento
        for fragmento in fragmentos
        if extracto_respalda_consulta(consulta, fragmento.extracto)
    ]


def pasajes_con_respaldo(
    consulta: str,
    pasajes: list[PasajeRecuperado],
) -> list[PasajeRecuperado]:
    return [
        pasaje
        for pasaje in pasajes
        if extracto_respalda_consulta(consulta, pasaje.extracto)
    ]


def texto_con_cantidades_controladas(respuesta: str, extractos: list[str]) -> str:
    """Sustituye la respuesta si trae una cantidad numérica ausente de los extractos.

    Una cantidad es un número, o un rango de dos números, junto a una unidad
    reconocida. No cubre recomendaciones sin cifras ni cantidades en palabras.
    """
    if _cantidades_no_respaldadas(respuesta, extractos):
        return TEXTO_INSUFICIENTE
    return respuesta


def _cantidades_no_respaldadas(respuesta: str, extractos: list[str]) -> bool:
    texto = normalizar(respuesta)
    if not texto:
        return False
    contexto = normalizar("\n".join(extractos))
    numeros = {_canonico_numero(numero) for numero in _NUMEROS.findall(contexto)}
    familias = {_familia_unidad(unidad) for unidad in _UNIDADES_PRESENTES.findall(contexto)}
    for hallazgo in _CANTIDAD.finditer(texto):
        familia = _familia_unidad(hallazgo.group("unidad"))
        numeros_respuesta = [_canonico_numero(hallazgo.group("n1"))]
        if hallazgo.group("n2"):
            numeros_respuesta.append(_canonico_numero(hallazgo.group("n2")))
        if familia not in familias or any(numero not in numeros for numero in numeros_respuesta):
            return True
    return False


def _canonico_numero(numero: str) -> str:
    limpio = numero.replace(",", ".")
    if "." not in limpio:
        return limpio.lstrip("0") or "0"
    entero, fraccion = limpio.split(".", 1)
    fraccion = fraccion.rstrip("0")
    entero_limpio = entero.lstrip("0") or "0"
    if not fraccion:
        return entero_limpio
    return f"{entero_limpio}.{fraccion}"


def _familia_unidad(unidad: str) -> str:
    compacta = re.sub(r"\s+", "", normalizar(unidad))
    if compacta in {"kg", "kilo", "kilos", "kilogramo", "kilogramos"}:
        return "kg"
    if compacta in {"litro", "litros"}:
        return "litro"
    if compacta in {"ml", "mililitro", "mililitros"}:
        return "ml"
    if compacta in {"cm", "centimetro", "centimetros"}:
        return "cm"
    if compacta in {"dia", "dias"}:
        return "dia"
    return "celsius"
