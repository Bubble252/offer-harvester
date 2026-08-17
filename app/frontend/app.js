const state = {
  profile: null,
  advisors: [],
  sources: [],
  targets: [],
  applications: [],
  materials: [],
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
  ["researching", "调研中"],
  ["ready_to_contact", "待联系"],
  ["contacted", "已联系"],
  ["replied", "已回复"],
  ["materials_preparing", "准备材料"],
  ["submitted", "已提交"],
  ["shortlisted", "入围"],
  ["interview_scheduled", "已约面试"],
  ["interview_done", "已完成面试"],
  ["accepted", "已录取"],
  ["rejected", "未录取"],
  ["withdrawn", "已放弃"],
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

function renderProfile() {
  if (!state.profile) {
    $("profileView").innerHTML = "<div class='empty-state'>尚未创建学生画像。</div>";
    return;
  }
  const profile = state.profile;
  $("profileView").innerHTML = [
    ["姓名", escapeHtml(profile.name)],
    ["教育背景", escapeHtml(profile.education || "待补充")],
    ["GPA", escapeHtml(profile.gpa || "待补充")],
    ["排名", escapeHtml(profile.rank || "待补充")],
    ["研究兴趣", tagList(profile.research_interests)],
    ["项目经历", tagList(profile.projects)],
    ["论文成果", tagList(profile.publications)],
    ["竞赛奖项", tagList(profile.competitions)],
    ["风险项", tagList(profile.risks)],
  ]
    .map(([label, value]) => `<div class="detail-group"><span class="detail-label">${label}</span><div>${value}</div></div>`)
    .join("");
}

function renderAdvisorOptions() {
  const select = $("advisorSelect");
  const current = select.value;
  select.innerHTML = "<option value=''>不绑定导师</option>";
  state.advisors.forEach((advisor) => {
    const option = document.createElement("option");
    option.value = advisor.advisor_id;
    option.textContent = advisor.name_zh || advisor.homepage_url || advisor.advisor_id;
    select.appendChild(option);
  });
  select.value = state.advisors.some((advisor) => advisor.advisor_id === current) ? current : "";
}

function renderAdvisors() {
  const sourceById = Object.fromEntries(state.sources.map((source) => [source.source_id, source]));
  const items = state.advisors.map((advisor) => {
    const source = sourceById[advisor.source_ids[0]];
    const sourceText = source
      ? `${source.source_type} · ${source.fetch_status}${source.url ? ` · ${source.url}` : ""}`
      : "来源待补充";
    return `<div class="list-item">
      <div class="item-title">${escapeHtml(advisor.name_zh || "未识别姓名")} ${escapeHtml(advisor.title)}</div>
      <div class="item-meta">${escapeHtml(sourceText)}</div>
      <div class="tag-row">${tagList(advisor.research_directions)}</div>
      ${source ? `<button data-source-id="${escapeHtml(source.source_id)}">查看来源正文</button>` : ""}
    </div>`;
  });
  $("advisorList").innerHTML = items.length ? items.join("") : "<div class='empty-state'>尚未保存导师资料。</div>";
}

function renderTargets() {
  const advisorById = Object.fromEntries(state.advisors.map((advisor) => [advisor.advisor_id, advisor]));
  const applicationByTarget = Object.fromEntries(state.applications.map((item) => [item.target_id, item]));
  const rows = state.targets.map((target) => {
    const advisor = advisorById[target.advisor_id];
    const application = applicationByTarget[target.target_id] || {};
    const options = applicationStatuses
      .map(([value, label]) => `<option value="${value}" ${value === application.status ? "selected" : ""}>${label}</option>`)
      .join("");
    return `<div class="target-row">
      <div><div class="target-name">${escapeHtml(target.name)}</div><div class="item-meta">${escapeHtml(advisor ? advisor.name_zh : "未绑定导师")} · ${escapeHtml(target.degree_track)}</div></div>
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
}

function renderMaterial(material, quality = null) {
  state.selectedMaterial = material;
  $("materialTitle").textContent = material.title;
  $("materialMeta").textContent = `${material.material_type} · ${material.created_at}`;
  $("materialView").textContent = material.content;
  const download = $("downloadMaterialBtn");
  download.href = `/api/generated/${encodeURIComponent(material.material_id)}/download`;
  download.classList.remove("hidden");
  if (!quality) {
    $("qualityView").innerHTML = "";
    return;
  }
  const messages = quality.checks
    .map((check) => `<li>${check.passed ? "通过" : "需复核"}：${escapeHtml(check.message)}</li>`)
    .join("");
  $("qualityView").innerHTML = `<div class="quality-summary ${quality.risk_level}"><strong>${quality.passed ? "基础质量检查通过" : "建议人工复核"}，风险：${escapeHtml(quality.risk_level)}</strong><ul>${messages}</ul></div>`;
}

function renderAll() {
  renderMetrics();
  renderDashboard();
  renderProfile();
  renderAdvisorOptions();
  renderAdvisors();
  renderTargets();
  renderGeneratedMaterials();
}

async function refresh() {
  try {
    try {
      state.profile = await api("/api/profile");
    } catch {
      state.profile = null;
    }
    [state.advisors, state.sources, state.targets, state.applications, state.materials] = await Promise.all([
      api("/api/advisors"),
      api("/api/advisor-sources"),
      api("/api/targets"),
      api("/api/applications"),
      api("/api/generated"),
    ]);
    renderAll();
  } catch (error) {
    toast(`刷新失败：${error.message}`);
  }
}

async function saveProfile() {
  const text = $("profileText").value.trim();
  if (!text) return toast("请先粘贴学生资料");
  const form = new FormData();
  form.append("text", text);
  const response = await fetch("/api/profile/upload", { method: "POST", body: form });
  if (!response.ok) return toast("学生画像生成失败");
  state.profile = await response.json();
  renderProfile();
  renderMetrics();
  toast("学生画像已生成");
}

async function saveAdvisor() {
  const payload = {
    source_type: $("sourceType").value,
    url: $("advisorUrl").value.trim(),
    manual_text: $("advisorText").value.trim(),
    trusted: true,
  };
  if (!payload.url && !payload.manual_text) return toast("请提供公开 URL 或粘贴正文");
  try {
    const result = await api("/api/advisor-sources", { method: "POST", body: JSON.stringify(payload) });
    $("advisorUrl").value = "";
    $("advisorText").value = "";
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
    renderMaterial(result.material || result, result.quality || null);
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
  if (task.status === "completed") {
    target.innerHTML = `<div class="quality-summary"><strong>可编辑 PPTX 已生成</strong><div class="item-meta">${escapeHtml(task.message)}</div><a class="text-button" href="/api/tasks/${encodeURIComponent(task.task_id)}/download">下载 PPTX</a></div>`;
    return;
  }
  const message = task.error || task.message || "正在处理";
  target.innerHTML = `<div class="quality-summary ${task.status === "failed" ? "high" : "medium"}"><strong>${escapeHtml(task.status)} · ${task.progress}%</strong><div class="item-meta">${escapeHtml(message)}</div></div>`;
}

async function generatePptx() {
  const id = currentTargetId();
  if (!id) return;
  $("pptxBtn").disabled = true;
  try {
    const task = await api(`/api/targets/${id}/ppt`, { method: "POST", body: JSON.stringify({}) });
    renderPresentationTask(task);
    toast(task.status === "completed" ? "可编辑 PPTX 已生成" : "PPTX 任务已提交");
  } catch (error) {
    toast(`PPTX 生成失败：${error.message}`);
  } finally {
    $("pptxBtn").disabled = false;
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
$("saveAdvisorBtn").addEventListener("click", saveAdvisor);
$("createTargetBtn").addEventListener("click", createTarget);
$("matchBtn").addEventListener("click", () => generate("match", "匹配分析"));
$("emailBtn").addEventListener("click", () => generate("materials/contact-email", "套磁邮件"));
$("questionsBtn").addEventListener("click", () => generate("materials/interview-questions", "面试问题"));
$("pptBtn").addEventListener("click", () => generate("materials/ppt-outline", "PPT 大纲"));
$("pptxBtn").addEventListener("click", generatePptx);
$("generateReportBtn").addEventListener("click", generateReport);
$("targetSelect").addEventListener("change", renderGeneratedMaterials);

$("advisorList").addEventListener("click", (event) => {
  const sourceId = event.target.dataset.sourceId;
  if (sourceId) showSource(sourceId);
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
$("generatedList").addEventListener("click", (event) => {
  const materialId = event.target.dataset.materialId;
  if (materialId) showMaterial(materialId);
});

refresh();
