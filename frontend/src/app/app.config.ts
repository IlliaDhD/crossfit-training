import { ApplicationConfig } from '@angular/core';
import { provideRouter } from '@angular/router';
import {
  provideKeycloak,
  withAutoRefreshToken,
  AutoRefreshTokenService,
  UserActivityService,
} from 'keycloak-angular';
import { routes } from './app.routes';

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
    provideRouter(routes),
  ],
};
