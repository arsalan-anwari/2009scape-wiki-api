from wiki_api.surfaces.http.routes.discovery import router as discovery_router
from wiki_api.surfaces.http.routes.entities import router as entities_router
from wiki_api.surfaces.http.routes.meta import router as meta_router

__all__ = ["discovery_router", "entities_router", "meta_router"]
