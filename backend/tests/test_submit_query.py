from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from app.application.services.servicio_recuperacion_rag import FragmentoRecuperado
from app.application.useCases.registrar_consulta import RegistrarConsulta
from app.domain.entities.consulta import Consulta
from app.domain.entities.contexto_agricola import ContextoAgricola
from app.domain.entities.evidencia import Evidencia
from app.domain.entities.respuesta import Respuesta
from app.domain.exceptions import (
    ErrorContextoSeleccionadoNoEncontrado,
    ErrorGeneracionTexto,
    ErrorTextoConsultaInvalido,
)
from app.domain.ports.input.clasificar_consulta_port import (
    PuertoClasificarConsulta,
    ResultadoClasificacionConsulta,
)
from app.domain.ports.input.registrar_consulta_port import ComandoRegistrarConsulta
from app.domain.ports.output.repositorio_consulta_port import PuertoRepositorioConsulta
from app.domain.ports.output.repositorio_evidencia_port import PuertoRepositorioEvidencia
from app.domain.ports.output.text_generation_port import (
    PasajeRecuperado,
    PuertoGeneracionTexto,
    RespuestaGenerada,
)
from app.domain.valueObjects.cultivo import Cultivo
from app.domain.valueObjects.region import Region
from app.domain.valueObjects.texto_consulta import TextoConsulta

FARMER_A = "farmer-a"
FARMER_B = "farmer-b"
QUESTION = "¿Qué puedo hacer para mejorar el cultivo de papa?"


class RepositorioConsultaEnMemoria(PuertoRepositorioConsulta):
    def __init__(self) -> None:
        self.contextos_seleccionados: dict[str, ContextoAgricola] = {}
        self.consultas: list[Consulta] = []
        self.respuestas: list[Respuesta] = []

    def buscar_contexto_seleccionado(self, agricultor_id: str) -> ContextoAgricola | None:
        contexto = self.contextos_seleccionados.get(agricultor_id)
        if contexto is None or contexto.agricultor_id != agricultor_id:
            return None
        return contexto

    def guardar_consulta(self, consulta: Consulta) -> None:
        self.consultas.append(consulta)

    def guardar_respuesta(self, respuesta: Respuesta) -> None:
        self.respuestas.append(respuesta)


class RepositorioEvidenciaEnMemoria(PuertoRepositorioEvidencia):
    def __init__(self) -> None:
        self.evidencias: list[Evidencia] = []

    def guardar_todas(self, evidencias: list[Evidencia]) -> None:
        self.evidencias.extend(evidencias)

    def listar_por_consulta_id(self, consulta_id: str) -> list[Evidencia]:
        return [item for item in self.evidencias if item.consulta_id == consulta_id]


class GeneracionTextoFalsa(PuertoGeneracionTexto):
    def generar(
        self,
        texto_consulta: str,
        cultivo: str,
        region: str,
        pasajes: list[PasajeRecuperado] | None = None,
    ) -> RespuestaGenerada:
        extra = ""
        if pasajes:
            extra = "|" + "|".join(item.extracto for item in pasajes)
        return RespuestaGenerada(
            texto_respuesta=f"FAKE:{cultivo}:{region}:{texto_consulta}{extra}",
            metodo_generacion="template",
        )


class RecuperacionRagFalsa:
    def __init__(self, fragmentos: list[FragmentoRecuperado] | None = None) -> None:
        self.fragmentos = fragmentos or []
        self.consultas: list[str] = []

    def recuperar(self, texto_consulta: str) -> list[FragmentoRecuperado]:
        self.consultas.append(texto_consulta)
        return list(self.fragmentos)


def _contexto(
    agricultor_id: str,
    cultivo: str = "papa",
    region: str = "Huancayo",
    nombre_predio: str | None = "Parcela 1",
) -> ContextoAgricola:
    return ContextoAgricola(
        contexto_id=str(uuid4()),
        agricultor_id=agricultor_id,
        nombre_predio=nombre_predio,
        cultivo=Cultivo(cultivo),
        region=Region(region),
        observaciones=None,
        esta_seleccionado=True,
        creado_en=datetime.now(timezone.utc).replace(tzinfo=None),
    )


