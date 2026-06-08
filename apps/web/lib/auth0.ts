import { Auth0Client } from "@auth0/nextjs-auth0/server";

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export const auth0 = new Auth0Client({
  domain: required("AUTH0_DOMAIN"),
  clientId: required("AUTH0_CLIENT_ID"),
  clientSecret: required("AUTH0_CLIENT_SECRET"),
  secret: required("AUTH0_SECRET"),
  appBaseUrl: required("NEXT_PUBLIC_APP_URL"),
  authorizationParameters: {
    scope: "openid profile email",
    audience: process.env.AUTH0_AUDIENCE,
  },
});
