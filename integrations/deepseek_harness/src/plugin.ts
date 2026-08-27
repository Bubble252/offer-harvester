/**
 * Controlled Offer Harvester tools for a DeepSeek Harness Cordis composition.
 *
 * This plugin never writes profile, tracker, or source-of-truth records directly.
 * The FastAPI control plane owns evidence checks, user confirmation, audit events,
 * and any workspace persistence.
 */

import type { Context } from "@deepseek-ai/cordis";
import z from "@deepseek-ai/schemastery";
import { defineTool } from "@deepseek-ai/dsh-tools";

import { auditMaterial, runProductSkill } from "./http-client.mjs";

export const name = "offer-harvester";
export const inject = ["tools"];

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const DEFAULT_TIMEOUT_MS = 20_000;
const DEFAULT_TOOLS = [
  "draft_contact_email",
  "advisor_due_diligence",
  "recommendation_letter_helper",
  "audit_material",
];

export interface Config {
  apiBaseUrl?: string;
  pluginToken?: string;
  privacyMode?: "metadata_only" | "private";
  requestTimeoutMs?: number;
  enabledTools?: string[];
  workspaceLabel?: string;
}

export const Config: z<Config> = z.object({
  apiBaseUrl: z.string().default(DEFAULT_API_BASE_URL),
  pluginToken: z.string().optional(),
  privacyMode: z.string().default("metadata_only"),
  requestTimeoutMs: z.number().default(DEFAULT_TIMEOUT_MS),
  enabledTools: z.array(z.string()).default(DEFAULT_TOOLS),
  workspaceLabel: z.string().optional(),
});

type ResolvedConfig = Required<Omit<Config, "pluginToken" | "workspaceLabel">>
  & Pick<Config, "pluginToken" | "workspaceLabel">;

function assertConfig(config: ResolvedConfig): void {
  if (!Number.isFinite(config.requestTimeoutMs) || config.requestTimeoutMs <= 0) {
    throw new Error("offer-harvester: requestTimeoutMs must be positive.");
  }
  if (!["metadata_only", "private"].includes(config.privacyMode)) {
    throw new Error("offer-harvester: privacyMode must be metadata_only or private.");
  }
}

function renderCandidate(value: unknown): string {
  const result = value as { candidate_status?: string; no_send?: boolean; output?: unknown };
  return JSON.stringify(
    {
      candidate_status: result.candidate_status ?? "candidate",
      no_send: result.no_send !== false,
      output: result.output ?? result,
      next_step: "Review the candidate in Offer Harvester before any external action.",
    },
    null,
    2,
  );
}

function enabled(config: ResolvedConfig, toolName: string): boolean {
  return config.enabledTools.includes(toolName);
}

export function apply(ctx: Context, config: Config): void {
  const resolved = config as ResolvedConfig;
  assertConfig(resolved);

  if (enabled(resolved, "draft_contact_email")) {
    ctx.tools.register(defineTool({
      name: "offer_harvester_draft_contact_email",
      description: "Create a reviewed, evidence-audited contact-email candidate in Offer Harvester. It never sends email.",
      parameters: {
        target_id: { type: "string", required: true, description: "Offer Harvester application target ID." },
        mode: { type: "string", description: "Optional draft mode: new, rewrite, advisor_alignment, reduce_exaggeration, or follow_up." },
      },
      output: {
        schema: { type: "object", additionalProperties: true },
        render: (_args, value) => [{ type: "text", text: renderCandidate(value) }],
      },
      async execute(args) {
        return runProductSkill(resolved, "contact-email-coach", {
          target_id: args.target_id,
          mode: args.mode ?? "new",
        });
      },
      presentCall: args => ({
        card: "generic",
        title: "Draft contact email candidate",
        kind: "write",
        rawInput: args.target_id,
      }),
    }));
  }

  if (enabled(resolved, "advisor_due_diligence")) {
    ctx.tools.register(defineTool({
      name: "offer_harvester_advisor_due_diligence",
      description: "Produce a source-grounded advisor due-diligence candidate. Community content remains a review signal, never a confirmed fact.",
      parameters: {
        advisor_id: { type: "string", required: true, description: "Offer Harvester advisor ID." },
        target_id: { type: "string", description: "Optional application target ID linked to the advisor." },
      },
      output: {
        schema: { type: "object", additionalProperties: true },
        render: (_args, value) => [{ type: "text", text: renderCandidate(value) }],
      },
      async execute(args) {
        return runProductSkill(resolved, "advisor-due-diligence", {
          advisor_id: args.advisor_id,
          target_id: args.target_id ?? "",
        });
      },
      presentCall: args => ({
        card: "generic",
        title: "Review advisor evidence",
        kind: "read",
        rawInput: args.advisor_id,
      }),
    }));
  }

  if (enabled(resolved, "recommendation_letter_helper")) {
    ctx.tools.register(defineTool({
      name: "offer_harvester_recommendation_letter_helper",
      description: "Create a recommendation-letter request and evidence packet candidate. It cannot impersonate, send, or submit on behalf of a recommender.",
      parameters: {
        target_id: { type: "string", description: "Optional application target ID." },
        recommender_name: { type: "string", description: "Optional recommender name." },
        relationship: { type: "string", description: "Optional relationship to the student." },
      },
      output: {
        schema: { type: "object", additionalProperties: true },
        render: (_args, value) => [{ type: "text", text: renderCandidate(value) }],
      },
      async execute(args) {
        return runProductSkill(resolved, "recommendation-letter-helper", {
          target_id: args.target_id ?? "",
          recommender_name: args.recommender_name ?? "",
          relationship: args.relationship ?? "",
        });
      },
      presentCall: () => ({
        card: "generic",
        title: "Create recommendation packet candidate",
        kind: "write",
        rawInput: "recommendation packet",
      }),
    }));
  }

  if (enabled(resolved, "audit_material")) {
    ctx.tools.register(defineTool({
      name: "offer_harvester_audit_material",
      description: "Run review, evidence audit, and material quality checks on an existing Offer Harvester material. The material is never changed.",
      parameters: {
        material_id: { type: "string", required: true, description: "Offer Harvester generated material ID." },
      },
      output: {
        schema: { type: "object", additionalProperties: true },
        render: (_args, value) => [{ type: "text", text: renderCandidate(value) }],
      },
      async execute(args) {
        return auditMaterial(resolved, args.material_id);
      },
      presentCall: args => ({
        card: "generic",
        title: "Audit application material",
        kind: "read",
        rawInput: args.material_id,
      }),
    }));
  }
}
