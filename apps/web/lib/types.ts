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

export const meSchema = z.object({
  membership_id: z.string().uuid(),
  org_id: z.string().uuid(),
  org_name: z.string(),
  branding: z.record(z.string(), z.string()).default({}),
  role: z.string().default("member"),
  auth0_user_id: z.string(),
  email: z.string(),
  display_name: z.string(),
});
export type Me = z.infer<typeof meSchema>;

export const todayV2Schema = z.object({
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
  edges_count: z.number().int().default(0),
  confidence: z.number().nullable().optional(),
  decided_at: z.string().nullable().optional(),
  occurred_at: z.string().nullable().optional(),
  affected_subsystems: z.array(z.string()).default([]),
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

export const digestV2Schema = z.object({
  id: z.string().uuid(),
  day_index: z.number().int(),
  phase: z.string(),
  content_md: z.string(),
  items: z.array(digestItemV2Schema),
  generated_at: z.string(),
  card_ids: z.array(z.string().uuid()).default([]),
  message_ids: z.array(z.string().uuid()).default([]),
});
export type DigestV2 = z.infer<typeof digestV2Schema>;

export const regenerateResponseSchema = z.object({
  job_id: z.string(),
});
export type RegenerateResponse = z.infer<typeof regenerateResponseSchema>;

export const focusTopicSchema = z.object({
  topic: z.string(),
  label: z.string(),
  weight: z.number(),
  sources: z.array(z.enum(["role", "phase", "learned"])),
  trend: z.enum(["up", "flat", "down"]),
});
export type FocusTopic = z.infer<typeof focusTopicSchema>;

export const memberSummarySchema = z.object({
  id: z.string().uuid(),
  display_name: z.string(),
  eng_role: z.string().nullable(),
  owned_subsystems: z.array(z.string()),
});
export type MemberSummary = z.infer<typeof memberSummarySchema>;

export const connectorSummarySchema = z.object({
  id: z.string().uuid(),
  kind: z.string(),
  status: z.string(),
  external_team_id: z.string().nullable(),
  channels_count: z.number().int(),
  message_count: z.number().int(),
});
export type ConnectorSummary = z.infer<typeof connectorSummarySchema>;

export const installResponseSchema = z.object({ redirect_url: z.string() });
export type InstallResponse = z.infer<typeof installResponseSchema>;

export const specSnapshotSchema = z.object({
  label: z.string(),
  value: z.string(),
});
export type SpecSnapshot = z.infer<typeof specSnapshotSchema>;

export const insightConflictSchema = z.object({
  subsystem: z.string(),
  severity: z.enum(["info", "warn", "critical"]),
  title: z.string(),
  detail: z.string(),
  impact: z.string(),
});
export type InsightConflict = z.infer<typeof insightConflictSchema>;

export const insightSourceSchema = z.object({
  kind: z.enum(["slack", "doc"]),
  channel: z.string().nullable(),
  author: z.string().nullable(),
  snippet: z.string(),
  ts: z.string().nullable(),
});
export type InsightSource = z.infer<typeof insightSourceSchema>;

export const suggestedActionSchema = z.object({
  label: z.string(),
  invitees: z.array(z.string()),
  description: z.string(),
});
export type SuggestedAction = z.infer<typeof suggestedActionSchema>;

export const proactiveInsightSchema = z.object({
  id: z.string(),
  req_id: z.string(),
  title: z.string(),
  detected_at: z.string(),
  summary: z.string(),
  before: z.array(specSnapshotSchema),
  after: z.array(specSnapshotSchema),
  affected_subsystems: z.array(z.string()),
  conflicts: z.array(insightConflictSchema),
  sources: z.array(insightSourceSchema),
  suggested_action: suggestedActionSchema,
  impact_summary: z.record(z.string(), z.string()),
});
export type ProactiveInsight = z.infer<typeof proactiveInsightSchema>;

export const timelinePhaseSchema = z.object({
  label: z.string(),
  start_month: z.number(),
  end_month: z.number(),
  status: z.enum(["done", "active", "upcoming"]),
});
export type TimelinePhase = z.infer<typeof timelinePhaseSchema>;

export const timelineLaneSegmentSchema = z.object({
  start: z.number(),
  end: z.number(),
  tone: z.enum(["primary", "muted"]),
});
export type TimelineLaneSegment = z.infer<typeof timelineLaneSegmentSchema>;

export const timelineLaneSchema = z.object({
  name: z.string(),
  segments: z.array(timelineLaneSegmentSchema),
  marker: z.number(),
});
export type TimelineLane = z.infer<typeof timelineLaneSchema>;

export const timelineSchema = z.object({
  project_id: z.string().uuid(),
  project_name: z.string(),
  current_phase: z.string(),
  current_day: z.number().int(),
  start_date: z.string(),
  months: z.array(z.string()),
  phases: z.array(timelinePhaseSchema),
  lanes: z.array(timelineLaneSchema),
  summary: z.string(),
  fcs_label: z.string(),
  progress_pct: z.number().int(),
});
export type Timeline = z.infer<typeof timelineSchema>;
