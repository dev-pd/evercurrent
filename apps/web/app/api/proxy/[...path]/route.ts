import { NextResponse, type NextRequest } from "next/server";
import { auth0 } from "@/lib/auth0";

const API_BASE_URL = process.env.INTERNAL_API_URL ?? "http://api:8000";

async function forward(request: NextRequest, segments: string[]): Promise<NextResponse> {
  const session = await auth0.getSession();
  if (!session?.user) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  let token: string | null = null;
  try {
    const result = await auth0.getAccessToken();
    token = result?.token ?? null;
  } catch {
    return NextResponse.json({ error: "no_access_token" }, { status: 401 });
  }

  const search = request.nextUrl.search;
  const url = `${API_BASE_URL}/api/v1/${segments.join("/")}${search}`;

  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers["Content-Type"] = contentType;
  }
  const impersonate = request.headers.get("x-impersonate-user");
  if (impersonate) {
    headers["X-Impersonate-User"] = impersonate;
  }
  if (session.user.sub) {
    headers["X-Auth-Sub"] = String(session.user.sub);
    headers["X-Auth-Email"] = String(session.user.email ?? "");
    headers["X-Auth-Name"] = String(session.user.name ?? session.user.email ?? "");
  }

  const body =
    request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer();

  const upstream = await fetch(url, {
    method: request.method,
    headers,
    body: body ? Buffer.from(body) : undefined,
    cache: "no-store",
    // @ts-expect-error: duplex required for fetch with streaming body in Node
    duplex: "half",
  });

  const responseBody = await upstream.text();
  return new NextResponse(responseBody, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/json",
    },
  });
}

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

export async function GET(request: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return forward(request, path);
}

export async function POST(request: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return forward(request, path);
}

export async function PATCH(request: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return forward(request, path);
}

export async function PUT(request: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return forward(request, path);
}

export async function DELETE(request: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return forward(request, path);
}
