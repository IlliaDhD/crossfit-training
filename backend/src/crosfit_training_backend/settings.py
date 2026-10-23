from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Settings:
    LOG_LEVEL: str

    # Keycloak
    KEYCLOAK_URL: str
    KEYCLOAK_REALM: str
    KEYCLOAK_CLIENT_ID: str
    KEYCLOAK_AUDIENCE: str
    KEYCLOAK_ADMIN_ROLE: str

    # MongoDB
    MONGO_URL: str
    MONGO_DB_NAME: str

    # CORS: origins of the browser frontend (comma-separated in the env variable)
    CORS_ORIGINS: tuple[str, ...]

    @property
    def KEYCLOAK_JWKS_URL(self) -> str:
        return (
            f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}"
            "/protocol/openid-connect/certs"
        )

    @property
    def KEYCLOAK_ISSUER(self) -> str:
        return f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings

    if _settings is None:
        _settings = Settings(
            LOG_LEVEL=getenv("LOG_LEVEL", "INFO"),
            KEYCLOAK_URL=getenv("KEYCLOAK_URL", ""),
            KEYCLOAK_REALM=getenv("KEYCLOAK_REALM", ""),
            KEYCLOAK_CLIENT_ID=getenv("KEYCLOAK_CLIENT_ID", ""),
            KEYCLOAK_AUDIENCE=getenv("KEYCLOAK_AUDIENCE", "crossfit-api"),
            KEYCLOAK_ADMIN_ROLE=getenv("KEYCLOAK_ADMIN_ROLE_NAME", ""),
            MONGO_URL=getenv("MONGO_URL", "mongodb://localhost:27017"),
            MONGO_DB_NAME=getenv("MONGO_DB_NAME", "crossfit"),
            CORS_ORIGINS=tuple(
                origin.strip()
                for origin in getenv("CORS_ORIGINS", "http://localhost:4200").split(",")
                if origin.strip()
            ),
        )

    return _settings
