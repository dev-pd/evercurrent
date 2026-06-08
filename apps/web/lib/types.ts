import { z } from "zod";

export const projectSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  current_phase: z.string(),
  current_day: z.number().int(),
  phase_concerns: z.record(z.string(), z.array(z.string())),
  milestones: z.array(z.record(z.string(), z.string())),
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
  topic_weights: z.record(z.string(), z.number()),
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
  topic_weights: z.record(z.string(), z.number()),
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
  result: z.record(z.string(), z.unknown()).nullable().optional(),
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

export const meSchema = z.object({
  membership_id: z.string().uuid(),
  org_id: z.string().uuid(),
  auth0_user_id: z.string(),
  email: z.string(),
  display_name: z.string(),
});
export type Me = z.infer<typeof meSchema>;

export const todayV2Schema = z.object({
  project_id: z.string().uuid(),
  live_day: z.number().int(),
  phase: z.string(),
  phase_concerns: z.array(z.string()),
  message_count_24h: z.number().int(),
  last_digest_at: z.string().nullable(),
  top_priority_count: z.number().int(),
});
export type TodayV2 = z.infer<typeof todayV2Schema>;

export const cardSourceSchema = z.object({
  id: z.string().uuid(),
  kind: z.string(),
  channel: z.string().nullable().optional(),
  author_display_name: z.string().nullable().optional(),
  author_username: z.string().nullable().optional(),
  ts: z.string().nullable().optional(),
  text: z.string(),
  url: z.string().nullable().optional(),
});
export type CardSource = z.infer<typeof cardSourceSchema>;

export const cardActivitySchema = z.object({
  id: z.string().uuid(),
  at: z.string(),
  actor: z.string().nullable().optional(),
  kind: z.string(),
  description: z.string(),
});
export type CardActivity = z.infer<typeof cardActivitySchema>;

export const cardEdgeSchema = z.object({
  id: z.string().uuid(),
  kind: z.string(),
  target_card_id: z.string().uuid().nullable().optional(),
  target_label: z.string(),
});
export type CardEdge = z.infer<typeof cardEdgeSchema>;

export const cardListItemSchema = z.object({
  id: z.string().uuid(),
  kind: z.string(),
  summary: z.string(),
  status: z.string(),
  sources_count: z.number().int(),
  edges_count: z.number().int(),
  confidence: z.number().nullable().optional(),
  decided_at: z.string().nullable().optional(),
  updated_at: z.string(),
});
export type CardListItem = z.infer<typeof cardListItemSchema>;

export const cardResponseSchema = z.object({
  id: z.string().uuid(),
  kind: z.string(),
  summary: z.string(),
  body: z.string().nullable(),
  status: z.string(),
  confidence: z.number().nullable().optional(),
  decided_at: z.string().nullable().optional(),
  updated_at: z.string(),
  sources: z.array(cardSourceSchema),
  edges: z.array(cardEdgeSchema).default([]),
  activity: z.array(cardActivitySchema).default([]),
});
export type CardResponse = z.infer<typeof cardResponseSchema>;

export const digestItemV2Schema = z.object({
  id: z.string().uuid(),
  bucket: z.enum(["top_priority", "watch_outs", "fyi"]),
  source: z.string(),
  author_display_name: z.string().nullable().optional(),
  ts: z.string().nullable().optional(),
  why_this_matters: z.string(),
  card_id: z.string().uuid().nullable().optional(),
  message_id: z.string().uuid().nullable().optional(),
});
export type DigestItemV2 = z.infer<typeof digestItemV2Schema>;

export const digestAnomalySchema = z.object({
  id: z.string().uuid(),
  summary: z.string(),
  card_id: z.string().uuid().nullable().optional(),
});
export type DigestAnomaly = z.infer<typeof digestAnomalySchema>;

export const digestV2Schema = z.object({
  id: z.string().uuid(),
  day_index: z.number().int(),
  phase: z.string(),
  content_md: z.string(),
  items: z.array(digestItemV2Schema),
  anomalies: z.array(digestAnomalySchema).default([]),
  generated_at: z.string(),
  card_ids: z.array(z.string().uuid()).default([]),
  message_ids: z.array(z.string().uuid()).default([]),
});
export type DigestV2 = z.infer<typeof digestV2Schema>;

export const regenerateResponseSchema = z.object({
  job_id: z.string(),
});
export type RegenerateResponse = z.infer<typeof regenerateResponseSchema>;

export const cardFeedbackResponseSchema = z.object({
  ok: z.boolean(),
});
export type CardFeedbackResponse = z.infer<typeof cardFeedbackResponseSchema>;