class ClasificadorFijo(PuertoClasificarConsulta):
    def ejecutar(self, comando) -> ResultadoClasificacionConsulta:
        return ResultadoClasificacionConsulta(
            categoria="siembra_manejo_cultivo",
            abstencion=False,
            motivo_abstencion=None,
            clase_primera="siembra_manejo_cultivo",
            puntuacion_primera=0.8,
            clase_segunda="riego",
            puntuacion_segunda=0.1,
            margen=0.7,
            puntuaciones_calibradas=False,
        )


def _caso_de_uso(
    repositorio: RepositorioConsultaEnMemoria | None = None,
    generacion: PuertoGeneracionTexto | None = None,
    rag: RecuperacionRagFalsa | None = None,
    repositorio_evidencia: RepositorioEvidenciaEnMemoria | None = None,
) -> tuple[
    RegistrarConsulta,
    RepositorioConsultaEnMemoria,
    PuertoGeneracionTexto,
    RecuperacionRagFalsa,
    RepositorioEvidenciaEnMemoria,
]:
    repo = repositorio or RepositorioConsultaEnMemoria()
    generator = generacion or GeneracionTextoFalsa()
    retrieval = rag or RecuperacionRagFalsa()
    evidencias = repositorio_evidencia or RepositorioEvidenciaEnMemoria()
    return (
        RegistrarConsulta(
            repo,
            generator,
            retrieval,
            evidencias,
            clasificar_consulta=ClasificadorFijo(),
        ),
        repo,
        generator,
        retrieval,
        evidencias,
    )


def test_submit_query_success() -> None:
    use_case, repository, _generation, _rag, _evidences = _caso_de_uso()
    context = _contexto(FARMER_A)
    repository.contextos_seleccionados[FARMER_A] = context

    result = use_case.ejecutar(ComandoRegistrarConsulta(agricultor_id=FARMER_A, texto=QUESTION))

    assert result.texto == QUESTION
    assert result.contexto.id == context.id
    assert result.contexto.cultivo == "papa"
    assert result.contexto.region == "Huancayo"
    assert result.metodo_generacion == "template"
    assert result.id
    assert result.creado_en


def test_submit_query_empty_text() -> None:
    use_case, repository, _generation, _rag, _evidences = _caso_de_uso()
    repository.contextos_seleccionados[FARMER_A] = _contexto(FARMER_A)
    with pytest.raises(ErrorTextoConsultaInvalido, match="obligatorio"):
        use_case.ejecutar(ComandoRegistrarConsulta(agricultor_id=FARMER_A, texto="   "))


def test_submit_query_invalid_text_too_long() -> None:
    use_case, repository, _generation, _rag, _evidences = _caso_de_uso()
    repository.contextos_seleccionados[FARMER_A] = _contexto(FARMER_A)
    with pytest.raises(ErrorTextoConsultaInvalido, match="longitud"):
        use_case.ejecutar(
            ComandoRegistrarConsulta(
                agricultor_id=FARMER_A,
                texto="a" * (TextoConsulta.MAX_LENGTH + 1),
            )
        )


def test_submit_query_without_selected_context() -> None:
    use_case, _repository, _generation, _rag, _evidences = _caso_de_uso()
    with pytest.raises(ErrorContextoSeleccionadoNoEncontrado, match="contexto agrícola"):
        use_case.ejecutar(ComandoRegistrarConsulta(agricultor_id=FARMER_A, texto=QUESTION))


def test_submit_query_uses_authenticated_farmer_selected_context() -> None:
    use_case, repository, _generation, _rag, _evidences = _caso_de_uso()
    context_a = _contexto(FARMER_A, cultivo="papa", region="Huancayo")
    context_b = _contexto(FARMER_B, cultivo="maiz", region="Cusco")
    repository.contextos_seleccionados[FARMER_A] = context_a
    repository.contextos_seleccionados[FARMER_B] = context_b

    result = use_case.ejecutar(ComandoRegistrarConsulta(agricultor_id=FARMER_A, texto=QUESTION))

    assert result.contexto.id == context_a.id
    assert result.contexto.cultivo == "papa"
    assert result.contexto.region == "Huancayo"
    assert result.contexto.id != context_b.id
    assert repository.consultas[0].agricultor_id == FARMER_A
    assert repository.consultas[0].contexto_id == context_a.id


