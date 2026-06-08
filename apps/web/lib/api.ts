import { z } from "zod";
import {
  cardListItemSchema,
  cardResponseSchema,
  digestV2Schema,
  meSchema,
  regenerateResponseSchema,
  cardFeedbackResponseSchema,
  todayV2Schema,
  type CardListItem,
  type CardResponse,
  type DigestV2,
  type Me,
  type RegenerateResponse,
  type CardFeedbackResponse,
  type TodayV2,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
  me(): Promise<Me>;
  getToday(projectId: string): Promise<TodayV2>;
  getDigestToday(): Promise<DigestV2>;
  regenerateDigest(): Promise<RegenerateResponse>;
  listCards(filters?: CardFilters): Promise<CardListItem[]>;
  getCard(id: string): Promise<CardResponse>;
  feedbackCard(id: string, useful: boolean): Promise<CardFeedbackResponse>;
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
  return {
    async me() {
      return apiFetch("/api/v1/me", meSchema, await getCtx());
    },
    async getToday(projectId) {
      return apiFetch(`/api/v1/projects/${projectId}/today`, todayV2Schema, await getCtx());
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
        { method: "POST", body: { useful } },
      );
    },
  };
}

export async function apiServer(): Promise<ApiClient> {
  return createClient(async () => {
    let token: string | null = null;
    try {
      const { auth0 } = await import("@/lib/auth0");
      const result = await auth0.getAccessToken();
      token = result?.token ?? null;
    } catch {
      token = null;
    }
    return { baseUrl: API_BASE_URL, token, pathPrefix: "" };
  });
}

export function apiBrowser(): ApiClient {
  return createClient(async () => ({
    baseUrl: "",
    token: null,
    pathPrefix: "/api/proxy",
  }));
}

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

export function getStreamUrl(projectId: string): string {
  return `${API_BASE_URL}/api/v1/events/stream?project_id=${encodeURIComponent(projectId)}`;
}
