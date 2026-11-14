import { ApplicationConfig } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import {
  provideKeycloak,
  withAutoRefreshToken,
  AutoRefreshTokenService,
  UserActivityService,
  createInterceptorCondition,
  IncludeBearerTokenCondition,
  includeBearerTokenInterceptor,
  INCLUDE_BEARER_TOKEN_INTERCEPTOR_CONFIG,
} from 'keycloak-angular';
import { API_URL_PATTERN } from './core/api.config';
import { routes } from './app.routes';

// the access token is added only to requests to our backend API
const apiCondition = createInterceptorCondition<IncludeBearerTokenCondition>({
  urlPattern: API_URL_PATTERN,
});

export const appConfig: ApplicationConfig = {
  providers: [
    provideKeycloak({
      config: {
        url: 'http://localhost:8080',  // chagne to env variable
        realm: 'crossfit',
        clientId: 'crossfit-frontend',
      },
      initOptions: {
        // неавторизованого користувача одразу перекидає на форму Keycloak
        onLoad: 'login-required',
        pkceMethod: 'S256',
        checkLoginIframe: false,
      },
      features: [
        withAutoRefreshToken({
          onInactivityTimeout: 'logout',
          sessionTimeout: 15 * 60 * 1000,
        }),
      ],
      providers: [AutoRefreshTokenService, UserActivityService],
    }),
    { provide: INCLUDE_BEARER_TOKEN_INTERCEPTOR_CONFIG, useValue: [apiCondition] },
    provideHttpClient(withInterceptors([includeBearerTokenInterceptor])),
    provideRouter(routes),
  ],
};
