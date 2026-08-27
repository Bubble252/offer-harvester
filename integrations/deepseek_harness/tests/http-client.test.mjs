import assert from "node:assert/strict";
import test from "node:test";

import {
  auditMaterial,
  normalizeApiBaseUrl,
  pluginHeaders,
  runProductSkill,
} from "../src/http-client.mjs";

test("normalizes the Offer Harvester API base URL", () => {
  assert.equal(normalizeApiBaseUrl("http://127.0.0.1:8000///"), "http://127.0.0.1:8000");
  assert.throws(() => normalizeApiBaseUrl(""), /base URL is required/);
});

test("keeps the static token optional and declares scope and privacy", () => {
  assert.deepEqual(
    pluginHeaders({ privacyMode: "private", pluginToken: "local-token" }, "skill:run"),
    {
      "Content-Type": "application/json",
      "X-Offer-Harvester-Plugin-Scopes": "skill:run",
      "X-Offer-Harvester-Privacy-Mode": "private",
      "X-Offer-Harvester-Plugin-Token": "local-token",
    },
  );
});

test("routes product tools and audits to scoped candidate-only endpoints", async () => {
  const calls = [];
  const fetchMock = async (url, init) => {
    calls.push({ url, init });
    return new Response(JSON.stringify({ candidate_status: "candidate", no_send: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  const config = { apiBaseUrl: "http://127.0.0.1:8000", requestTimeoutMs: 1000 };

  await runProductSkill(config, "advisor-due-diligence", { advisor_id: "adv_1" }, fetchMock);
  await auditMaterial(config, "mat_1", fetchMock);

  assert.equal(calls[0].url, "http://127.0.0.1:8000/api/plugin/skills/advisor-due-diligence/run");
  assert.equal(calls[0].init.headers["X-Offer-Harvester-Plugin-Scopes"], "advisor:report");
  assert.equal(calls[1].url, "http://127.0.0.1:8000/api/plugin/materials/audit");
  assert.equal(calls[1].init.headers["X-Offer-Harvester-Plugin-Scopes"], "material:audit");
  assert.deepEqual(JSON.parse(calls[1].init.body), { material_id: "mat_1" });
});

test("surfaces a server rejection without retrying a side-effecting tool call", async () => {
  const fetchMock = async () => new Response(JSON.stringify({ detail: "scope denied" }), {
    status: 403,
    headers: { "Content-Type": "application/json" },
  });
  await assert.rejects(
    () => runProductSkill(
      { apiBaseUrl: "http://127.0.0.1:8000", requestTimeoutMs: 1000 },
      "contact-email-coach",
      { target_id: "target_1" },
      fetchMock,
    ),
    /403: scope denied/,
  );
});
