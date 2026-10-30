from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.domain.entities.evidencia import Evidencia
from app.domain.ports.output.repositorio_evidencia_port import PuertoRepositorioEvidencia
from app.infrastructure.adapters.output.mysql.connection import (
    Base,
    id_a_dominio,
    id_a_entero,
)

_PREFIJO_FRAGMENTO = "CHUNK:"


class RegistroEvidencia(Base):
    __tablename__ = "evidencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    consulta_id: Mapped[int] = mapped_column(Integer, nullable=False)
    respuesta_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    documento_id: Mapped[int] = mapped_column(Integer, nullable=False)
    titulo_documento: Mapped[str] = mapped_column(
        String(200), nullable=False, default="", server_default=""
    )
    texto_fragmento: Mapped[str] = mapped_column(Text, nullable=False)
    puntuacion_similitud: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    fecha_creacion: Mapped[object] = mapped_column(DateTime, nullable=True)


class RepositorioEvidenciaMysql(PuertoRepositorioEvidencia):
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def guardar_todas(self, evidencias: list[Evidencia]) -> None:
        if not evidencias:
            return
        registros = [
            RegistroEvidencia(
                consulta_id=id_a_entero(item.consulta_id),
                respuesta_id=id_a_entero(item.respuesta_id) if item.respuesta_id else None,
                documento_id=id_a_entero(item.documento_id),
                titulo_documento=(item.titulo_documento or "").strip(),
                texto_fragmento=_texto_con_fragmento(item.fragmento_id, item.extracto),
                puntuacion_similitud=Decimal(str(item.puntaje_similitud)),
            )
            for item in evidencias
        ]
        with self._session_factory() as session:
            session.add_all(registros)
            session.commit()

    def listar_por_consulta_id(self, consulta_id: str) -> list[Evidencia]:
        with self._session_factory() as session:
            registros = session.scalars(
                select(RegistroEvidencia)
                .where(RegistroEvidencia.consulta_id == id_a_entero(consulta_id))
                .order_by(RegistroEvidencia.id.asc())
            ).all()
            return [
                self._a_entidad(registro, orden)
                for orden, registro in enumerate(registros, start=1)
            ]

    def _a_entidad(self, registro: RegistroEvidencia, orden_relevancia: int) -> Evidencia:
        fragmento_id, extracto = _partir_texto_fragmento(registro.texto_fragmento)
        puntaje = float(registro.puntuacion_similitud or 0)
        return Evidencia(
            evidencia_id=id_a_dominio(registro.id),
            consulta_id=id_a_dominio(registro.consulta_id),
            respuesta_id=id_a_dominio(registro.respuesta_id or 0),
            documento_id=id_a_dominio(registro.documento_id),
            fragmento_id=fragmento_id or id_a_dominio(registro.id),
            extracto=extracto,
            puntaje_similitud=puntaje,
            orden_relevancia=orden_relevancia,
            titulo_documento=(registro.titulo_documento or "").strip(),
        )


def _texto_con_fragmento(fragmento_id: str, extracto: str) -> str:
    identificador = (fragmento_id or "").strip()
    if identificador:
        return f"{_PREFIJO_FRAGMENTO}{identificador}\n{extracto}"
    return extracto


def _partir_texto_fragmento(texto: str) -> tuple[str, str]:
    contenido = texto or ""
    primera, _, resto = contenido.partition("\n")
    if primera.startswith(_PREFIJO_FRAGMENTO):
        return primera[len(_PREFIJO_FRAGMENTO) :].strip(), resto
    return "", contenido
