// TODO: move to an environment variable (same as the Keycloak url in app.config.ts)
export const API_URL = 'http://localhost:8000';

/** Role that may create exercises (must match KEYCLOAK_ADMIN_ROLE_NAME on the backend). */
export const ADMIN_ROLE = 'coach';

/** Regex for the Keycloak bearer interceptor: the token is sent only to our API. */
export const API_URL_PATTERN = new RegExp(
  '^' + API_URL.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(/.*)?$',
  'i',
);
