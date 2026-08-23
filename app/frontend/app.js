const state = {
  profile: null,
  advisors: [],
  sources: [],
  targets: [],
  applications: [],
  archives: [],
  communications: [],
  emailSignals: [],
  materials: [],
  userDocuments: [],
  readinessScore: null,
  lifecycleSync: null,
  triageReport: null,
  profileExpansionReport: null,
  gapPlans: [],
  strategyStatus: null,
  templateRegistry: null,
  sourceConnectorRegistry: null,
  selectedCustomTemplate: null,
  pdfReadabilityReport: null,
  referencePresentations: [],
  presentationPrechecks: [],
  presentationQualityReports: [],
  selectedMaterial: null,
};

const titles = {
  dashboard: "申请概览",
  profile: "学生资料",
  advisors: "导师资料",
  targets: "申请目标",
  materials: "材料中心",
  report: "进度报告",
};

const applicationStatuses = [
  ["draft", "草稿"],
  ["drafted", "已起草"],
  ["researching", "调研中"],
  ["ready_to_contact", "待联系"],
  ["contacted", "已联系"],
  ["replied", "已回复"],
  ["materials_preparing", "准备材料"],
  ["submitted", "已提交"],
  ["shortlisted", "入围"],
  ["interview", "面试中"],
  ["interview_scheduled", "已约面试"],
  ["interview_done", "已完成面试"],
  ["waitlist", "候补"],
  ["offer", "拟录取"],
  ["accepted", "已录取"],
  ["rejected", "未录取"],
  ["no_response", "无回复"],
  ["withdrawn", "已放弃"],
];

const profileFields = [
  ["name", "姓名"],
  ["education", "教育背景"],
  ["gpa", "GPA"],
  ["rank", "排名"],
  ["research_interests", "研究兴趣"],
  ["projects", "项目经历"],
  ["publications", "论文成果"],
  ["competitions", "竞赛奖项"],
  ["skills", "技能关键词"],
];

const confirmationStatuses = [
  ["unconfirmed", "未确认"],
  ["confirmed", "已确认"],
  ["rejected", "已否认"],
  ["needs_review", "需复核"],
];

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("show");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => node.classList.remove("show"), 2800);
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || response.statusText);
  }
  return response.json();
}

function statusLabel(status) {
  const item = applicationStatuses.find(([value]) => value === status);
  return item ? item[1] : status || "调研中";
}

function tagList(values) {
  if (!values || !values.length) return "<span class='item-meta'>待补充</span>";
  return `<div class="tag-row">${values.map((value) => `<span class="tag">${escapeHtml(value)}</span>`).join("")}</div>`;
}

function listToText(values) {
  return (values || []).join("\n");
}

