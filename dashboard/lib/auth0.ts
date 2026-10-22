import { Auth0Client } from "@auth0/nextjs-auth0/server";

const audience = process.env.AUTH0_API_AUDIENCE;

export const auth0 = new Auth0Client({
  authorizationParameters: audience
    ? { audience, scope: "openid profile email" }
    : { scope: "openid profile email" },
  // The browser uses same-origin command routes only. It never receives a backend token.
  enableAccessTokenEndpoint: false,
});
