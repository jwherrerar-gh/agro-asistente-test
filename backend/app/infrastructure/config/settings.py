from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "agro-asistente"
    app_env: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "agro_asistente"

    jwt_secret: str = "change-me-in-local-env-do-not-use-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120

    knowledge_dir: str = "../knowledge"

    chroma_persist_dir: str = "./chroma_data"
    chroma_collection: str = "agro_knowledge_pmv1"

    rag_top_k: int = 3
    rag_min_similarity: float = 0.12
    chunk_size: int = 500

    embedding_provider: str = "local"
    embedding_dimension: int = 128
    embedding_api_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""

    generation_provider: str = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:1.5b"
    ollama_timeout_seconds: int = 90

    senamhi_wis2_base_url: str = "https://wis.senamhi.gob.pe/oapi"
    senamhi_wis2_collection: str = "urn:wmo:md:pe-senamhi:synop-hourly"
    senamhi_wis2_timeout_seconds: int = 20

    cors_origins: str = "http://localhost:5173"

    # Clasificador experimental HU-07. 0.17 es el margen fijado en la validación de v2.
    clasificador_margen_minimo: float = 0.17
    clasificador_modelo_ruta: str = ""

    @field_validator("clasificador_margen_minimo")
    @classmethod
    def validar_margen_clasificador(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError(
                "CLASIFICADOR_MARGEN_MINIMO debe estar entre 0 y 1. "
                "El valor predeterminado es 0.17 y no se sustituye en silencio."
            )
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip() and "*" not in origin.strip()
        ]
        if not origins:
            return ["http://localhost:5173"]
        return origins

    @property
    def mysql_url(self) -> str:
        user = quote_plus((self.mysql_user or "").strip())
        password = quote_plus(self.mysql_password) if self.mysql_password else ""
        host = (self.mysql_host or "localhost").strip()
        database = (self.mysql_database or "").strip()
        if password:
            auth = f"{user}:{password}"
        else:
            auth = user
        return (
            f"mysql+pymysql://{auth}@{host}:{self.mysql_port}/"
            f"{database}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
