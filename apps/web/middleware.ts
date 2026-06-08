import { NextResponse, type NextRequest } from "next/server";
import { auth0 } from "@/lib/auth0";

const PUBLIC_PATHS = new Set<string>(["/"]);

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_PATHS.has(pathname)) {
    return true;
  }
  if (pathname.startsWith("/api/auth/")) {
    return true;
  }
  return false;
}

export async function middleware(request: NextRequest) {
  const authResponse = await auth0.middleware(request);

  if (request.nextUrl.pathname.startsWith("/api/auth/")) {
    return authResponse;
  }

  if (isPublicPath(request.nextUrl.pathname)) {
    return authResponse;
  }

  const session = await auth0.getSession(request);
  if (!session) {
    const loginUrl = new URL("/api/auth/login", request.nextUrl.origin);
    loginUrl.searchParams.set("returnTo", request.nextUrl.pathname + request.nextUrl.search);
    return NextResponse.redirect(loginUrl);
  }

  return authResponse;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
