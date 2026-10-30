import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.infrastructure.adapters.input.http.auth_controller import create_auth_router
from app.infrastructure.adapters.input.http.clasificacion_controller import (
    create_clasificacion_router,
)
from app.infrastructure.adapters.input.http.context_controller import create_context_router
from app.infrastructure.adapters.input.http.health_controller import create_health_router
from app.infrastructure.adapters.input.http.knowledge_controller import create_knowledge_router
from app.infrastructure.adapters.input.http.query_controller import create_query_router
from app.infrastructure.adapters.input.http.riesgo_controller import create_riesgo_router
from app.infrastructure.adapters.input.http.weather_controller import create_weather_router
from app.infrastructure.composition import build_container

container = build_container()

app = FastAPI(
    title=container.settings.app_name,
    version="0.1.0",
    description="PMV1 - Sistema de asistencia técnica agrícola basado en IA",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=container.settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(create_health_router(container))
app.include_router(create_auth_router(container))
app.include_router(create_context_router(container))
app.include_router(create_query_router(container))
app.include_router(create_knowledge_router(container))
app.include_router(create_weather_router(container))
app.include_router(create_clasificacion_router(container))
app.include_router(create_riesgo_router(container))


def host_de_escucha() -> str:
    """Producción escucha en todas las interfaces. El desarrollo local puede fijar otra."""
    return "0.0.0.0"


def puerto_de_escucha(environ: dict[str, str] | None = None) -> int:
    """Usa PORT y, si no existe, el 8000 del entorno local."""
    env = environ if environ is not None else os.environ
    bruto = str(env.get("PORT", "")).strip() or "8000"
    try:
        puerto = int(bruto)
    except ValueError as error:
        raise ValueError("PORT debe ser un entero entre 1 y 65535") from error
    if puerto < 1 or puerto > 65535:
        raise ValueError("PORT debe ser un entero entre 1 y 65535")
    return puerto


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=host_de_escucha(),
        port=puerto_de_escucha(),
        reload=False,
    )
