import { z } from "zod";
import {
  cardListItemSchema,
  cardResponseSchema,
  digestV2Schema,
  focusTopicSchema,
  memberSummarySchema,
  projectSchema,
  regenerateResponseSchema,
  cardFeedbackResponseSchema,
  proactiveInsightSchema,
  timelineSchema,
  todayV2Schema,
  type CardListItem,
  type CardResponse,
  type DigestV2,
  type FocusTopic,
  type MemberSummary,
  type Project,
  type ProactiveInsight,
  type RegenerateResponse,
  type CardFeedbackResponse,
  type Timeline,
  type TodayV2,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Server components run inside the web container and must reach the API by its
// absolute internal URL. NEXT_PUBLIC_API_URL is browser-facing (e.g. "/api"
// behind nginx) and is relative — useless for server-side fetch().
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
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const rewritten = ctx.pathPrefix
    ? path.replace(/^\/api\/v1/, ctx.pathPrefix)
    : path;

  const response = await fetch(`${ctx.baseUrl}${rewritten}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
    cache: "no-store",
  });

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
  listMembers(): Promise<MemberSummary[]>;
  getFocus(): Promise<FocusTopic[]>;
  focusSignal(topic: string, delta: number): Promise<FocusTopic[]>;
  listProjects(): Promise<Project[]>;
  getToday(projectId: string): Promise<TodayV2>;
  getDigestToday(): Promise<DigestV2>;
  regenerateDigest(): Promise<RegenerateResponse>;
  listCards(filters?: CardFilters): Promise<CardListItem[]>;
  getCard(id: string): Promise<CardResponse>;
  feedbackCard(id: string, useful: boolean): Promise<CardFeedbackResponse>;
  getInsights(limit?: number): Promise<ProactiveInsight[]>;
  getTimeline(projectId: string): Promise<Timeline>;
}

export interface CardFilters {
  projectId?: string;
  kind?: string;
  status?: string;
}

function buildCardQuery(filters?: CardFilters): string {
  if (!filters) return "";
  const params = new URLSearchParams();
  if (filters.projectId) params.set("project_id", filters.projectId);
  if (filters.kind) params.set("kind", filters.kind);
  if (filters.status) params.set("status", filters.status);
  const query = params.toString();
  return query ? `?${query}` : "";
}

function createClient(getCtx: () => Promise<FetchContext>): ApiClient {
  const cardListSchema = z.array(cardListItemSchema);
  const insightListSchema = z.array(proactiveInsightSchema);
  const projectListSchema = z.array(projectSchema);
  const memberListSchema = z.array(memberSummarySchema);
  const focusListSchema = z.array(focusTopicSchema);
  return {
    async listMembers() {
      return apiFetch("/api/v1/members", memberListSchema, await getCtx());
    },
    async getFocus() {
      return apiFetch("/api/v1/focus", focusListSchema, await getCtx());
    },
    async focusSignal(topic, delta) {
      return apiFetch("/api/v1/focus/signal", focusListSchema, await getCtx(), {
        method: "POST",
        body: { topic, delta },
      });
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
    async listCards(filters) {
      return apiFetch(`/api/v1/cards${buildCardQuery(filters)}`, cardListSchema, await getCtx());
    },
    async getCard(id) {
      return apiFetch(`/api/v1/cards/${id}`, cardResponseSchema, await getCtx());
    },
    async feedbackCard(id, useful) {
      return apiFetch(
        `/api/v1/cards/${id}/feedback`,
        cardFeedbackResponseSchema,
        await getCtx(),
        { method: "POST", body: { signal: useful ? 1 : -1 } },
      );
    },
    async getInsights(limit = 5) {
      return apiFetch(`/api/v1/insights?limit=${limit}`, insightListSchema, await getCtx());
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

export async function apiServer(impersonate?: string | null): Promise<ApiClient> {
  return createClient(async () => {
    let token: string | null = null;
    try {
      const { auth0 } = await import("@/lib/auth0");
      const result = await auth0.getAccessToken();
      token = result?.token ?? null;
    } catch {
      token = null;
    }
    return { baseUrl: INTERNAL_API_URL, token, pathPrefix: "", impersonate };
  });
}

export function apiBrowser(): ApiClient {
  return createClient(async () => {
    const impersonate =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("as")
        : null;
    return { baseUrl: "", token: null, pathPrefix: "/api/proxy", impersonate };
  });
}

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

export function getStreamUrl(projectId: string): string {
  // nginx routes /api/v1/events straight to the API with proxy_buffering off
  // (real SSE); the route is unauthenticated. Keep this relative so the
  // browser hits nginx, not the buffering Next.js proxy. Backend route is
  // /api/v1/events (no /stream suffix).
  return `/api/v1/events?project_id=${encodeURIComponent(projectId)}`;
}
