from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.infrastructure.config.settings import Settings, get_settings


class Base(DeclarativeBase):
    """Declarative base de SQLAlchemy. Solo debe usarse en infraestructura MySQL."""


def create_mysql_engine(settings: Settings | None = None) -> Engine:
    current = settings or get_settings()
    connect_args = {"connect_timeout": 3}
    if current.mysql_port == 4000 or current.mysql_host and ".tidbcloud.com" in current.mysql_host:
        connect_args.update({
            "ssl": {
                "ca": current.mysql_ssl_ca_path or None,
                "verify_cert": current.mysql_ssl_verify_cert,
                "verify_identity": current.mysql_ssl_verify_identity,
            }
        })
    return create_engine(
        current.mysql_url,
        pool_pre_ping=True,
        future=True,
        connect_args=connect_args,
    )


def create_session_factory(settings: Settings | None = None) -> sessionmaker:
    engine = create_mysql_engine(settings)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def ping_mysql(settings: Settings | None = None) -> bool:
    try:
        engine = create_mysql_engine(settings)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except (SQLAlchemyError, OSError):
        return False


def id_a_entero(valor: str | int) -> int:
    return int(str(valor).strip())


def id_a_dominio(valor: int | str) -> str:
    return str(valor)
