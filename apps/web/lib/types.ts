import { z } from "zod";

export const projectSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  current_phase: z.string(),
  current_day: z.number().int(),
  phase_concerns: z.record(z.array(z.string())),
  milestones: z.array(z.record(z.string())),
});
export type Project = z.infer<typeof projectSchema>;

export const userSchema = z.object({
  id: z.string().uuid(),
  project_id: z.string().uuid(),
  username: z.string(),
  display_name: z.string(),
  role: z.string(),
  owned_subsystems: z.array(z.string()),
  owned_parts: z.array(z.string()),
  topic_weights: z.record(z.number()),
});
export type User = z.infer<typeof userSchema>;

export const digestItemSchema = z.object({
  id: z.string().uuid(),
  channel: z.string(),
  author_username: z.string(),
  author_display_name: z.string(),
  day: z.number().int(),
  ts: z.string(),
  text: z.string(),
  topic: z.string().nullable().optional(),
  urgency: z.string().nullable().optional(),
});
export type DigestItem = z.infer<typeof digestItemSchema>;

export const digestSchema = z.object({
  id: z.string().uuid(),
  user_id: z.string().uuid(),
  day: z.number().int(),
  content_md: z.string(),
  item_message_ids: z.array(z.string().uuid()),
  items: z.array(digestItemSchema),
  generated_at: z.string(),
});
export type Digest = z.infer<typeof digestSchema>;

export const decisionSchema = z.object({
  id: z.string().uuid(),
  summary: z.string(),
  rationale: z.string().nullable(),
  decided_by: z.string(),
  decided_at: z.string(),
  source_message_ids: z.array(z.string().uuid()),
  affected_subsystems: z.array(z.string()),
  status: z.string(),
  confidence: z.number(),
});
export type Decision = z.infer<typeof decisionSchema>;

export const generateDigestsSchema = z.object({
  job_id: z.string(),
  day: z.number().int(),
});
export type GenerateDigestsResponse = z.infer<typeof generateDigestsSchema>;

export const feedbackResponseSchema = z.object({
  user_id: z.string().uuid(),
  topic_weights: z.record(z.number()),
});
export type FeedbackResponse = z.infer<typeof feedbackResponseSchema>;

export type AgentEventType = "text_delta" | "tool_use_start" | "tool_use_result" | "done" | "close";

export interface AgentEvent {
  type: AgentEventType;
  data: Record<string, unknown>;
}