def test_submit_query_persists_query() -> None:
    use_case, repository, _generation, _rag, _evidences = _caso_de_uso()
    context = _contexto(FARMER_A)
    repository.contextos_seleccionados[FARMER_A] = context

    result = use_case.ejecutar(ComandoRegistrarConsulta(agricultor_id=FARMER_A, texto=QUESTION))

    assert len(repository.consultas) == 1
    stored = repository.consultas[0]
    assert stored.id == result.id
    assert stored.agricultor_id == FARMER_A
    assert stored.contexto_id == context.id
    assert stored.texto.value == QUESTION
    assert stored.creado_en is not None


def test_submit_query_uses_text_generation_port() -> None:
    use_case, repository, _generation, _rag, _evidences = _caso_de_uso()
    repository.contextos_seleccionados[FARMER_A] = _contexto(
        FARMER_A, cultivo="papa", region="Huancayo"
    )

    result = use_case.ejecutar(ComandoRegistrarConsulta(agricultor_id=FARMER_A, texto=QUESTION))

    assert result.respuesta == f"FAKE:papa:Huancayo:{QUESTION}"
    assert result.metodo_generacion == "template"


def test_submit_query_persists_response() -> None:
    use_case, repository, _generation, _rag, _evidences = _caso_de_uso()
    repository.contextos_seleccionados[FARMER_A] = _contexto(FARMER_A)

    result = use_case.ejecutar(ComandoRegistrarConsulta(agricultor_id=FARMER_A, texto=QUESTION))

    assert len(repository.respuestas) == 1
    stored = repository.respuestas[0]
    assert stored.consulta_id == result.id
    assert stored.texto_respuesta == result.respuesta
    assert stored.metodo_generacion == "template"


def test_submit_query_use_case_does_not_import_frameworks_or_sdks() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "application"
        / "useCases"
        / "registrar_consulta.py"
    ).read_text(encoding="utf-8")
    lowered = source.lower()
    forbidden = (
        "fastapi",
        "sqlalchemy",
        "chromadb",
        "chroma",
        "openai",
        "anthropic",
        "langchain",
        "httpx",
        "pydantic",
        "import jwt",
        "from jwt",
        "import bcrypt",
        "pymysql",
        "ollama",
    )
    for item in forbidden:
        assert item not in lowered
    assert "puertorepositorioconsulta" in lowered
    assert "puertogeneraciontexto" in lowered
    assert "puertorepositorioevidencia" in lowered
    assert "repositorioconsultamysql" not in lowered
    assert "adaptadorgeneracionplantilla" not in lowered
    assert "chromavectorstoreadapter" not in lowered


def test_submit_query_associates_and_persists_evidences() -> None:
    snippet = FragmentoRecuperado(
        documento_id="doc-1",
        titulo_documento="Riego de papa",
        fragmento_id="abc:chunk:0000",
        extracto="Riego frecuente en floración.",
        puntaje_similitud=0.81,
    )
    use_case, repository, _generation, rag, evidence_repo = _caso_de_uso(
        rag=RecuperacionRagFalsa([snippet])
    )
    repository.contextos_seleccionados[FARMER_A] = _contexto(FARMER_A)

    consulta_con_respaldo = "¿Conviene un riego frecuente en floración?"
    result = use_case.ejecutar(
        ComandoRegistrarConsulta(agricultor_id=FARMER_A, texto=consulta_con_respaldo)
    )

    assert rag.consultas == [consulta_con_respaldo]
    assert len(result.evidencias) == 1
    assert result.evidencias[0].documento_id == "doc-1"
    assert result.evidencias[0].extracto == "Riego frecuente en floración."
    assert result.evidencias[0].orden_relevancia == 1
    assert len(evidence_repo.evidencias) == 1
    stored = evidence_repo.evidencias[0]
    assert stored.consulta_id == result.id
    assert stored.respuesta_id == repository.respuestas[0].id
    assert stored.documento_id == "doc-1"
    assert stored.titulo_documento == "Riego de papa"
    assert result.evidencias[0].titulo_documento == "Riego de papa"
    assert "Riego frecuente" in result.respuesta