function textToList(value) {
  return String(value || "")
    .split(/\n|；|;/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function confirmationOptions(current) {
  return confirmationStatuses
    .map(([value, label]) => `<option value="${value}" ${value === current ? "selected" : ""}>${label}</option>`)
    .join("");
}

function profileFieldValue(profile, field) {
  const value = profile[field];
  if (Array.isArray(value)) return tagList(value);
  return escapeHtml(value || "待补充");
}

function showView(view) {
  document.querySelectorAll("[data-view-panel]").forEach((node) => {
    node.classList.toggle("active", node.dataset.viewPanel === view);
  });
  document.querySelectorAll("[data-view]").forEach((node) => {
    node.classList.toggle("active", node.dataset.view === view);
  });
  $("pageTitle").textContent = titles[view];
}

function renderMetrics() {
  const contacted = state.applications.filter((item) => item.status === "contacted").length;
  const pending = state.applications.filter((item) =>
    ["researching", "ready_to_contact", "materials_preparing"].includes(item.status)
  ).length;
  $("metrics").innerHTML = [
    ["申请目标", state.targets.length],
    ["已联系导师", contacted],
    ["待推进目标", pending],
    ["已生成材料", state.materials.length],
  ]
    .map(([label, value]) => `<div class="metric"><span class="metric-label">${label}</span><strong class="metric-value">${value}</strong></div>`)
    .join("");
}

function renderDashboard() {
  const targetById = Object.fromEntries(state.targets.map((target) => [target.target_id, target]));
  const actions = state.applications
    .filter((item) => item.next_action || item.status)
    .slice(0, 6)
    .map((item) => {
      const target = targetById[item.target_id];
      return `<div class="action-item"><div class="item-title">${escapeHtml(target ? target.name : item.target_id)}</div><div class="item-meta">${escapeHtml(item.next_action || `当前状态：${statusLabel(item.status)}`)}</div></div>`;
    });
  $("nextActions").innerHTML = actions.length ? actions.join("") : "<div class='empty-state'>创建申请目标后，这里会显示下一步行动。</div>";

  const recent = state.materials
    .slice(-5)
    .reverse()
    .map((material) => `<div class="list-item"><div class="item-title">${escapeHtml(material.title)}</div><div class="item-meta">${escapeHtml(material.material_type)} · ${escapeHtml(material.created_at)}</div></div>`);
  $("recentMaterials").innerHTML = recent.length ? recent.join("") : "<div class='empty-state'>尚未生成材料。</div>";
}

function readinessLabel(score) {
  if (score >= 85) return "准备充分";
  if (score >= 70) return "基本可投";
  if (score >= 55) return "仍需补齐";
  return "准备不足";
}

function renderReadinessDashboard() {
  const report = state.readinessScore;
  if (!report) {
    $("readinessSummary").innerHTML = "<div class='empty-state'>尚未生成申请准备度评分。</div>";
    return;
  }
  const dimensions = (report.dimensions || [])
    .slice()
    .sort((a, b) => b.weight - a.weight)
    .map(
      (dimension) => `<div class="readiness-dimension">
        <div class="readiness-dimension-head">
          <strong>${escapeHtml(dimension.label)}</strong>
          <span>${escapeHtml(String(dimension.score ?? 0))}</span>
        </div>
        <div class="readiness-bar"><span style="width:${Math.max(0, Math.min(100, dimension.score ?? 0))}%"></span></div>
        <div class="item-meta">${escapeHtml(dimension.summary || "")}</div>
        ${dimension.action_items && dimension.action_items.length ? `<div class="readiness-actions">${dimension.action_items.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>` : ""}
      </div>`
    )
    .join("");
  const topTargets = (report.target_scores || [])
    .slice()
    .sort((a, b) => b.score - a.score)
    .slice(0, 3)
    .map(
      (item) => `<div class="list-item readiness-target-item">
        <div class="item-title">${escapeHtml(item.target_name)}</div>
        <div class="item-meta">${escapeHtml(item.status)} · ${escapeHtml(item.score)} 分</div>
      </div>`
    )
    .join("");
  $("readinessSummary").innerHTML = `
    <div class="readiness-overview">
      <div class="readiness-score-card">
        <div class="readiness-score-value">${escapeHtml(String(report.total_score ?? 0))}</div>
        <div class="readiness-score-meta">${escapeHtml(report.status || readinessLabel(report.total_score ?? 0))}</div>
      </div>
      <div class="readiness-copy">
        <p>${escapeHtml(report.summary || "")}</p>
        ${report.high_priority_actions && report.high_priority_actions.length ? `<div class="readiness-actions">${report.high_priority_actions.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>` : ""}
      </div>
    </div>
    <div class="readiness-subgrid">
      <div>
        <h3>维度分</h3>
        <div class="readiness-dimension-list">${dimensions}</div>
      </div>
      <div>
        <h3>当前目标排行</h3>
        <div class="stack-list">${topTargets || "<div class='empty-state'>还没有目标评分。</div>"}</div>
      </div>
    </div>
  `;
}

function renderTargetReadiness() {
  const report = state.readinessScore;
  const select = $("readinessTargetSelect");
  if (!select) return;
  const current = select.value;
  const targets = (report && report.target_scores) || [];
  select.innerHTML = "<option value=''>选择目标查看准备度</option>";
  targets.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.target_id;
    option.textContent = `${item.target_name} · ${item.score} 分`;
    select.appendChild(option);
  });
  const selectedId = targets.some((item) => item.target_id === current)
    ? current
    : targets[0]?.target_id || "";
  select.value = selectedId;
  const detail = $("targetReadinessView");
  if (!detail) return;
  const item = targets.find((entry) => entry.target_id === selectedId);
  if (!item) {
    detail.innerHTML = "<div class='empty-state'>选择一个目标后，这里会显示详细评分。</div>";
    return;
  }
  const dimensions = (item.dimensions || [])
    .slice()
    .sort((a, b) => b.weight - a.weight)
    .map(
      (dimension) => `<div class="readiness-dimension">
        <div class="readiness-dimension-head">
          <strong>${escapeHtml(dimension.label)}</strong>
          <span>${escapeHtml(String(dimension.score ?? 0))}</span>
        </div>
        <div class="readiness-bar"><span style="width:${Math.max(0, Math.min(100, dimension.score ?? 0))}%"></span></div>
        <div class="item-meta">${escapeHtml(dimension.summary || "")}</div>
        ${dimension.reasons && dimension.reasons.length ? `<div class="readiness-notes">${dimension.reasons.map((note) => `<span>${escapeHtml(note)}</span>`).join("")}</div>` : ""}
      </div>`
    )
    .join("");
  detail.innerHTML = `
    <div class="readiness-overview">
      <div class="readiness-score-card">
        <div class="readiness-score-value">${escapeHtml(String(item.score ?? 0))}</div>
        <div class="readiness-score-meta">${escapeHtml(item.status || readinessLabel(item.score ?? 0))}</div>
      </div>
      <div class="readiness-copy">
        <p>${escapeHtml(item.summary || "")}</p>
        ${item.action_items && item.action_items.length ? `<div class="readiness-actions">${item.action_items.map((action) => `<span>${escapeHtml(action)}</span>`).join("")}</div>` : ""}
      </div>
    </div>
    <div class="readiness-dimension-list">${dimensions}</div>
  `;
  renderLifecycle();
}

function renderLifecycle() {
  const selectedId = $("readinessTargetSelect").value;
  const target = state.targets.find((item) => item.target_id === selectedId);
  const archives = (state.archives || []).filter((item) => item.target_id === selectedId);
  const communications = (state.communications || []).filter((item) => item.target_id === selectedId);
  const latestArchive = archives[archives.length - 1];
  if (!target) {
    $("lifecycleView").innerHTML = "<div class='empty-state'>选择一个目标后，这里会显示归档和沟通记录。</div>";
    return;
  }
  const archiveHtml = latestArchive
    ? `<div class="list-item">
        <div class="item-title">归档：${escapeHtml(latestArchive.stage)}</div>
        <div class="item-meta">${escapeHtml(latestArchive.archive_path)} · ${escapeHtml(latestArchive.updated_at)}</div>
        <div class="item-meta">材料快照 ${latestArchive.submitted_material_paths.length} 份 · 沟通记录 ${latestArchive.communication_paths.length} 份</div>
      </div>`
    : "<div class='empty-state'>还没有申请归档。</div>";
  const commHtml = communications.length
    ? communications
        .slice()
        .reverse()
        .slice(0, 4)
        .map((item) => `<div class="list-item">
          <div class="item-title">${escapeHtml(item.kind)} · ${escapeHtml(item.title)}</div>
          <div class="item-meta">${escapeHtml(item.archive_path || "尚未写入归档")} · ${escapeHtml(item.created_at)}</div>
        </div>`)
        .join("")
    : "<div class='empty-state'>还没有沟通草稿。</div>";
  const syncHtml = state.lifecycleSync
    ? `<div class="quality-summary">
        <strong>${escapeHtml(state.lifecycleSync.title)}</strong>
        <div class="item-meta">${escapeHtml(state.lifecycleSync.message)}</div>
      </div>`
    : "";
  $("lifecycleView").innerHTML = `
    <div class="lifecycle-grid">
      <div>
        <h3>归档</h3>
        ${archiveHtml}
      </div>
      <div>
        <h3>沟通草稿</h3>
        <div class="stack-list">${commHtml}</div>
      </div>
    </div>
    ${syncHtml}
  `;
  renderEmailSignals();
}

function renderEmailSignals() {
  const view = $("emailSignalView");
  if (!view) return;
  const selectedId = $("readinessTargetSelect").value || $("targetSelect").value;
  const signals = (state.emailSignals || [])
    .filter((item) => !selectedId || !item.target_id || item.target_id === selectedId)
    .slice()
    .reverse();
  if (!signals.length) {
    view.innerHTML = "<div class='empty-state'>尚未识别邮件信号。</div>";
    return;
  }
  view.innerHTML = `<div class="stack-list email-signal-list">
    ${signals
      .slice(0, 8)
      .map(
        (item) => `<div class="list-item strategy-item">
          <div class="item-title">${escapeHtml(item.signal_type)} · ${escapeHtml(item.proposed_status)} · ${escapeHtml(item.status)}</div>
          <div class="item-meta">${escapeHtml(item.target_name || "未匹配目标")} · ${escapeHtml(item.subject || "无主题")}</div>
          <div class="item-meta">${escapeHtml(item.sender || "未知发件人")} · ${escapeHtml(item.received_at || "未知日期")} · confidence ${escapeHtml(String(Math.round((item.confidence || 0) * 100)))}%</div>
          <div class="item-meta">${escapeHtml(item.body_excerpt || item.evidence_summary || "")}</div>
          <div class="button-row compact-actions">
            <button data-approve-email-signal-id="${escapeHtml(item.candidate_id)}" ${item.status !== "needs_user_confirmation" ? "disabled" : ""}>确认写入</button>
            <button class="secondary" data-reject-email-signal-id="${escapeHtml(item.candidate_id)}" ${item.status === "approved" || item.status === "rejected" ? "disabled" : ""}>拒绝</button>
          </div>
        </div>`
      )
      .join("")}
  </div>`;
}

function latestGapPlanForTarget(targetId) {
  return (state.gapPlans || []).filter((item) => item.target_id === targetId).slice(-1)[0];
}

function renderStrategy() {
  const triage = state.triageReport;
  const expansion = state.profileExpansionReport;
  const selectedTargetId = $("readinessTargetSelect").value || $("targetSelect").value;
  const gapPlan = latestGapPlanForTarget(selectedTargetId);

  const triageHtml = triage
    ? `
      <div class="strategy-summary">${escapeHtml(triage.summary || "")}</div>
      <div class="stack-list">
        ${(triage.items || [])
          .slice(0, 5)
          .map(
            (item) => `<div class="list-item strategy-item">
              <div class="item-title">${escapeHtml(item.target_name)} · ${escapeHtml(String(item.triage_score))} 分</div>
              <div class="item-meta">${escapeHtml(item.tier)} · ${item.preliminary ? "初筛结果" : "正式结果"} · deadline ${escapeHtml(item.deadline_urgency)}</div>
              <div class="readiness-actions">${(item.recommended_next_actions || []).slice(0, 2).map((action) => `<span>${escapeHtml(action)}</span>`).join("")}</div>
              <button data-strategy-target-id="${escapeHtml(item.target_id)}">进入目标</button>
            </div>`
          )
          .join("")}
      </div>`
    : "<div class='empty-state'>尚未生成批量粗排。</div>";

  const expansionHtml = expansion
    ? `
      <div class="strategy-summary">${escapeHtml(expansion.summary || "")}</div>
      <div class="stack-list">
        ${(expansion.candidates || [])
          .slice(0, 6)
          .map(
            (item) => `<div class="list-item strategy-item">
              <div class="item-title">${escapeHtml(item.field_name)}：${escapeHtml(item.value)}</div>
              <div class="item-meta">${escapeHtml(item.status)} · ${escapeHtml(item.source_type)} · ${item.inferred ? "推断字段" : "文本字段"}</div>
            </div>`
          )
          .join("") || "<div class='empty-state'>没有新的画像候选。</div>"}
      </div>`
    : "<div class='empty-state'>尚未生成画像扩展候选。</div>";

  const gapHtml = gapPlan
    ? `
      <div class="strategy-summary">${escapeHtml(gapPlan.summary || "")}</div>
      <div class="readiness-actions">${(gapPlan.next_actions || []).slice(0, 4).map((action) => `<span>${escapeHtml(action)}</span>`).join("")}</div>
      <div class="stack-list">
        ${(gapPlan.gaps || [])
          .slice(0, 5)
          .map(
            (item) => `<div class="list-item strategy-item">
              <div class="item-title">${escapeHtml(item.title)}</div>
              <div class="item-meta">${escapeHtml(item.category)} · ${escapeHtml(item.severity)} · ${escapeHtml(item.source)}</div>
            </div>`
          )
          .join("")}
      </div>`
    : "<div class='empty-state'>选择目标并生成 gap plan 后显示行动计划。</div>";

  const templateRegistryHtml = state.templateRegistry
    ? `<div class="template-registry-list">
        <div class="strategy-summary">内置模板 ${escapeHtml(String(state.templateRegistry.template_count || 0))} 个，已激活 ${escapeHtml(String(state.templateRegistry.active_count || 0))} 个；用户模板 ${escapeHtml(String(state.templateRegistry.custom_template_count || 0))} 个，已启用 ${escapeHtml(String(state.templateRegistry.custom_active_count || 0))} 个。</div>
        <div class="stack-list">
          ${(state.templateRegistry.templates || [])
            .map(
              (item) => `<div class="list-item strategy-item">
                <div class="item-title">${escapeHtml(item.name || item.template_id)} · ${item.active ? "可激活" : "需修正"}</div>
                <div class="item-meta">${escapeHtml(item.template_type)} · ${escapeHtml(item.path)} · 变量 ${escapeHtml(String((item.variables || []).length))} 个</div>
                <div class="item-meta">${escapeHtml((item.validation_issues || []).map((issue) => issue.message).join("；") || "manifest、变量、样例渲染和隐私扫描通过。")}</div>
              </div>`
            )
            .join("")}
          ${(state.templateRegistry.custom_templates || [])
            .map(
              (item) => `<div class="list-item strategy-item">
                <div class="item-title">${escapeHtml(item.name || item.template_id)} · ${escapeHtml(item.status || "draft")}</div>
                <div class="item-meta">${escapeHtml(item.template_type)} · 版本 ${escapeHtml(String(item.version_count || 0))} · ${item.active ? "当前启用" : "未启用"}</div>
                <div class="item-meta">${escapeHtml((item.validation_issues || []).map((issue) => issue.message).join("；") || "模板校验通过。")}</div>
              </div>`
            )
            .join("")}
        </div>
      </div>`
    : "";

  const sourceConnectorHtml = state.sourceConnectorRegistry
    ? `<div class="template-registry-list">
        <div class="strategy-summary">连接器 ${escapeHtml(String(state.sourceConnectorRegistry.connector_count || 0))} 个，manifest 合法 ${escapeHtml(String(state.sourceConnectorRegistry.active_count || 0))} 个，可注册 ${escapeHtml(String(state.sourceConnectorRegistry.registrable_count || 0))} 个。</div>
        <div class="stack-list">
          ${(state.sourceConnectorRegistry.connectors || [])
            .map(
              (item) => `<div class="list-item strategy-item">
                <div class="item-title">${escapeHtml(item.name || item.connector_id)} · ${item.registration_eligible ? "可注册" : item.refresh_state === "stale" ? "已过期" : item.refresh_state === "needs_review" ? "需复核" : item.live_test_status === "not_run" ? "待 live test" : "不可注册"}</div>
                <div class="item-meta">${escapeHtml(item.source_type)} · ${escapeHtml(item.path)} · URL pattern ${escapeHtml(String((item.url_patterns || []).length))} 个 · 字段 ${escapeHtml(String(Object.keys(item.field_mapping || {}).length))} 个</div>
                <div class="item-meta">live test：${escapeHtml(item.live_test_status || "not_run")} · 刷新：${escapeHtml(item.refresh_state || "not_tested")} · 下次检查 ${escapeHtml(item.next_refresh_at || "尚未安排")}</div>
                <div class="item-meta">${escapeHtml((item.validation_issues || []).map((issue) => issue.message).join("；") || "manifest、字段映射、访问规则和测试查询通过。")}</div>
                ${item.test_urls && item.test_urls.length ? `<button class="secondary" data-source-connector-id="${escapeHtml(item.connector_id)}">${item.refresh_due || item.refresh_state === "stale" ? "刷新公开 live test" : "运行公开 live test"}</button>` : "<div class='item-meta'>未声明公开测试 URL，只能手动粘贴兜底。</div>"}
              </div>`
            )
            .join("")}
        </div>
      </div>`
    : "";

  const registryHtml = state.strategyStatus
    ? `<div class="quality-summary">
        <strong>${escapeHtml(state.strategyStatus.title)}</strong>
        <div class="item-meta">${escapeHtml(state.strategyStatus.message)}</div>
        ${templateRegistryHtml}
        ${sourceConnectorHtml}
      </div>`
    : "";

  $("strategyView").innerHTML = `
    <div class="strategy-grid">
      <div>
        <h3>批量粗排</h3>
        ${triageHtml}
      </div>
      <div>
        <h3>画像扩展候选</h3>
        ${expansionHtml}
      </div>
      <div>
        <h3>Gap / Upskill</h3>
        ${gapHtml}
      </div>
    </div>
    ${registryHtml}
  `;
  renderCustomTemplateOptions();
}

function customTemplates() {
  return state.templateRegistry?.custom_templates || [];
}

function renderCustomTemplateOptions(selectedId = "") {
  const select = $("customTemplateSelect");
  if (!select) return;
  const current = selectedId || select.value || state.selectedCustomTemplate?.template_id || "";
  select.innerHTML = "<option value=''>新建用户模板</option>";
  customTemplates().forEach((item) => {
    const option = document.createElement("option");
    option.value = item.template_id;
    option.textContent = `${item.name || item.template_id} · ${item.status}`;
    select.appendChild(option);
  });
  select.value = customTemplates().some((item) => item.template_id === current) ? current : "";
  const selected = customTemplates().find((item) => item.template_id === select.value);
  if (selected && selected.template_id !== state.selectedCustomTemplate?.template_id) {
    fillCustomTemplateEditor(selected);
  } else if (!selected && !state.selectedCustomTemplate) {
    clearCustomTemplateEditor();
  }
}

function fillCustomTemplateEditor(template) {
  state.selectedCustomTemplate = template;
  $("customTemplateName").value = template.name || "";
  $("customTemplateType").value = template.template_type || "contact_email";
  $("customTemplateStatus").value = template.status || "draft";
  $("customTemplateContent").value = template.content || "";
  $("customTemplateDescription").value = template.description || "";
  $("customTemplateVariables").value = listToText(template.variables);
  $("customTemplateSampleContext").value = JSON.stringify(template.sample_context || {}, null, 2);
  $("customTemplateApplicableScenarios").value = listToText(template.applicable_scenarios);
  $("customTemplateStyleRules").value = listToText(template.style_rules);
  $("customTemplatePrivacyRules").value = listToText(template.privacy_rules);
  $("customTemplateValidationMethods").value = listToText(template.validation_methods);
  $("customTemplateManagedBlock").value = template.managed_block || "";
  $("templateDiffView").textContent = `版本数：${template.version_count || 0} · 当前状态：${template.status || "draft"}`;
}

function clearCustomTemplateEditor() {
  state.selectedCustomTemplate = null;
  [
    "customTemplateName",
    "customTemplateContent",
    "customTemplateDescription",
    "customTemplateVariables",
    "customTemplateSampleContext",
    "customTemplateApplicableScenarios",
    "customTemplateStyleRules",
    "customTemplatePrivacyRules",
    "customTemplateValidationMethods",
    "customTemplateManagedBlock",
  ].forEach((id) => {
    $(id).value = "";
  });
  $("customTemplateType").value = "contact_email";
  $("customTemplateStatus").value = "draft";
  $("templateDiffView").textContent = "尚未选择模板 diff";
}

function customTemplatePayload() {
  let sampleContext = {};
  const rawSample = $("customTemplateSampleContext").value.trim();
  if (rawSample) {
    try {
      sampleContext = JSON.parse(rawSample);
    } catch {
      throw new Error("样例上下文必须是合法 JSON");
    }
  }
  return {
    name: $("customTemplateName").value.trim(),
    template_type: $("customTemplateType").value,
    status: $("customTemplateStatus").value,
    content: $("customTemplateContent").value,
    description: $("customTemplateDescription").value.trim(),
    variables: textToList($("customTemplateVariables").value),
    sample_context: sampleContext,
    applicable_scenarios: textToList($("customTemplateApplicableScenarios").value),
    style_rules: textToList($("customTemplateStyleRules").value),
    privacy_rules: textToList($("customTemplatePrivacyRules").value),
    validation_methods: textToList($("customTemplateValidationMethods").value),
    managed_block: $("customTemplateManagedBlock").value.trim(),
  };
}

function renderProfile() {
  if (!state.profile) {
    $("profileView").innerHTML = "<div class='empty-state'>尚未创建学生画像。</div>";
    renderUserDocuments();
    return;
  }
  const profile = state.profile;
  $("profileView").innerHTML = profileFields
    .map(([field, label]) => {
      const status = (profile.confirmation_map || {})[field] || "unconfirmed";
      const evidenceIds = (profile.evidence_map || {})[field] || [];
      return `<div class="detail-group profile-field-row">
        <span class="detail-label">${label}</span>
        <div class="profile-field-main">
          <div>${profileFieldValue(profile, field)}</div>
          <div class="field-evidence">${evidenceIds.length ? `证据：${escapeHtml(evidenceIds.join("、"))}` : "证据：待补充"}</div>
        </div>
        <select class="confirmation-select" data-profile-field="${field}" aria-label="${label}确认状态">
          ${confirmationOptions(status)}
        </select>
      </div>`;
    })
    .join("");
  $("profileView").innerHTML += [
    ["来源资料", tagList(profile.source_document_ids)],
    ["风险项", tagList(profile.risks)],
  ]
    .map(([label, value]) => `<div class="detail-group"><span class="detail-label">${label}</span><div>${value}</div></div>`)
    .join("");
  renderUserDocuments();
}

function renderUserDocuments() {
  const documents = state.userDocuments || [];
  $("userDocumentList").innerHTML = documents.length
    ? documents
        .slice()
        .reverse()
        .map((document) => `<div class="list-item">
          <div class="item-title">${escapeHtml(document.original_filename || document.document_id)}</div>
          <div class="item-meta">${escapeHtml(document.category)} · ${escapeHtml(document.source_type)} · ${escapeHtml(document.uploaded_at)}</div>
        </div>`)
        .join("")
    : "<div class='empty-state'>尚未保存原始资料。</div>";
}

function renderAdvisorOptions() {
  const select = $("advisorSelect");
  const current = select.value;
  select.innerHTML = "<option value=''>不绑定导师</option>";
  const attachSelect = $("advisorAttachSelect");
  const attachCurrent = attachSelect.value;
  attachSelect.innerHTML = "<option value=''>创建新导师画像</option>";
  state.advisors.forEach((advisor) => {
    const option = document.createElement("option");
    option.value = advisor.advisor_id;
    option.textContent = advisor.name_zh || advisor.homepage_url || advisor.advisor_id;
    select.appendChild(option);
    const attachOption = option.cloneNode(true);
    attachSelect.appendChild(attachOption);
  });
  select.value = state.advisors.some((advisor) => advisor.advisor_id === current) ? current : "";
  attachSelect.value = state.advisors.some((advisor) => advisor.advisor_id === attachCurrent) ? attachCurrent : "";
}

function renderAdvisors() {
  const sourceById = Object.fromEntries(state.sources.map((source) => [source.source_id, source]));
  const items = state.advisors.map((advisor) => {
    const source = sourceById[advisor.source_ids[0]];
    const sourceText = source
      ? `${source.source_type} · ${source.fetch_status}${source.url ? ` · ${source.url}` : ""}`
      : "来源待补充";
    const evidenceCount = advisor.source_ids ? advisor.source_ids.length : 0;
    const risks = advisor.risk_notes && advisor.risk_notes.length ? advisor.risk_notes : [];
    const requirements = advisor.admission_requirements && advisor.admission_requirements.length
      ? advisor.admission_requirements.slice(0, 2).join("；")
      : "招生要求待补充";
    return `<div class="list-item">
      <div class="item-title">${escapeHtml(advisor.name_zh || "未识别姓名")} ${escapeHtml(advisor.title)}</div>
      <div class="item-meta">${escapeHtml(sourceText)}</div>
      <div class="advisor-grid">
        <div><span class="detail-label">机构</span>${escapeHtml([advisor.school, advisor.college || advisor.department].filter(Boolean).join(" · ") || "待补充")}</div>
        <div><span class="detail-label">实验室</span>${escapeHtml(advisor.lab_name || "待补充")}</div>
        <div><span class="detail-label">招生</span>${escapeHtml(`${advisor.recruiting_status || "unknown"} · ${requirements}`)}</div>
        <div><span class="detail-label">证据</span>${evidenceCount} 条来源 · ${advisor.identity_confirmed ? "身份信息较完整" : "身份需复核"}</div>
      </div>
      ${tagList(advisor.research_directions)}
      ${risks.length ? `<div class="risk-line">${escapeHtml(risks.join("；"))}</div>` : ""}
      <div class="button-row compact-actions">
        ${source ? `<button data-source-id="${escapeHtml(source.source_id)}">查看来源正文</button>` : ""}
        <button data-edit-advisor-id="${escapeHtml(advisor.advisor_id)}">编辑导师画像</button>
        <button data-create-target-advisor-id="${escapeHtml(advisor.advisor_id)}">创建申请目标</button>
      </div>
    </div>`;
  });
  $("advisorList").innerHTML = items.length ? items.join("") : "<div class='empty-state'>尚未保存导师资料。</div>";
}

function showAdvisorEditor(advisorId) {
  const advisor = state.advisors.find((item) => item.advisor_id === advisorId);
  if (!advisor) return toast("未找到导师画像");
  $("editAdvisorId").value = advisor.advisor_id;
  $("editNameZh").value = advisor.name_zh || "";
  $("editNameEn").value = advisor.name_en || "";
  $("editTitle").value = advisor.title || "";
  $("editEmail").value = advisor.email || "";
  $("editSchool").value = advisor.school || "";
  $("editCollege").value = advisor.college || advisor.department || "";
  $("editLabName").value = advisor.lab_name || "";
  $("editRecruitingStatus").value = advisor.recruiting_status || "unknown";
  $("editResearchDirections").value = listToText(advisor.research_directions);
  $("editAdmissionRequirements").value = listToText(advisor.admission_requirements);
  $("editPreferredStudentProfile").value = listToText(advisor.preferred_student_profile);
  $("editRepresentativePapers").value = listToText(advisor.representative_papers);
  $("editResearchProjects").value = listToText(advisor.research_projects);
  $("editRiskNotes").value = listToText(advisor.risk_notes);
  $("editIdentityConfirmed").checked = Boolean(advisor.identity_confirmed);
  $("advisorEditor").classList.remove("hidden");
}

function hideAdvisorEditor() {
  $("editAdvisorId").value = "";
  $("advisorEditor").classList.add("hidden");
}

function renderTargets() {
  const advisorById = Object.fromEntries(state.advisors.map((advisor) => [advisor.advisor_id, advisor]));
  const applicationByTarget = Object.fromEntries(state.applications.map((item) => [item.target_id, item]));
  const readinessByTarget = Object.fromEntries(
    ((state.readinessScore && state.readinessScore.target_scores) || []).map((item) => [item.target_id, item])
  );
  const rows = state.targets.map((target) => {
    const advisor = advisorById[target.advisor_id];
    const application = applicationByTarget[target.target_id] || {};
    const readiness = readinessByTarget[target.target_id];
    const options = applicationStatuses
      .map(([value, label]) => `<option value="${value}" ${value === application.status ? "selected" : ""}>${label}</option>`)
      .join("");
    return `<div class="target-row">
      <div><div class="target-name">${escapeHtml(target.name)}</div><div class="item-meta">${escapeHtml(advisor ? advisor.name_zh : "未绑定导师")} · ${escapeHtml(target.degree_track)}${readiness ? ` · 准备度 ${escapeHtml(String(readiness.score ?? 0))}` : ""}</div></div>
      <div class="item-meta">${escapeHtml(target.application_round)}</div>
      <div class="item-meta">${escapeHtml(target.deadline || "未设截止日期")}</div>
      <div><select class="status-select" data-application-id="${escapeHtml(application.application_id || "")}" ${application.application_id ? "" : "disabled"}>${options}</select></div>
      <div><button data-target-id="${escapeHtml(target.target_id)}">准备材料</button></div>
    </div>`;
  });
  $("targetList").innerHTML = rows.length ? rows.join("") : "<div class='empty-state'>尚未创建申请目标。</div>";

  const targetSelect = $("targetSelect");
  const selected = targetSelect.value;
  targetSelect.innerHTML = "<option value=''>请选择申请目标</option>";
  state.targets.forEach((target) => {
    const option = document.createElement("option");
    option.value = target.target_id;
    option.textContent = target.name;
    targetSelect.appendChild(option);
  });
  targetSelect.value = state.targets.some((target) => target.target_id === selected) ? selected : "";
}

function renderGeneratedMaterials() {
  const selectedTarget = $("targetSelect").value;
  const materials = state.materials
    .filter((item) => !selectedTarget || item.target_id === selectedTarget)
    .slice()
    .reverse();
  $("generatedList").innerHTML = materials.length
    ? materials
        .map((item) => `<div class="list-item"><div class="item-title">${escapeHtml(item.title)}</div><div class="item-meta">${escapeHtml(item.created_at)}</div><button data-material-id="${escapeHtml(item.material_id)}">查看材料</button></div>`)
        .join("")
    : "<div class='empty-state'>选择目标后生成材料会显示在这里。</div>";
  renderReferencePptOptions();
}

function precheckForReference(referenceId) {
  return (state.presentationPrechecks || [])
    .filter((item) => item.reference_id === referenceId)
    .slice(-1)[0];
}

function qualityForTask(taskId) {
  return (state.presentationQualityReports || [])
    .filter((item) => item.task_id === taskId)
    .slice(-1)[0];
}

function renderReferencePptOptions(selectedId = "") {
  const select = $("referencePptSelect");
  if (!select) return;
  const current = selectedId || select.value;
  select.innerHTML = "<option value=''>不使用参考 PPT</option>";
  (state.referencePresentations || []).forEach((item) => {
    const option = document.createElement("option");
    option.value = item.reference_id;
    option.textContent = item.original_filename || item.reference_id;
    select.appendChild(option);
  });
  select.value = (state.referencePresentations || []).some((item) => item.reference_id === current)
    ? current
    : "";
  renderReferencePptView();
}

function renderReferencePptView() {
  const view = $("referencePptView");
  if (!view) return;
  const referenceId = $("referencePptSelect").value;
  if (!referenceId) {
    view.innerHTML = "<div class='empty-state'>未选择参考 PPT。</div>";
    return;
  }
  const report = precheckForReference(referenceId);
  if (!report) {
    view.innerHTML = "<div class='empty-state'>尚未找到预检报告。</div>";
    return;
  }
  const issues = (report.issues || [])
    .map((issue) => `<li>${escapeHtml(issue.severity)}：${escapeHtml(issue.message)}</li>`)
    .join("");
  view.innerHTML = `<div class="quality-summary ${report.passed ? "low" : "medium"}">
    <strong>参考 PPT 预检：${report.passed ? "可用" : "建议复核"}</strong>
    <div class="item-meta">${escapeHtml(String(report.slide_count))} 页 · 元素 ${escapeHtml(String(report.total_shape_count))} 个 · 单页最多 ${escapeHtml(String(report.max_shapes_per_slide))} 个</div>
    <ul>${issues || "<li>未发现阻断问题。</li>"}</ul>
  </div>`;
}

function renderMaterial(material, quality = null, workflow = null) {
  state.selectedMaterial = material;
  $("materialTitle").textContent = material.title;
  $("materialMeta").textContent = `${material.material_type} · ${material.created_at}`;
  $("materialView").textContent = material.content;
  const download = $("downloadMaterialBtn");
  download.href = `/api/generated/${encodeURIComponent(material.material_id)}/download`;
  download.classList.remove("hidden");
  const sections = [];
  if (quality) {
    const messages = quality.checks
      .map((check) => `<li>${check.passed ? "通过" : "需复核"}：${escapeHtml(check.message)}</li>`)
      .join("");
    sections.push(`<div class="quality-summary ${quality.risk_level}"><strong>${quality.passed ? "基础质量检查通过" : "建议人工复核"}，风险：${escapeHtml(quality.risk_level)}</strong><ul>${messages}</ul></div>`);
  }
  if (workflow && workflow.review) {
    const review = workflow.review;
    const issues = (review.issues || [])
      .map((issue) => `<li>${escapeHtml(issue.message || issue.type)}</li>`)
      .join("");
    const optional = (review.optional_improvements || [])
      .map((item) => `<li>${escapeHtml(item)}</li>`)
      .join("");
    sections.push(`<div class="quality-summary ${review.risk_level}"><strong>Reviewer：${review.passed ? "通过" : "需要修改"}</strong><ul>${issues || optional || "<li>未发现必须修改项。</li>"}</ul></div>`);
  }
  if (workflow && workflow.evidence_audit) {
    const audit = workflow.evidence_audit;
    const claims = (audit.claims || [])
      .slice(0, 6)
      .map((claim) => `<li>${escapeHtml(claim.status)}：${escapeHtml(claim.message)}</li>`)
      .join("");
    const confirmations = (audit.needs_confirmation || [])
      .map((item) => `<li>需确认：${escapeHtml(item)}</li>`)
      .join("");
    sections.push(`<div class="quality-summary ${audit.passed ? "low" : "high"}"><strong>Evidence Auditor：${audit.passed ? "证据通过" : "证据需复核"}</strong><ul>${claims}${confirmations}</ul></div>`);
  }
  if (!sections.length) {
    $("qualityView").innerHTML = "";
    return;
  }
  $("qualityView").innerHTML = sections.join("");
}

function renderMatchReport(report) {
  state.selectedMaterial = null;
  $("materialTitle").textContent = "匹配分析报告";
  $("materialMeta").textContent = `${report.tier || "unknown"} · ${report.fit_score ?? 0} 分`;
  const strengths = (report.strengths || [])
    .map((item) => `- ${item.point || item.dimension || "匹配点待补充"}`)
    .join("\n");
  const gaps = (report.gaps || [])
    .map((item) => `- ${item.point || "风险项待补充"}${item.suggestion ? `；建议：${item.suggestion}` : ""}`)
    .join("\n");
  const actions = (report.recommended_actions || []).map((item) => `- ${item}`).join("\n");
  $("materialView").textContent = [
    `# 匹配分析报告`,
    "",
    `匹配等级：${report.tier || "unknown"}`,
    `匹配分数：${report.fit_score ?? 0}`,
    "",
    `## 总结`,
    report.summary || "暂无总结。",
    "",
    `## 匹配点`,
    strengths || "- 暂未识别到明确匹配点。",
    "",
    `## 风险与缺口`,
    gaps || "- 暂未识别到主要风险。",
    "",
    `## 下一步`,
    actions || "- 补充学生资料和导师来源后重新分析。",
  ].join("\n");
  $("downloadMaterialBtn").classList.add("hidden");
  $("qualityView").innerHTML = "";
}

function renderAll() {
  renderMetrics();
  renderDashboard();
  renderReadinessDashboard();
  renderProfile();
  renderAdvisorOptions();
  renderAdvisors();
  renderTargets();
  renderGeneratedMaterials();
  renderTargetReadiness();
  renderLifecycle();
  renderStrategy();
}

async function refresh() {
  try {
    try {
      state.profile = await api("/api/profile");
    } catch {
      state.profile = null;
    }
    [
      state.advisors,
      state.sources,
      state.targets,
      state.applications,
      state.archives,
      state.communications,
      state.emailSignals,
      state.materials,
      state.userDocuments,
      state.readinessScore,
      state.gapPlans,
      state.referencePresentations,
      state.presentationPrechecks,
      state.presentationQualityReports,
    ] = await Promise.all([
      api("/api/advisors"),
      api("/api/advisor-sources"),
      api("/api/targets"),
      api("/api/applications"),
      api("/api/application-archives"),
      api("/api/communications"),
      api("/api/email-signals"),
      api("/api/generated"),
      api("/api/user-documents").then((manifest) => manifest.documents || []),
      api("/api/readiness-score"),
      api("/api/gap-plans"),
      api("/api/reference-presentations"),
      api("/api/presentation-prechecks"),
      api("/api/presentation-quality-reports"),
    ]);
    const triageReports = await api("/api/target-triage");
    const expansionReports = await api("/api/profile-expansion");
    const [templateRegistry, sourceConnectorRegistry] = await Promise.all([
      api("/api/template-registry/status"),
      api("/api/source-connectors/status"),
    ]);
    state.templateRegistry = templateRegistry;
    state.sourceConnectorRegistry = sourceConnectorRegistry;
    state.triageReport = triageReports.slice(-1)[0] || null;
    state.profileExpansionReport = expansionReports.slice(-1)[0] || null;
    renderAll();
  } catch (error) {
    toast(`刷新失败：${error.message}`);
  }
}

async function saveProfile() {
  const text = $("profileText").value.trim();
  const file = $("profileFile").files[0];
  if (!text && !file) return toast("请先粘贴或上传学生资料");
  const form = new FormData();
  form.append("text", text);
  form.append("category", $("profileCategory").value);
  if (file) form.append("file", file);
  const response = await fetch("/api/profile/upload", { method: "POST", body: form });
  if (!response.ok) return toast("学生画像生成失败");
  state.profile = await response.json();
  $("profileFile").value = "";
  await refresh();
  toast("学生画像已生成");
}

async function saveProfileConfirmations() {
  if (!state.profile) return toast("尚未创建学生画像");
  const confirmationMap = { ...(state.profile.confirmation_map || {}) };
  document.querySelectorAll("[data-profile-field]").forEach((node) => {
    confirmationMap[node.dataset.profileField] = node.value;
  });
  try {
    state.profile = await api("/api/profile", {
      method: "PUT",
      body: JSON.stringify({ ...state.profile, confirmation_map: confirmationMap }),
    });
    renderProfile();
    toast("字段确认状态已保存");
  } catch (error) {
    toast(`保存字段确认失败：${error.message}`);
  }
}

async function saveAdvisor() {
  const payload = {
    advisor_id: $("advisorAttachSelect").value,
    source_type: $("sourceType").value,
    url: $("advisorUrl").value.trim(),
    manual_text: $("advisorText").value.trim(),
    trusted: $("sourceTrusted").checked,
  };
  if (!payload.url && !payload.manual_text) return toast("请提供公开 URL 或粘贴正文");
  try {
    const result = await api("/api/advisor-sources", { method: "POST", body: JSON.stringify(payload) });
    $("advisorUrl").value = "";
    $("advisorText").value = "";
    $("advisorAttachSelect").value = result.advisor.advisor_id;
    toast(result.source.fetch_status === "success" ? "导师资料已抓取并解析" : "已保存手动资料或抓取失败兜底");
    await refresh();
  } catch (error) {
    toast(`保存导师资料失败：${error.message}`);
  }
}

async function createTarget() {
  const name = $("targetName").value.trim();
  if (!name) return toast("请填写目标名称");
  const advisorId = $("advisorSelect").value;
  const advisor = state.advisors.find((item) => item.advisor_id === advisorId);
  const payload = {
    name,
    advisor_id: advisorId,
    school: advisor ? advisor.school : "",
    college: advisor ? advisor.college : "",
    degree_track: $("degreeTrack").value,
    application_round: $("applicationRound").value,
    deadline: $("deadline").value,
    source_ids: advisor ? advisor.source_ids : [],
  };
  await api("/api/targets", { method: "POST", body: JSON.stringify(payload) });
  $("targetName").value = "";
  $("deadline").value = "";
  toast("申请目标已创建");
  await refresh();
}

async function saveAdvisorEdit() {
  const advisorId = $("editAdvisorId").value;
  if (!advisorId) return toast("请先选择导师画像");
  const directions = textToList($("editResearchDirections").value);
  const payload = {
    name_zh: $("editNameZh").value.trim(),
    name_en: $("editNameEn").value.trim(),
    title: $("editTitle").value.trim(),
    email: $("editEmail").value.trim(),
    school: $("editSchool").value.trim(),
    college: $("editCollege").value.trim(),
    department: $("editCollege").value.trim(),
    lab_name: $("editLabName").value.trim(),
    recruiting_status: $("editRecruitingStatus").value,
    research_directions: directions,
    recent_focus: directions.slice(0, 3),
    keywords: directions,
    admission_requirements: textToList($("editAdmissionRequirements").value),
    preferred_student_profile: textToList($("editPreferredStudentProfile").value),
    representative_papers: textToList($("editRepresentativePapers").value),
    research_projects: textToList($("editResearchProjects").value),
    risk_notes: textToList($("editRiskNotes").value),
    identity_confirmed: $("editIdentityConfirmed").checked,
  };
  try {
    await api(`/api/advisors/${advisorId}`, { method: "PUT", body: JSON.stringify(payload) });
    toast("导师画像已保存");
    hideAdvisorEditor();
    await refresh();
  } catch (error) {
    toast(`导师画像保存失败：${error.message}`);
  }
}

async function createTargetFromAdvisor(advisorId) {
  try {
    const result = await api(`/api/advisors/${advisorId}/target`, {
      method: "POST",
      body: JSON.stringify({
        degree_track: $("degreeTrack").value,
        application_round: $("applicationRound").value,
        deadline: $("deadline").value,
        priority: "medium",
      }),
    });
    toast("已从导师画像创建申请目标");
    await refresh();
    $("targetSelect").value = result.target.target_id;
    renderGeneratedMaterials();
    showView("targets");
  } catch (error) {
    toast(`创建申请目标失败：${error.message}`);
  }
}

function currentTargetId() {
  const id = $("targetSelect").value;
  if (!id) toast("请先选择申请目标");
  return id;
}

async function generate(path, label) {
  const id = currentTargetId();
  if (!id) return;
  try {
    const result = await api(`/api/targets/${id}/${path}`, { method: "POST" });
    if (path === "match") {
      renderMatchReport(result);
    } else {
      renderMaterial(result.material || result, result.quality || null, result.agent_run ? result : null);
    }
    toast(`${label}已生成`);
    await refresh();
  } catch (error) {
    toast(`${label}生成失败：${error.message}`);
  }
}

function renderPresentationTask(task) {
  const target = $("presentationTaskView");
  if (!task) {
    target.innerHTML = "";
    return;
  }
  const quality = qualityForTask(task.task_id);
  const qualityHtml = quality
    ? `<div class="item-meta">PPT 质量分 ${escapeHtml(String(quality.total_score))} · 内容 ${escapeHtml(String(quality.content_score))} · 设计 ${escapeHtml(String(quality.design_score))} · 连贯 ${escapeHtml(String(quality.coherence_score))}</div>`
    : task.quality_score
      ? `<div class="item-meta">PPT 质量分 ${escapeHtml(String(task.quality_score))}</div>`
      : "";
  const fallbackHtml = task.fallback_reason
    ? `<div class="item-meta">Fallback：${escapeHtml(task.fallback_reason)}</div>`
    : "";
  if (task.status === "completed") {
    target.innerHTML = `<div class="quality-summary"><strong>可编辑 PPTX 已生成</strong><div class="item-meta">${escapeHtml(task.engine_name || "LocalPptxAdapter")} · ${escapeHtml(task.message)}</div>${fallbackHtml}${qualityHtml}<a class="text-button" href="/api/tasks/${encodeURIComponent(task.task_id)}/download">下载 PPTX</a></div>`;
    return;
  }
  const message = task.error || task.message || "正在处理";
  target.innerHTML = `<div class="quality-summary ${task.status === "failed" ? "high" : "medium"}"><strong>${escapeHtml(task.status)} · ${task.progress}%</strong><div class="item-meta">${escapeHtml(message)}</div></div>`;
}

function pptNumberValue(id, fallback) {
  const value = Number.parseInt($(id).value, 10);
  return Number.isFinite(value) ? value : fallback;
}

async function generatePptx() {
  const id = currentTargetId();
  if (!id) return;
  $("pptxBtn").disabled = true;
  try {
    const task = await api(`/api/targets/${id}/ppt`, {
      method: "POST",
      body: JSON.stringify({
        reference_file_id: $("referencePptSelect").value,
        num_slides: Math.max(1, Math.min(12, pptNumberValue("pptSlideCount", 5))),
        duration_minutes: Math.max(1, Math.min(20, pptNumberValue("pptDurationMinutes", 5))),
        length_factor: $("pptLengthFactor").value,
      }),
    });
    renderPresentationTask(task);
    toast(task.status === "completed" ? "可编辑 PPTX 已生成" : "PPTX 任务已提交");
    await refresh();
  } catch (error) {
    toast(`PPTX 生成失败：${error.message}`);
  } finally {
    $("pptxBtn").disabled = false;
  }
}

async function uploadReferencePpt() {
  const file = $("referencePptFile").files[0];
  if (!file) return toast("请先选择 .pptx 文件");
  const form = new FormData();
  form.append("file", file);
  $("uploadReferencePptBtn").disabled = true;
  try {
    const result = await api("/api/reference-presentations", { method: "POST", body: form });
    state.referencePresentations = [...(state.referencePresentations || []), result.reference];
    state.presentationPrechecks = [...(state.presentationPrechecks || []), result.precheck];
    $("referencePptFile").value = "";
    renderReferencePptOptions(result.reference.reference_id);
    toast(result.precheck.passed ? "参考 PPT 已上传并通过预检" : "参考 PPT 已上传，建议复核预检提示");
  } catch (error) {
    toast(`参考 PPT 上传失败：${error.message}`);
  } finally {
    $("uploadReferencePptBtn").disabled = false;
  }
}

async function updateApplication(applicationId, status) {
  if (!applicationId) return;
  try {
    await api(`/api/applications/${applicationId}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    toast("申请状态已更新");
    await refresh();
  } catch (error) {
    toast(`状态更新失败：${error.message}`);
  }
}

function currentLifecycleTargetId() {
  const id = $("readinessTargetSelect").value || $("targetSelect").value;
  if (!id) toast("请先选择申请目标");
  return id;
}

async function createArchive() {
  const id = currentLifecycleTargetId();
  if (!id) return;
  try {
    const materials = state.materials.filter((item) => item.target_id === id).map((item) => item.material_id);
    await api(`/api/targets/${id}/archive`, {
      method: "POST",
      body: JSON.stringify({
        material_ids: materials,
        stage: "drafted",
        notes: "前端手动创建归档",
      }),
    });
    toast("申请归档已创建");
    await refresh();
  } catch (error) {
    toast(`创建归档失败：${error.message}`);
  }
}

async function createCommunication(kind) {
  const id = currentLifecycleTargetId();
  if (!id) return;
  try {
    await api(`/api/targets/${id}/communications`, {
      method: "POST",
      body: JSON.stringify({
        kind,
        source_material_ids: state.materials.filter((item) => item.target_id === id).map((item) => item.material_id),
      }),
    });
    toast(`${kind} 草稿已生成`);
    await refresh();
  } catch (error) {
    toast(`生成沟通草稿失败：${error.message}`);
  }
}

async function checkEmailSync() {
  try {
    const result = await api("/api/email-sync/status?provider=gmail", { method: "POST" });
    state.lifecycleSync = { title: "邮箱同步骨架", message: result.message };
    renderLifecycle();
  } catch (error) {
    toast(`邮箱同步检查失败：${error.message}`);
  }
}

async function importEmailSignals() {
  const rawText = $("emailSignalText").value.trim();
  if (!rawText) return toast("请先粘贴邮件文本");
  $("emailImportBtn").disabled = true;
  try {
    const result = await api("/api/email-signals/import", {
      method: "POST",
      body: JSON.stringify({ provider: "gmail", raw_text: rawText }),
    });
    state.emailSignals = [...(state.emailSignals || []), ...(result.candidates || [])];
    $("emailSignalText").value = "";
    state.lifecycleSync = { title: "邮箱信号识别", message: result.message };
    renderLifecycle();
    toast(`识别到 ${result.candidates.length} 条候选信号`);
  } catch (error) {
    toast(`邮件信号识别失败：${error.message}`);
  } finally {
    $("emailImportBtn").disabled = false;
  }
}

async function decideEmailSignal(candidateId, action) {
  try {
    await api(`/api/email-signals/${encodeURIComponent(candidateId)}/${action}`, {
      method: "POST",
      body: JSON.stringify({ apply_to_outcome: true }),
    });
    toast(action === "approve" ? "邮件信号已确认写入" : "邮件信号已拒绝");
    await refresh();
  } catch (error) {
    toast(`邮件信号处理失败：${error.message}`);
  }
}

async function checkPipelineSync() {
  try {
    const result = await api("/api/pipeline-sync/status", {
      method: "POST",
      body: JSON.stringify({ provider: "notion" }),
    });
    state.lifecycleSync = { title: "外部看板同步骨架", message: result.message };
    renderLifecycle();
  } catch (error) {
    toast(`外部同步检查失败：${error.message}`);
  }
}

async function generateTriageReport() {
  try {
    state.triageReport = await api("/api/target-triage", {
      method: "POST",
      body: JSON.stringify({ include_all_targets: true }),
    });
    renderStrategy();
    toast("批量目标粗排已生成");
  } catch (error) {
    toast(`批量粗排失败：${error.message}`);
  }
}

async function generateProfileExpansion() {
  try {
    state.profileExpansionReport = await api("/api/profile-expansion", { method: "POST" });
    renderStrategy();
    toast("画像扩展候选已生成");
  } catch (error) {
    toast(`画像扩展失败：${error.message}`);
  }
}

async function generateGapPlan() {
  const targetId = $("readinessTargetSelect").value || $("targetSelect").value;
  if (!targetId) return toast("请先选择申请目标");
  try {
    const plan = await api("/api/gap-plans", {
      method: "POST",
      body: JSON.stringify({ target_id: targetId }),
    });
    state.gapPlans = [...(state.gapPlans || []), plan];
    renderStrategy();
    toast("Gap / Upskill 计划已生成");
  } catch (error) {
    toast(`生成 gap plan 失败：${error.message}`);
  }
}

async function checkTemplateRegistry() {
  try {
    const result = await api("/api/template-registry/status");
    state.templateRegistry = result;
    state.strategyStatus = {
      title: "模板 registry",
      message: `${result.activation_policy} ${result.privacy_policy}`,
    };
    renderStrategy();
    renderCustomTemplateOptions();
  } catch (error) {
    toast(`模板 registry 检查失败：${error.message}`);
  }
}

async function checkSourceConnectors() {
  try {
    const result = await api("/api/source-connectors/status");
    state.sourceConnectorRegistry = result;
    state.strategyStatus = {
      title: "来源连接器 registry",
      message: result.access_policy,
    };
    renderStrategy();
  } catch (error) {
    toast(`来源连接器检查失败：${error.message}`);
  }
}

async function saveCustomTemplate() {
  try {
    const payload = customTemplatePayload();
    const existingId = state.selectedCustomTemplate?.template_id;
    const template = existingId
      ? await api(`/api/templates/${encodeURIComponent(existingId)}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        })
      : await api("/api/templates", {
          method: "POST",
          body: JSON.stringify(payload),
        });
    await checkTemplateRegistry();
    renderCustomTemplateOptions(template.template_id);
    toast("模板已保存");
  } catch (error) {
    toast(`模板保存失败：${error.message}`);
  }
}

async function toggleCustomTemplateLifecycle() {
  const templateId = $("customTemplateSelect").value || state.selectedCustomTemplate?.template_id;
  if (!templateId) return toast("请先选择一个用户模板");
  const nextStatus = $("customTemplateStatus").value;
  try {
    const template = await api(`/api/templates/${encodeURIComponent(templateId)}/lifecycle`, {
      method: "PATCH",
      body: JSON.stringify({ status: nextStatus }),
    });
    await checkTemplateRegistry();
    renderCustomTemplateOptions(template.template_id);
    toast("模板状态已更新");
  } catch (error) {
    toast(`模板状态更新失败：${error.message}`);
  }
}

async function showCustomTemplateDiff() {
  const templateId = $("customTemplateSelect").value || state.selectedCustomTemplate?.template_id;
  if (!templateId) return toast("请先选择一个用户模板");
  try {
    const diff = await api(`/api/templates/${encodeURIComponent(templateId)}/diff`);
    $("templateDiffView").textContent = diff.diff_text || diff.summary || "没有差异";
  } catch (error) {
    toast(`查看 diff 失败：${error.message}`);
  }
}

async function checkPdfReadability() {
  const file = $("pdfReadabilityFile").files[0];
  if (!file) return toast("请先选择 PDF 文件");
  const form = new FormData();
  form.append("file", file);
  form.append("expected_fields", $("pdfReadabilityFields").value || "");
  if (state.selectedMaterial?.material_id) {
    form.append("material_id", state.selectedMaterial.material_id);
  }
  try {
    const report = await api("/api/pdf/readability-check", { method: "POST", body: form });
    state.pdfReadabilityReport = report;
    renderPdfReadabilityReport(report);
    toast(report.readable ? "PDF 可读性检查通过" : "PDF 需要复核");
    await refresh();
  } catch (error) {
    toast(`PDF 检查失败：${error.message}`);
  }
}

function renderPdfReadabilityReport(report) {
  const view = $("pdfReadabilityView");
  if (!view) return;
  if (!report) {
    view.innerHTML = "";
    return;
  }
  const issues = (report.issues || [])
    .map((issue) => `<li>${escapeHtml(issue.severity)}：${escapeHtml(issue.message)}</li>`)
    .join("");
  const suggestions = (report.suggestions || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  view.innerHTML = `<div class="quality-summary ${report.readable ? "low" : "medium"}">
    <strong>PDF ${report.readable ? "可读" : "需复核"}</strong>
    <div class="item-meta">${escapeHtml(report.filename || "")} · ${escapeHtml(String(report.page_count || 0))} 页 · 文本层 ${report.text_layer_detected ? "有" : "无"}</div>
    <ul>${issues || "<li>未发现阻断问题。</li>"}</ul>
    ${suggestions ? `<div class="item-meta">建议</div><ul>${suggestions}</ul>` : ""}
  </div>`;
}

async function runSourceConnectorLiveTest(connectorId) {
  const connector = (state.sourceConnectorRegistry?.connectors || []).find(
    (item) => item.connector_id === connectorId
  );
  const url = connector?.test_urls?.[0];
  const query = connector?.test_queries?.[0];
  if (!connector || !url || !query) {
    return toast("该 connector 没有可执行的公开测试 URL 或查询词");
  }
  if (!window.confirm(`确认访问公开 URL 并遵守 robots.txt / ToS？\n${url}`)) return;
  try {
    const result = await api(`/api/source-connectors/${encodeURIComponent(connectorId)}/live-test`, {
      method: "POST",
      body: JSON.stringify({ url, query, tos_acknowledged: true }),
    });
    state.sourceConnectorRegistry = await api("/api/source-connectors/status");
    state.strategyStatus = {
      title: "来源连接器 live test",
      message: result.registration_eligible
        ? `${connector.name} 已通过公开页面测试，可以注册。`
        : `${connector.name} 未通过测试：${result.error || "请改用手动粘贴兜底。"}`,
    };
    renderStrategy();
    toast(result.registration_eligible ? "live test 通过" : "live test 未通过");
  } catch (error) {
    toast(`live test 失败：${error.message}`);
  }
}

async function showSource(sourceId) {
  const source = await api(`/api/advisor-sources/${sourceId}`);
  $("materialTitle").textContent = source.title || "导师来源正文";
  $("materialMeta").textContent = `${source.source_type} · ${source.fetch_status} · ${source.content_hash || "无内容指纹"}`;
  $("materialView").textContent = source.cleaned_text || source.raw_text || "来源正文为空";
  $("qualityView").innerHTML = "";
  $("downloadMaterialBtn").classList.add("hidden");
  showView("materials");
}

async function showMaterial(materialId) {
  const material = await api(`/api/generated/${materialId}`);
  renderMaterial(material);
}

async function generateReport() {
  try {
    const report = await api("/api/report");
    $("reportView").textContent = report.content;
    toast("进度报告已生成");
  } catch (error) {
    toast(`报告生成失败：${error.message}`);
  }
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => showView(button.dataset.view));
});
document.querySelectorAll("[data-view-link]").forEach((button) => {
  button.addEventListener("click", () => showView(button.dataset.viewLink));
});

