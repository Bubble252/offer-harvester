const DEFAULT_TIMEOUT_MS = 20_000;

export function normalizeApiBaseUrl(value) {
  const trimmed = String(value || "").trim();
  if (!trimmed) {
    throw new Error("Offer Harvester API base URL is required.");
  }
  return trimmed.replace(/\/+$/, "");
}

export function pluginHeaders(config, scope) {
  const privacyMode = config.privacyMode === "private" ? "private" : "metadata_only";
  const headers = {
    "Content-Type": "application/json",
    "X-Offer-Harvester-Plugin-Scopes": scope,
    "X-Offer-Harvester-Privacy-Mode": privacyMode,
  };
  if (config.pluginToken) {
    headers["X-Offer-Harvester-Plugin-Token"] = config.pluginToken;
  }
  return headers;
}

export async function callOfferHarvester(
  config,
  path,
  payload,
  scope,
  fetchImpl = globalThis.fetch,
) {
  if (typeof fetchImpl !== "function") {
    throw new Error("A fetch implementation is required for the DSH integration.");
  }
  const timeoutMs = Number(config.requestTimeoutMs || DEFAULT_TIMEOUT_MS);
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new Error("requestTimeoutMs must be a positive number.");
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchImpl(`${normalizeApiBaseUrl(config.apiBaseUrl)}${path}`, {
      method: "POST",
      headers: pluginHeaders(config, scope),
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    const raw = await response.text();
    let data = {};
    if (raw) {
      try {
        data = JSON.parse(raw);
      } catch {
        data = { detail: raw };
      }
    }
    if (!response.ok) {
      const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data);
      throw new Error(`Offer Harvester API ${response.status}: ${detail}`);
    }
    return data;
  } finally {
    clearTimeout(timer);
  }
}

export function runProductSkill(config, skillId, payload, fetchImpl) {
  const scope = skillId === "advisor-due-diligence" ? "advisor:report" : "skill:run";
  return callOfferHarvester(
    config,
    `/api/plugin/skills/${encodeURIComponent(skillId)}/run`,
    payload,
    scope,
    fetchImpl,
  );
}

export function auditMaterial(config, materialId, fetchImpl) {
  return callOfferHarvester(
    config,
    "/api/plugin/materials/audit",
    { material_id: materialId },
    "material:audit",
    fetchImpl,
  );
}
