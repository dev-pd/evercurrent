import { z } from "zod";
import {
  signalPageSchema,
  signalResponseSchema,
  digestV2Schema,
  meSchema,
  memberSummarySchema,
  connectorSummarySchema,
  installResponseSchema,
  projectSchema,
  regenerateResponseSchema,
  proactiveInsightSchema,
  timelineSchema,
  todayV2Schema,
  type SignalPage,
  type SignalResponse,
  type DigestV2,
  type Me,
  type MemberSummary,
  type ConnectorSummary,
  type InstallResponse,
  type Project,
  type ProactiveInsight,
  type RegenerateResponse,
  type Timeline,
  type TodayV2,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL ?? "http://api:8000";

export class ApiError extends Error {
  status: number;
  body?: unknown;
  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE" | "PUT";
  body?: unknown;
  signal?: AbortSignal;
}

interface FetchContext {
  baseUrl: string;
  token: string | null;
  pathPrefix: string;
  impersonate?: string | null;
  authHeaders?: Record<string, string>;
}

async function apiFetch<T>(
  path: string,
  schema: z.ZodType<T>,
  ctx: FetchContext,
  options: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (ctx.token) {
    headers.Authorization = `Bearer ${ctx.token}`;
  }
  if (ctx.impersonate) {
    headers["X-Impersonate-User"] = ctx.impersonate;
  }
  if (ctx.authHeaders) {
    Object.assign(headers, ctx.authHeaders);
  }
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const rewritten = ctx.pathPrefix ? path.replace(/^\/api\/v1/, ctx.pathPrefix) : path;

  // Default timeout so a hanging upstream never blocks a server render forever.
  const timeoutCtrl = options.signal ? null : new AbortController();
  const timeoutId = timeoutCtrl ? setTimeout(() => timeoutCtrl.abort(), 12_000) : null;

  let response: Response;
  try {
    response = await fetch(`${ctx.baseUrl}${rewritten}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: options.signal ?? timeoutCtrl?.signal,
      cache: "no-store",
    });
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }

  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = await response.text().catch(() => undefined);
    }
    throw new ApiError(
      `API ${options.method ?? "GET"} ${path} failed with ${response.status}`,
      response.status,
      body,
    );
  }

  const json = (await response.json()) as unknown;
  return schema.parse(json);
}

export interface ApiClient {
  getMe(): Promise<Me>;
  listMembers(): Promise<MemberSummary[]>;
  listConnectors(): Promise<ConnectorSummary[]>;
  startInstall(kind: "slack" | "dropbox"): Promise<InstallResponse>;
  syncSlack(connectorId: string): Promise<{ status: string; connector_id: string }>;
  disconnect(connectorId: string): Promise<{ status: string; kind: string }>;
  listProjects(): Promise<Project[]>;
  getToday(projectId: string): Promise<TodayV2>;
  getDigestToday(): Promise<DigestV2>;
  regenerateDigest(): Promise<RegenerateResponse>;
  listSignals(filters?: SignalFilters): Promise<SignalPage>;
  getSignal(id: string): Promise<SignalResponse>;
  getInsights(limit?: number): Promise<ProactiveInsight[]>;
  generateInsight(): Promise<{ status: string; project_id: string }>;
  getTimeline(projectId: string): Promise<Timeline>;
}

export interface SignalFilters {
  projectId?: string;
  kind?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

function buildSignalQuery(filters?: SignalFilters): string {
  if (!filters) return "";
  const params = new URLSearchParams();
  if (filters.projectId) params.set("project_id", filters.projectId);
  if (filters.kind) params.set("kind", filters.kind);
  if (filters.status) params.set("status", filters.status);
  if (filters.limit) params.set("limit", String(filters.limit));
  if (filters.offset) params.set("offset", String(filters.offset));
  const query = params.toString();
  return query ? `?${query}` : "";
}

function createClient(getCtx: () => Promise<FetchContext>): ApiClient {
  const insightListSchema = z.array(proactiveInsightSchema);
  const projectListSchema = z.array(projectSchema);
  const memberListSchema = z.array(memberSummarySchema);
  return {
    async getMe() {
      return apiFetch("/api/v1/me", meSchema, await getCtx());
    },
    async listMembers() {
      return apiFetch("/api/v1/members", memberListSchema, await getCtx());
    },
    async listConnectors() {
      return apiFetch("/api/v1/connectors", z.array(connectorSummarySchema), await getCtx());
    },
    async startInstall(kind) {
      return apiFetch(`/api/v1/connectors/${kind}/install`, installResponseSchema, await getCtx(), {
        method: "POST",
      });
    },
    async syncSlack(connectorId) {
      return apiFetch(
        `/api/v1/connectors/${connectorId}/slack/sync`,
        z.object({ status: z.string(), connector_id: z.string() }),
        await getCtx(),
        { method: "POST" },
      );
    },
    async disconnect(connectorId) {
      return apiFetch(
        `/api/v1/connectors/${connectorId}`,
        z.object({ status: z.string(), kind: z.string() }),
        await getCtx(),
        { method: "DELETE" },
      );
    },
    async listProjects() {
      return apiFetch("/api/v1/projects", projectListSchema, await getCtx());
    },
    async getToday(projectId) {
      return apiFetch(
        `/api/v1/today?project_id=${encodeURIComponent(projectId)}`,
        todayV2Schema,
        await getCtx(),
      );
    },
    async getDigestToday() {
      return apiFetch("/api/v1/digests/today", digestV2Schema, await getCtx());
    },
    async regenerateDigest() {
      return apiFetch("/api/v1/digests/regenerate", regenerateResponseSchema, await getCtx(), {
        method: "POST",
        body: {},
      });
    },
    async listSignals(filters) {
      return apiFetch(
        `/api/v1/signals${buildSignalQuery(filters)}`,
        signalPageSchema,
        await getCtx(),
      );
    },
    async getSignal(id) {
      return apiFetch(`/api/v1/signals/${id}`, signalResponseSchema, await getCtx());
    },
    async getInsights(limit = 5) {
      return apiFetch(`/api/v1/insights?limit=${limit}`, insightListSchema, await getCtx());
    },
    async generateInsight() {
      return apiFetch(
        `/api/v1/insights/generate`,
        z.object({ status: z.string(), project_id: z.string() }),
        await getCtx(),
        { method: "POST" },
      );
    },
    async getTimeline(projectId) {
      return apiFetch(
        `/api/v1/timeline/${encodeURIComponent(projectId)}`,
        timelineSchema,
        await getCtx(),
      );
    },
  };
}

export const VIEW_AS_COOKIE = "view_as";

export async function apiServer(impersonateOverride?: string | null | false): Promise<ApiClient> {
  // Resolve auth + impersonation ONCE per render, not per fetch — otherwise a
  // page firing N fetches makes N Auth0 getAccessToken round-trips (slow).
  let token: string | null = null;
  let authHeaders: Record<string, string> | undefined;
  try {
    const { auth0 } = await import("@/lib/auth0");
    const result = await auth0.getAccessToken();
    token = result?.token ?? null;
    const session = await auth0.getSession();
    const user = session?.user;
    if (user?.sub) {
      authHeaders = {
        "X-Auth-Sub": String(user.sub),
        "X-Auth-Email": String(user.email ?? ""),
        "X-Auth-Name": String(user.name ?? user.email ?? ""),
      };
    }
  } catch {
    token = null;
  }

  let impersonate: string | null = null;
  if (impersonateOverride === false) {
    impersonate = null;
  } else if (typeof impersonateOverride === "string") {
    impersonate = impersonateOverride;
  } else {
    const { cookies } = await import("next/headers");
    impersonate = (await cookies()).get(VIEW_AS_COOKIE)?.value ?? null;
  }

  const ctx: FetchContext = {
    baseUrl: INTERNAL_API_URL,
    token,
    pathPrefix: "",
    impersonate,
    authHeaders,
  };
  return createClient(async () => ctx);
}

// Admin context — never impersonates the viewed member (Settings uses this).
export function apiServerAdmin(): Promise<ApiClient> {
  return apiServer(false);
}

function readViewAsCookie(): string | null {
  if (typeof document === "undefined") return null;
  const hit = document.cookie.split("; ").find((entry) => entry.startsWith(`${VIEW_AS_COOKIE}=`));
  return hit ? decodeURIComponent(hit.split("=")[1]) : null;
}

export function apiBrowser(): ApiClient {
  return createClient(async () => {
    return { baseUrl: "", token: null, pathPrefix: "/api/proxy", impersonate: readViewAsCookie() };
  });
}

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

export function getStreamUrl(projectId: string): string {
  return `/api/v1/events?project_id=${encodeURIComponent(projectId)}`;
}
