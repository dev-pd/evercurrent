/* Backend API client. Adds the X-Impersonate-User header on every request
   based on the Zustand impersonation store so the backend can personalise. */

import { useImpersonationStore } from "@/stores/impersonation";
import {
  type Decision,
  decisionSchema,
  type Digest,
  digestSchema,
  type FeedbackResponse,
  feedbackResponseSchema,
  type GenerateDigestsResponse,
  generateDigestsSchema,
  type Project,
  projectSchema,
  type User,
  userSchema,
} from "@/lib/types";
import { z } from "zod";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api";

async function request<T>(path: string, init?: RequestInit, schema?: z.ZodSchema<T>): Promise<T> {
  const userId =
    typeof window !== "undefined" ? useImpersonationStore.getState().currentUserId : null;
  const headers = new Headers(init?.headers);
  if (userId) headers.set("X-Impersonate-User", userId);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }
  const data: unknown = await response.json();
  return schema ? schema.parse(data) : (data as T);
}

export const api = {
  async listProjects(): Promise<Project[]> {
    return request("/projects", undefined, z.array(projectSchema));
  },
  async getProject(id: string): Promise<Project> {
    return request(`/projects/${id}`, undefined, projectSchema);
  },
  async changePhase(id: string, phase: string): Promise<Project> {
    return request(
      `/projects/${id}/phase`,
      { method: "POST", body: JSON.stringify({ phase }) },
      projectSchema,
    );
  },
  async listUsers(projectId: string): Promise<User[]> {
    return request(`/users?project_id=${projectId}`, undefined, z.array(userSchema));
  },
  async getDigest(userId: string, day: number): Promise<Digest> {
    return request(`/digests/${userId}?day=${day}`, undefined, digestSchema);
  },
  async generateDigests(projectId: string, day: number): Promise<GenerateDigestsResponse> {
    return request(
      `/digests/generate?day=${day}&project_id=${projectId}`,
      { method: "POST" },
      generateDigestsSchema,
    );
  },
  async postFeedback(args: {
    userId: string;
    messageId: string;
    signal: 1 | -1;
    topic?: string;
  }): Promise<FeedbackResponse> {
    return request(
      "/feedback",
      {
        method: "POST",
        body: JSON.stringify({
          user_id: args.userId,
          message_id: args.messageId,
          signal: args.signal,
          topic: args.topic,
        }),
      },
      feedbackResponseSchema,
    );
  },
  async listDecisions(_projectId: string): Promise<Decision[]> {
    return request("/decisions", undefined, z.array(decisionSchema));
  },
  agentChatUrl(projectId: string): string {
    return `${BASE_URL}/agent/chat?project_id=${projectId}`;
  },
};
