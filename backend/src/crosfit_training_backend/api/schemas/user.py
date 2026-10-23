from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class AuthUser(BaseModel):
    """The authenticated user. There is no users collection: identity is the token."""

    model_config = ConfigDict(frozen=True)

    user_id: UUID = Field(description="Keycloak `sub`; used as `user_id` in documents")
    username: str | None = None
    roles: frozenset[str] = frozenset()

    @field_serializer("roles")
    def _serialize_roles(self, roles: frozenset[str]) -> list[str]:
        return sorted(roles)


class Roles(BaseModel):
    roles: list[str] = Field(default_factory=list)


class TokenClaims(BaseModel):
    """Access token claims we rely on. Everything else is ignored."""

    model_config = ConfigDict(extra="ignore")

    sub: UUID
    preferred_username: str | None = None
    realm_access: Roles = Field(default_factory=Roles)
    resource_access: dict[str, Roles] = Field(default_factory=dict)

    def to_user(self, client_id: str | None = None) -> AuthUser:
        """Realm roles plus the roles of the client `client_id`."""
        roles = set(self.realm_access.roles)
        if client_id and client_id in self.resource_access:
            roles |= set(self.resource_access[client_id].roles)
        return AuthUser(
            user_id=self.sub,
            username=self.preferred_username,
            roles=frozenset(roles),
        )
