export interface OfferHarvesterPluginConfig {
  apiBaseUrl: string;
  pluginToken?: string;
  privacyMode?: "metadata_only" | "private";
  requestTimeoutMs?: number;
}

export function normalizeApiBaseUrl(value: unknown): string;
export function pluginHeaders(
  config: OfferHarvesterPluginConfig,
  scope: string,
): Record<string, string>;
export function callOfferHarvester(
  config: OfferHarvesterPluginConfig,
  path: string,
  payload: Record<string, unknown>,
  scope: string,
): Promise<Record<string, unknown>>;
export function runProductSkill(
  config: OfferHarvesterPluginConfig,
  skillId: string,
  payload: Record<string, unknown>,
): Promise<Record<string, unknown>>;
export function auditMaterial(
  config: OfferHarvesterPluginConfig,
  materialId: string,
): Promise<Record<string, unknown>>;
