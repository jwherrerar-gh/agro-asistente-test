from app.application.services.servicio_recuperacion_rag import (
    FragmentoRecuperado,
    ServicioRecuperacionRag,
)
from app.application.services.suficiencia_contexto import (
    fragmentos_con_respaldo,
    texto_con_cantidades_controladas,
)
from app.domain.entities.consulta import Consulta
from app.domain.entities.evidencia import Evidencia
from app.domain.entities.respuesta import Respuesta
from app.domain.exceptions import (
    ErrorClasificadorNoDisponible,
    ErrorContextoSeleccionadoNoEncontrado,
)
from app.domain.ports.input.clasificar_consulta_port import (
    ComandoClasificarConsulta,
    PuertoClasificarConsulta,
    ResultadoClasificacionConsulta,
)
from app.domain.ports.input.registrar_consulta_port import (
    ComandoRegistrarConsulta,
    PuertoRegistrarConsulta,
    ResultadoContextoConsulta,
    ResultadoEvidenciaConsulta,
    ResultadoRegistrarConsulta,
)
from app.domain.ports.output.repositorio_consulta_port import PuertoRepositorioConsulta
from app.domain.ports.output.repositorio_evidencia_port import PuertoRepositorioEvidencia
from app.domain.ports.output.text_generation_port import PasajeRecuperado, PuertoGeneracionTexto
from app.domain.valueObjects.texto_consulta import TextoConsulta


class RegistrarConsulta(PuertoRegistrarConsulta):
    def __init__(
        self,
        repositorio_consulta: PuertoRepositorioConsulta,
        generacion_texto: PuertoGeneracionTexto,
        recuperacion_rag: ServicioRecuperacionRag,
        repositorio_evidencia: PuertoRepositorioEvidencia,
        clasificar_consulta: PuertoClasificarConsulta,
    ) -> None:
        self._repositorio_consulta = repositorio_consulta
        self._generacion_texto = generacion_texto
        self._recuperacion_rag = recuperacion_rag
        self._repositorio_evidencia = repositorio_evidencia
        self._clasificar_consulta = clasificar_consulta

    def ejecutar(self, comando: ComandoRegistrarConsulta) -> ResultadoRegistrarConsulta:
        texto_consulta = TextoConsulta(comando.texto)
        contexto = self._repositorio_consulta.buscar_contexto_seleccionado(comando.agricultor_id)
        if contexto is None or contexto.agricultor_id != comando.agricultor_id:
            raise ErrorContextoSeleccionadoNoEncontrado(
                "Debes seleccionar un contexto agrícola antes de consultar"
            )

        consulta = Consulta.crear(
            agricultor_id=comando.agricultor_id,
            contexto_id=contexto.id,
            texto=texto_consulta,
        )
        clasificacion, error_clasificacion = self._clasificar_una_vez(consulta.texto.value)
        fragmentos = self._recuperacion_rag.recuperar(consulta.texto.value)
        utilizados = fragmentos_con_respaldo(consulta.texto.value, fragmentos)
        generada = self._generacion_texto.generar(
            texto_consulta=consulta.texto.value,
            cultivo=contexto.cultivo.value,
            region=contexto.region.value,
            pasajes=_pasajes_desde_fragmentos(utilizados),
        )
        texto_controlado = texto_con_cantidades_controladas(
            generada.texto_respuesta,
            [fragmento.extracto for fragmento in utilizados],
        )
        self._repositorio_consulta.guardar_consulta(consulta)
        respuesta = Respuesta.crear(
            consulta_id=consulta.id,
            texto_respuesta=texto_controlado,
            metodo_generacion=generada.metodo_generacion,
        )
        self._repositorio_consulta.guardar_respuesta(respuesta)

        evidencias = _evidencias_desde_fragmentos(consulta.id, respuesta.id, utilizados)
        if evidencias:
            self._repositorio_evidencia.guardar_todas(evidencias)

        return ResultadoRegistrarConsulta(
            id=consulta.id,
            texto=consulta.texto.value,
            respuesta=respuesta.texto_respuesta,
            metodo_generacion=respuesta.metodo_generacion,
            creado_en=consulta.creado_en.isoformat(),
            contexto=ResultadoContextoConsulta(
                id=contexto.id,
                cultivo=contexto.cultivo.value,
                region=contexto.region.value,
                nombre_predio=contexto.nombre_predio,
            ),
            evidencias=tuple(_resultado_evidencia(item) for item in evidencias),
            clasificacion=clasificacion,
            error_clasificacion=error_clasificacion,
        )

    def _clasificar_una_vez(
        self, texto: str
    ) -> tuple[ResultadoClasificacionConsulta | None, str | None]:
        try:
            return self._clasificar_consulta.ejecutar(ComandoClasificarConsulta(texto=texto)), None
        except ErrorClasificadorNoDisponible as error:
            return None, str(error)


def _pasajes_desde_fragmentos(fragmentos: list[FragmentoRecuperado]) -> list[PasajeRecuperado]:
    return [
        PasajeRecuperado(titulo=item.titulo_documento, extracto=item.extracto)
        for item in fragmentos
    ]


def _evidencias_desde_fragmentos(
    consulta_id: str,
    respuesta_id: str,
    fragmentos: list[FragmentoRecuperado],
) -> list[Evidencia]:
    evidencias: list[Evidencia] = []
    for indice, fragmento in enumerate(fragmentos, start=1):
        evidencias.append(
            Evidencia.crear(
                consulta_id=consulta_id,
                respuesta_id=respuesta_id,
                documento_id=fragmento.documento_id,
                fragmento_id=fragmento.fragmento_id,
                extracto=fragmento.extracto,
                puntaje_similitud=fragmento.puntaje_similitud,
                orden_relevancia=indice,
                titulo_documento=fragmento.titulo_documento,
            )
        )
    return evidencias


def _resultado_evidencia(evidencia: Evidencia) -> ResultadoEvidenciaConsulta:
    return ResultadoEvidenciaConsulta(
        documento_id=evidencia.documento_id,
        titulo_documento=evidencia.titulo_documento,
        fragmento_id=evidencia.fragmento_id,
        extracto=evidencia.extracto,
        puntaje_similitud=evidencia.puntaje_similitud,
        orden_relevancia=evidencia.orden_relevancia,
    )