def test_submit_query_without_relevant_results_does_not_invent_evidence() -> None:
    use_case, repository, _generation, _rag, evidence_repo = _caso_de_uso()
    repository.contextos_seleccionados[FARMER_A] = _contexto(FARMER_A)

    result = use_case.ejecutar(ComandoRegistrarConsulta(agricultor_id=FARMER_A, texto=QUESTION))

    assert result.evidencias == ()
    assert evidence_repo.evidencias == []
    assert result.respuesta == f"FAKE:papa:Huancayo:{QUESTION}"


class GeneracionTextoNoDisponible(PuertoGeneracionTexto):
    def generar(
        self,
        texto_consulta: str,
        cultivo: str,
        region: str,
        pasajes: list[PasajeRecuperado] | None = None,
    ) -> RespuestaGenerada:
        raise ErrorGeneracionTexto(
            "No se pudo generar la respuesta: el servicio de generación local no está disponible."
        )


def test_submit_query_generation_error_does_not_persist() -> None:
    use_case, repository, _generation, rag, evidence_repo = _caso_de_uso(
        generacion=GeneracionTextoNoDisponible(),
        rag=RecuperacionRagFalsa(
            [
                FragmentoRecuperado(
                    documento_id="doc-1",
                    titulo_documento="Heladas",
                    fragmento_id="abc:chunk:0000",
                    extracto="Cubrir plantones jóvenes antes de madrugadas frías.",
                    puntaje_similitud=0.7,
                )
            ]
        ),
    )
    repository.contextos_seleccionados[FARMER_A] = _contexto(FARMER_A)

    with pytest.raises(ErrorGeneracionTexto, match="no está disponible"):
        use_case.ejecutar(ComandoRegistrarConsulta(agricultor_id=FARMER_A, texto=QUESTION))

    assert rag.consultas == [QUESTION]
    assert repository.consultas == []
    assert repository.respuestas == []
    assert evidence_repo.evidencias == []


EXTRACTO_RIEGO = (
    "El riego debe realizarse considerando el suelo. "
    "Vigilar la humedad del suelo. Evitar el exceso de agua."
)
EXTRACTO_HELADAS = (
    "Las heladas pueden afectar el cultivo. "
    "Utilizar métodos de protección. Vigilar la temperatura."
)


class GeneracionControlada(PuertoGeneracionTexto):
    def __init__(self, texto: str) -> None:
        self.texto = texto
        self.pasajes: list[PasajeRecuperado] | None = None

    def generar(
        self,
        texto_consulta: str,
        cultivo: str,
        region: str,
        pasajes: list[PasajeRecuperado] | None = None,
    ) -> RespuestaGenerada:
        self.pasajes = list(pasajes or [])
        return RespuestaGenerada(texto_respuesta=self.texto, metodo_generacion="ollama")


def _riego() -> FragmentoRecuperado:
    return FragmentoRecuperado(
        documento_id="18",
        titulo_documento="Prueba de riego de papa",
        fragmento_id="riego:chunk:0000",
        extracto=EXTRACTO_RIEGO,
        puntaje_similitud=0.40,
    )


def _heladas() -> FragmentoRecuperado:
    return FragmentoRecuperado(
        documento_id="5",
        titulo_documento="Manejo de heladas en el cultivo de papa",
        fragmento_id="heladas:chunk:0000",
        extracto=EXTRACTO_HELADAS,
        puntaje_similitud=0.41,
    )


