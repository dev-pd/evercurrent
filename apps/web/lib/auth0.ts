import { Auth0Client } from "@auth0/nextjs-auth0/server";

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

function buildClient(): Auth0Client {
  return new Auth0Client({
    domain: required("AUTH0_DOMAIN"),
    clientId: required("AUTH0_CLIENT_ID"),
    clientSecret: required("AUTH0_CLIENT_SECRET"),
    secret: required("AUTH0_SECRET"),
    appBaseUrl: required("NEXT_PUBLIC_APP_URL"),
    routes: {
      login: "/api/auth/login",
      logout: "/api/auth/logout",
      callback: "/api/auth/callback",
      backChannelLogout: "/api/auth/backchannel-logout",
    },
    authorizationParameters: {
      scope: "openid profile email",
      audience: process.env.AUTH0_AUDIENCE || undefined,
    },
  });
}

let cached: Auth0Client | null = null;

export const auth0 = new Proxy({} as Auth0Client, {
  get(_target, prop) {
    cached ??= buildClient();
    const value = Reflect.get(cached as object, prop);
    return typeof value === "function" ? value.bind(cached) : value;
  },
});
