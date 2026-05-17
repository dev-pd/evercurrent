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
  phase: z.string(),
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

export const documentSchema = z.object({
  id: z.string().uuid(),
  project_id: z.string().uuid(),
  kind: z.string(),
  title: z.string(),
  phases: z.array(z.string()),
  body_excerpt: z.string(),
  chars: z.number().int(),
});
export type Document = z.infer<typeof documentSchema>;

export const jobStatusSchema = z.object({
  job_id: z.string(),
  status: z.string(),
  result: z.record(z.unknown()).nullable().optional(),
  enqueue_time: z.string().nullable().optional(),
  start_time: z.string().nullable().optional(),
  finish_time: z.string().nullable().optional(),
});
export type JobStatus = z.infer<typeof jobStatusSchema>;

export const todaySchema = z.object({
  project_id: z.string().uuid(),
  live_day: z.number().int(),
  live_date: z.string(),
  start_date: z.string(),
  phase: z.string(),
  phase_concerns: z.array(z.string()),
  message_count: z.number().int(),
  last_message_at: z.string().nullable(),
  last_digest_generated_at: z.string().nullable(),
});
export type Today = z.infer<typeof todaySchema>;

export type AgentEventType = "text_delta" | "tool_use_start" | "tool_use_result" | "done" | "close";

export interface AgentEvent {
  type: AgentEventType;
  data: Record<string, unknown>;
}