def test_submit_query_riego_envia_solo_el_fragmento_utilizado() -> None:
    generacion = GeneracionControlada("Vigilar la humedad del suelo y evitar el exceso de agua.")
    use_case, repository, _generation, _rag, evidence_repo = _caso_de_uso(
        generacion=generacion,
        rag=RecuperacionRagFalsa([_riego(), _heladas()]),
    )
    repository.contextos_seleccionados[FARMER_A] = _contexto(FARMER_A)

    result = use_case.ejecutar(
        ComandoRegistrarConsulta(
            agricultor_id=FARMER_A,
            texto="¿Cómo debo regar el cultivo de papa para no encharcar el suelo?",
        )
    )

    assert generacion.pasajes is not None
    assert [pasaje.extracto for pasaje in generacion.pasajes] == [EXTRACTO_RIEGO]
    assert result.respuesta == "Vigilar la humedad del suelo y evitar el exceso de agua."
    assert [item.documento_id for item in result.evidencias] == ["18"]
    assert [item.titulo_documento for item in evidence_repo.evidencias] == [
        "Prueba de riego de papa"
    ]
    assert [item.documento_id for item in evidence_repo.evidencias] == ["18"]


def test_submit_query_heladas_conserva_solo_su_fragmento() -> None:
    generacion = GeneracionControlada("Utilizar métodos de protección y vigilar la temperatura.")
    use_case, repository, _generation, _rag, evidence_repo = _caso_de_uso(
        generacion=generacion,
        rag=RecuperacionRagFalsa([_heladas(), _riego()]),
    )
    repository.contextos_seleccionados[FARMER_A] = _contexto(FARMER_A)

    result = use_case.ejecutar(
        ComandoRegistrarConsulta(
            agricultor_id=FARMER_A,
            texto="¿Qué hago si hay heladas en el cultivo de papa?",
        )
    )

    assert generacion.pasajes is not None
    assert [pasaje.extracto for pasaje in generacion.pasajes] == [EXTRACTO_HELADAS]
    assert [item.documento_id for item in evidence_repo.evidencias] == ["5"]
    assert result.respuesta.startswith("Utilizar métodos de protección")


def test_submit_query_urea_no_guarda_dosis_ni_fragmentos_ajenos() -> None:
    generacion = GeneracionControlada(
        "Se recomienda aplicar entre 150 y 200 kg de urea por hectárea."
    )
    use_case, repository, _generation, _rag, evidence_repo = _caso_de_uso(
        generacion=generacion,
        rag=RecuperacionRagFalsa([_heladas(), _riego()]),
    )
    repository.contextos_seleccionados[FARMER_A] = _contexto(FARMER_A)

    result = use_case.ejecutar(
        ComandoRegistrarConsulta(
            agricultor_id=FARMER_A,
            texto="¿Cuántos kilos de urea por hectárea debo aplicar al cultivo de papa?",
        )
    )

    assert generacion.pasajes == []
    assert result.respuesta == "La base de conocimiento no alcanza para responder."
    assert result.evidencias == ()
    assert evidence_repo.evidencias == []


def test_submit_query_sin_fragmentos_sustituye_una_dosis_inventada() -> None:
    generacion = GeneracionControlada("Aplique 150 kg de urea.")
    use_case, repository, _generation, _rag, evidence_repo = _caso_de_uso(
        generacion=generacion,
        rag=RecuperacionRagFalsa([]),
    )
    repository.contextos_seleccionados[FARMER_A] = _contexto(FARMER_A)

    result = use_case.ejecutar(
        ComandoRegistrarConsulta(
            agricultor_id=FARMER_A,
            texto="¿Cuántos kilos de urea por hectárea debo aplicar?",
        )
    )

    assert generacion.pasajes == []
    assert result.respuesta == "La base de conocimiento no alcanza para responder."
    assert "150" not in result.respuesta
    assert evidence_repo.evidencias == []


def test_submit_query_error_de_generacion_no_persiste_aunque_el_fragmento_respalde() -> None:
    use_case, repository, _generation, rag, evidence_repo = _caso_de_uso(
        generacion=GeneracionTextoNoDisponible(),
        rag=RecuperacionRagFalsa([_riego()]),
    )
    repository.contextos_seleccionados[FARMER_A] = _contexto(FARMER_A)

    with pytest.raises(ErrorGeneracionTexto, match="no está disponible"):
        use_case.ejecutar(
            ComandoRegistrarConsulta(
                agricultor_id=FARMER_A,
                texto="¿Cómo debo regar el cultivo de papa?",
            )
        )

    assert rag.consultas
    assert repository.consultas == []
    assert repository.respuestas == []
    assert evidence_repo.evidencias == []