$("refreshBtn").addEventListener("click", refresh);
$("saveProfileBtn").addEventListener("click", saveProfile);
$("saveProfileConfirmationsBtn").addEventListener("click", saveProfileConfirmations);
$("saveAdvisorBtn").addEventListener("click", saveAdvisor);
$("createTargetBtn").addEventListener("click", createTarget);
$("matchBtn").addEventListener("click", () => generate("match", "匹配分析"));
$("emailBtn").addEventListener("click", () => generate("materials/contact-email", "套磁邮件"));
$("questionsBtn").addEventListener("click", () => generate("materials/interview-questions", "面试问题"));
$("pptBtn").addEventListener("click", () => generate("materials/ppt-outline", "PPT 大纲"));
$("pptxBtn").addEventListener("click", generatePptx);
$("uploadReferencePptBtn").addEventListener("click", uploadReferencePpt);
$("referencePptSelect").addEventListener("change", renderReferencePptView);
$("generateReportBtn").addEventListener("click", generateReport);
$("targetSelect").addEventListener("change", renderGeneratedMaterials);
$("readinessTargetSelect").addEventListener("change", renderTargetReadiness);
$("archiveTargetBtn").addEventListener("click", createArchive);
$("followUpBtn").addEventListener("click", () => createCommunication("follow_up"));
$("thankYouBtn").addEventListener("click", () => createCommunication("thank_you"));
$("emailSyncBtn").addEventListener("click", checkEmailSync);
$("emailImportBtn").addEventListener("click", importEmailSignals);
$("pipelineSyncBtn").addEventListener("click", checkPipelineSync);
$("triageBtn").addEventListener("click", generateTriageReport);
$("profileExpandBtn").addEventListener("click", generateProfileExpansion);
$("gapPlanBtn").addEventListener("click", generateGapPlan);
$("templateRegistryBtn").addEventListener("click", checkTemplateRegistry);
$("sourceConnectorBtn").addEventListener("click", checkSourceConnectors);
$("saveTemplateBtn").addEventListener("click", saveCustomTemplate);
$("activateTemplateBtn").addEventListener("click", toggleCustomTemplateLifecycle);
$("archiveTemplateBtn").addEventListener("click", async () => {
  $("customTemplateStatus").value = "archived";
  await toggleCustomTemplateLifecycle();
});
$("diffTemplateBtn").addEventListener("click", showCustomTemplateDiff);
$("customTemplateSelect").addEventListener("change", () => {
  const template = customTemplates().find((item) => item.template_id === $("customTemplateSelect").value);
  if (template) fillCustomTemplateEditor(template);
  else clearCustomTemplateEditor();
});
$("customTemplateFile").addEventListener("change", async () => {
  const file = $("customTemplateFile").files[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  form.append("template_type", $("customTemplateType").value || "contact_email");
  form.append("name", $("customTemplateName").value || file.name.replace(/\.[^.]+$/, ""));
  form.append("description", $("customTemplateDescription").value || "");
  try {
    const template = await api("/api/templates/upload", { method: "POST", body: form });
    await checkTemplateRegistry();
    renderCustomTemplateOptions(template.template_id);
    toast("模板文件已导入");
  } catch (error) {
    toast(`模板导入失败：${error.message}`);
  } finally {
    $("customTemplateFile").value = "";
  }
});
$("pdfReadabilityBtn").addEventListener("click", checkPdfReadability);
$("saveAdvisorEditBtn").addEventListener("click", saveAdvisorEdit);
$("cancelAdvisorEditBtn").addEventListener("click", hideAdvisorEditor);

$("advisorList").addEventListener("click", (event) => {
  const sourceId = event.target.dataset.sourceId;
  if (sourceId) showSource(sourceId);
  const editAdvisorId = event.target.dataset.editAdvisorId;
  if (editAdvisorId) showAdvisorEditor(editAdvisorId);
  const advisorId = event.target.dataset.createTargetAdvisorId;
  if (advisorId) createTargetFromAdvisor(advisorId);
});
$("targetList").addEventListener("click", (event) => {
  const targetId = event.target.dataset.targetId;
  if (!targetId) return;
  $("targetSelect").value = targetId;
  renderGeneratedMaterials();
  showView("materials");
});
$("targetList").addEventListener("change", (event) => {
  const applicationId = event.target.dataset.applicationId;
  if (applicationId) updateApplication(applicationId, event.target.value);
});
$("emailSignalView").addEventListener("click", (event) => {
  const approveId = event.target.dataset.approveEmailSignalId;
  if (approveId) decideEmailSignal(approveId, "approve");
  const rejectId = event.target.dataset.rejectEmailSignalId;
  if (rejectId) decideEmailSignal(rejectId, "reject");
});
$("strategyView").addEventListener("click", (event) => {
  const connectorId = event.target.dataset.sourceConnectorId;
  if (connectorId) {
    runSourceConnectorLiveTest(connectorId);
    return;
  }
  const targetId = event.target.dataset.strategyTargetId;
  if (!targetId) return;
  $("targetSelect").value = targetId;
  $("readinessTargetSelect").value = targetId;
  renderGeneratedMaterials();
  renderTargetReadiness();
  showView("materials");
});
$("generatedList").addEventListener("click", (event) => {
  const materialId = event.target.dataset.materialId;
  if (materialId) showMaterial(materialId);
});

refresh();
