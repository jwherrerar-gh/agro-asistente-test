import json
from pathlib import Path

from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from app.domain.entities.documento_conocimiento import DocumentoConocimiento
from app.domain.exceptions import (
    ErrorArchivoConocimientoNoEncontrado,
    ErrorDocumentoConocimientoDuplicado,
)
from app.domain.ports.output.repositorio_documento_conocimiento_port import (
    PuertoRepositorioDocumentoConocimiento,
)
from app.domain.valueObjects.hash_contenido import HashContenido
from app.infrastructure.adapters.output.mysql.connection import (
    Base,
    id_a_dominio,
    id_a_entero,
)


class RegistroDocumentoConocimiento(Base):
    __tablename__ = "documentos_conocimiento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ruta_origen: Mapped[str] = mapped_column(String(500), nullable=False)
    hash_contenido: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    fecha_creacion: Mapped[object] = mapped_column(DateTime, nullable=True)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)


class RepositorioDocumentoConocimientoMysql(PuertoRepositorioDocumentoConocimiento):
    def __init__(self, session_factory: sessionmaker, knowledge_dir: str) -> None:
        self._session_factory = session_factory
        self._directorio_conocimiento = Path(knowledge_dir)

    def existe_por_hash(self, hash_contenido: HashContenido) -> bool:
        with self._session_factory() as session:
            documento_id = session.scalar(
                select(RegistroDocumentoConocimiento.id).where(
                    RegistroDocumentoConocimiento.hash_contenido == hash_contenido.value
                )
            )
            return documento_id is not None

    def guardar(self, documento: DocumentoConocimiento, contenido: str) -> None:
        registro = RegistroDocumentoConocimiento(
            ruta_origen=documento.ruta_origen[:500],
            hash_contenido=documento.hash_contenido.value,
            fecha_creacion=documento.incorporado_en,
            contenido=contenido,
        )
        with self._session_factory() as session:
            session.add(registro)
            try:
                session.flush()
                documento.id = id_a_dominio(registro.id)
                session.commit()
            except IntegrityError as error:
                session.rollback()
                raise ErrorDocumentoConocimientoDuplicado(
                    "El documento de conocimiento ya está registrado"
                ) from error

    def listar_todos(self) -> list[DocumentoConocimiento]:
        with self._session_factory() as session:
            registros = session.scalars(
                select(RegistroDocumentoConocimiento).order_by(
                    RegistroDocumentoConocimiento.fecha_creacion.desc()
                )
            ).all()
            return [self._a_entidad(registro) for registro in registros]

    def buscar_por_id(self, documento_id: str) -> DocumentoConocimiento | None:
        with self._session_factory() as session:
            registro = session.scalar(
                select(RegistroDocumentoConocimiento).where(
                    RegistroDocumentoConocimiento.id == id_a_entero(documento_id)
                )
            )
            if registro is None:
                return None
            return self._a_entidad(registro)

    def leer_contenido(self, documento: DocumentoConocimiento) -> str:
        with self._session_factory() as session:
            registro = session.scalar(
                select(RegistroDocumentoConocimiento).where(
                    RegistroDocumentoConocimiento.id == id_a_entero(documento.id)
                )
            )
            if registro is None:
                raise ErrorArchivoConocimientoNoEncontrado(
                    "No se encontró el archivo del documento de conocimiento"
                )
            contenido = registro.contenido
            if isinstance(contenido, bytes):
                return contenido.decode("utf-8")
            return str(contenido)

    def actualizar_cantidad_fragmentos(self, documento_id: str, cantidad_fragmentos: int) -> None:
        with self._session_factory() as session:
            registro = session.scalar(
                select(RegistroDocumentoConocimiento).where(
                    RegistroDocumentoConocimiento.id == id_a_entero(documento_id)
                )
            )
            if registro is None:
                return
            meta = _leer_meta(self._ruta_meta(registro.ruta_origen))
            _escribir_meta(
                self._ruta_meta(registro.ruta_origen),
                titulo=str(meta.get("title") or ""),
                tema=str(meta.get("topic") or ""),
                cantidad_fragmentos=cantidad_fragmentos,
            )

    def _ruta_archivo(self, ruta_origen: str) -> Path:
        nombre_archivo = Path(ruta_origen).name
        return self._directorio_conocimiento / nombre_archivo

    def _ruta_meta(self, ruta_origen: str) -> Path:
        return self._ruta_archivo(ruta_origen).with_suffix(".meta.json")

    def _a_entidad(self, registro: RegistroDocumentoConocimiento) -> DocumentoConocimiento:
        meta = _leer_meta(self._ruta_meta(registro.ruta_origen))
        return DocumentoConocimiento(
            documento_id=id_a_dominio(registro.id),
            titulo=str(meta.get("title") or ""),
            ruta_origen=registro.ruta_origen,
            tema=str(meta.get("topic") or ""),
            hash_contenido=HashContenido(registro.hash_contenido),
            cantidad_fragmentos=int(meta.get("chunk_count") or 0),
            incorporado_en=registro.fecha_creacion,
        )


def _escribir_meta(ruta: Path, titulo: str, tema: str, cantidad_fragmentos: int) -> None:
    ruta.write_text(
        json.dumps(
            {"title": titulo, "topic": tema, "chunk_count": cantidad_fragmentos},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _leer_meta(ruta: Path) -> dict[str, object]:
    if not ruta.exists():
        return {}
    try:
        loaded = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}
