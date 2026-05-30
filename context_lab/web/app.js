const state = {
  options: null,
  experiment: null,
  caseId: "support_refund",
  defaultPrompt: "",
  activeTab: "simulator",
  selectedId: "current",
};

const tabMeta = {
  simulator: {
    title: "실험하기",
    subtitle: "프롬프트, 맥락 유지 개수, 압축 전략, KV 캐시 사용 방식을 바꿔 보며 결과를 비교합니다.",
    breadcrumb: "LLM Context Playground / 실험하기",
  },
  comparison: {
    title: "결과 비교",
    subtitle: "같은 프롬프트를 여러 맥락 구성 방식으로 실행해 품질과 비용을 비교합니다.",
    breadcrumb: "LLM Context Playground / 결과 비교",
  },
  calculator: {
    title: "맥락 분석",
    subtitle: "선택한 실험에서 실제로 들어간 context section과 token 비중을 확인합니다.",
    breadcrumb: "LLM Context Playground / 맥락 분석",
  },
  learning: {
    title: "캡처 노트",
    subtitle: "블로그에 정리하기 좋은 실험 요약과 학습 포인트를 정리합니다.",
    breadcrumb: "LLM Context Playground / 캡처 노트",
  },
};

const compressionLabels = {
  none: "압축 없음",
  summary: "요약 압축",
  structured: "구조화 상태",
  hybrid: "하이브리드",
};

const retrievalLabels = {
  off: "검색 끔",
  on: "RAG 켬",
};

const kvLabels = {
  off: "KV 캐시 없음",
  static: "정적 prefix 캐시",
  conversation: "대화 prefix 캐시",
};

const selectors = {
  tabButtons: () => [...document.querySelectorAll(".tab-button")],
  tabViews: () => [...document.querySelectorAll(".tab-view")],
};

const el = {
  caseSelect: document.querySelector("#caseSelect"),
  promptInput: document.querySelector("#promptInput"),
  restorePromptButton: document.querySelector("#restorePromptButton"),
  retentionTurns: document.querySelector("#retentionTurns"),
  compressionMode: document.querySelector("#compressionMode"),
  retrievalMode: document.querySelector("#retrievalMode"),
  kvCacheMode: document.querySelector("#kvCacheMode"),
  maxTokens: document.querySelector("#maxTokens"),
  reservedTokens: document.querySelector("#reservedTokens"),
  runButton: document.querySelector("#runButton"),
  resetBudgetButton: document.querySelector("#resetBudgetButton"),
  pageTitle: document.querySelector("#pageTitle"),
  pageSubtitle: document.querySelector("#pageSubtitle"),
  breadcrumb: document.querySelector("#breadcrumb"),
  caseStatus: document.querySelector("#caseStatus"),
  caseNotes: document.querySelector("#caseNotes"),
  experimentChecklist: document.querySelector("#experimentChecklist"),
  selectedScenarioChip: document.querySelector("#selectedScenarioChip"),
  currentResult: document.querySelector("#currentResult"),
  guidanceList: document.querySelector("#guidanceList"),
  apiPromptStats: document.querySelector("#apiPromptStats"),
  apiPromptPreview: document.querySelector("#apiPromptPreview"),
  answerRequirementStatus: document.querySelector("#answerRequirementStatus"),
  comparisonCards: document.querySelector("#comparisonCards"),
  qualityChart: document.querySelector("#qualityChart"),
  costChart: document.querySelector("#costChart"),
  metricsRows: document.querySelector("#metricsRows"),
  tokenGauge: document.querySelector("#tokenGauge"),
  tokenGaugeText: document.querySelector("#tokenGaugeText"),
  tokenDetails: document.querySelector("#tokenDetails"),
  tokenCaption: document.querySelector("#tokenCaption"),
  sectionBreakdown: document.querySelector("#sectionBreakdown"),
  bundleSummary: document.querySelector("#bundleSummary"),
  contextSections: document.querySelector("#contextSections"),
  captureSummary: document.querySelector("#captureSummary"),
  codeStrategyName: document.querySelector("#codeStrategyName"),
  pseudoCode: document.querySelector("#pseudoCode"),
  blogPoints: document.querySelector("#blogPoints"),
};

async function init() {
  state.options = await fetchJson("/api/options");
  renderTabs();
  renderCaseOptions();
  await loadCase();
  await runExperiment();
}

function renderTabs() {
  for (const button of selectors.tabButtons()) {
    button.classList.toggle("active", button.dataset.tab === state.activeTab);
    button.addEventListener("click", () => {
      state.activeTab = button.dataset.tab;
      renderActiveTab();
    });
  }
  renderActiveTab();
}

function renderActiveTab() {
  for (const button of selectors.tabButtons()) {
    button.classList.toggle("active", button.dataset.tab === state.activeTab);
  }
  for (const view of selectors.tabViews()) {
    view.classList.toggle("active", view.id === `view-${state.activeTab}`);
  }
  const meta = tabMeta[state.activeTab];
  el.pageTitle.textContent = meta.title;
  el.pageSubtitle.textContent = meta.subtitle;
  el.breadcrumb.textContent = meta.breadcrumb;
}

function renderCaseOptions() {
  el.caseSelect.innerHTML = "";
  for (const item of state.options.cases) {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = caseLabel(item.id);
    el.caseSelect.append(option);
  }
  el.caseSelect.value = state.caseId;
}

async function loadCase() {
  state.caseId = el.caseSelect.value;
  const data = await fetchJson(`/api/case?case=${encodeURIComponent(state.caseId)}`);
  state.defaultPrompt = data.userTurn;
  el.promptInput.value = data.userTurn;
  el.caseNotes.textContent = data.notes;
  el.caseStatus.textContent = caseLabel(state.caseId);
  renderChecklist(data.expected, data.unsafe);
}

function renderChecklist(expected, unsafe) {
  const expectedItems = expected.map((item) => `<span class="small-chip">${escapeHtml(item)}</span>`).join("");
  const unsafeItems = unsafe.length
    ? unsafe.map((item) => `<span class="small-chip danger">${escapeHtml(item)}</span>`).join("")
    : `<span class="small-chip">없음</span>`;
  el.experimentChecklist.innerHTML = `
    <div>
      <strong>유지해야 할 근거</strong>
      <div class="chip-row">${expectedItems}</div>
    </div>
    <div>
      <strong>노출 금지 정보</strong>
      <div class="chip-row">${unsafeItems}</div>
    </div>
  `;
}

async function runExperiment() {
  normalizeBudgetInputs();
  el.runButton.disabled = true;
  try {
    const query = new URLSearchParams({
      case: state.caseId,
      prompt: el.promptInput.value,
      mode: "mock",
      retentionTurns: el.retentionTurns.value,
      compression: el.compressionMode.value,
      retrieval: el.retrievalMode.value,
      kvCache: el.kvCacheMode.value,
      maxInputTokens: el.maxTokens.value,
      reservedOutputTokens: el.reservedTokens.value,
    });
    state.experiment = await fetchJson(`/api/experiment?${query.toString()}`);
    state.selectedId = state.experiment.selectedId;
    renderAll();
  } finally {
    el.runButton.disabled = false;
  }
}

function renderAll() {
  renderCurrentResult();
  renderPromptInspection();
  renderComparison();
  renderContextAnalysis();
  renderCaptureNotes();
}

function selectedResult() {
  return state.experiment.results.find((item) => item.id === state.selectedId) ?? state.experiment.results[0];
}

function renderCurrentResult() {
  const result = selectedResult();
  el.selectedScenarioChip.textContent = result.name;
  el.guidanceList.innerHTML = guidanceFor(result).map((item) => `<div>${escapeHtml(item)}</div>`).join("");
  el.currentResult.innerHTML = `
    <div class="answer-head">
      <div>
        <span class="small-chip">${escapeHtml(retentionLabel(result.settings.retentionTurns))}</span>
        <span class="small-chip">${escapeHtml(compressionLabels[result.settings.compression])}</span>
        <span class="small-chip">${escapeHtml(retrievalLabels[result.settings.retrieval])}</span>
        <span class="small-chip">${escapeHtml(kvLabels[result.settings.kvCache])}</span>
      </div>
      ${passHtml(result)}
    </div>
    <div class="mini-metrics">
      ${metricBox("품질", `${result.qualityScore}`)}
      ${metricBox("입력 token", `${result.tokens}`)}
      ${metricBox("캐시 후보", `${result.cachedTokens}`)}
      ${metricBox("예상 지연", `${result.latencyMs} ms`)}
    </div>
    <pre>${escapeHtml(localizeAnswer(result.answer))}</pre>
    <p>${escapeHtml(result.lesson)}</p>
  `;
}

function renderPromptInspection() {
  const result = selectedResult();
  el.apiPromptStats.textContent = `${result.tokens} token · ${result.sections.length}개 section`;
  el.apiPromptPreview.textContent = result.apiPrompt;

  const expected = state.experiment.expectedFacts.map((fact) => {
    const missed = result.missing.includes(fact);
    return `
      <div class="${missed ? "bad" : "ok"}">
        <span>${missed ? "확인 필요" : "유지됨"}</span>
        <strong>${escapeHtml(fact)}</strong>
      </div>
    `;
  }).join("");
  const unsafeFacts = state.experiment.unsafeFacts.length
    ? state.experiment.unsafeFacts.map((fact) => {
        const exposed = result.unsafe.includes(fact);
        return `
          <div class="${exposed ? "bad" : "ok"}">
            <span>${exposed ? "노출됨" : "차단됨"}</span>
            <strong>${escapeHtml(fact)}</strong>
          </div>
        `;
      }).join("")
    : `<div class="ok"><span>차단됨</span><strong>민감 정보 없음</strong></div>`;

  el.answerRequirementStatus.innerHTML = `
    <section>
      <h4>반드시 유지</h4>
      ${expected}
    </section>
    <section>
      <h4>노출 금지</h4>
      ${unsafeFacts}
    </section>
  `;
}

function renderComparison() {
  el.comparisonCards.innerHTML = "";
  for (const result of state.experiment.results) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = `comparison-card ${state.selectedId === result.id ? "active" : ""}`;
    card.addEventListener("click", () => {
      state.selectedId = result.id;
      renderAll();
    });
    card.innerHTML = `
      <div class="card-title-row">
        <div class="strategy-name"><span class="strategy-symbol">${escapeHtml(result.name.slice(0, 2))}</span>${escapeHtml(result.name)}</div>
        ${passHtml(result)}
      </div>
      <p>${escapeHtml(result.description)}</p>
      <div class="meter"><span style="width:${clamp(result.tokenUtilization)}%"></span></div>
      <div class="card-metrics"><span>${result.tokens} token</span><span>품질 ${result.qualityScore}</span></div>
    `;
    el.comparisonCards.append(card);
  }

  el.qualityChart.innerHTML = "";
  for (const result of state.experiment.results) {
    el.qualityChart.append(chartRow(result.name, result.qualityScore, result.qualityScore));
  }

  const maxTokens = Math.max(...state.experiment.results.map((item) => item.tokens), 1);
  el.costChart.innerHTML = "";
  for (const result of state.experiment.results) {
    const width = Math.round((result.tokens / maxTokens) * 100);
    el.costChart.append(chartRow(result.name, width, `${result.tokens}t / cache ${result.cachedTokens}t`));
  }

  el.metricsRows.innerHTML = "";
  for (const result of state.experiment.results) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${escapeHtml(result.name)}</td>
      <td>${escapeHtml(retentionLabel(result.settings.retentionTurns))}</td>
      <td>${escapeHtml(compressionLabels[result.settings.compression])}</td>
      <td>${result.tokens} (${result.tokenUtilization}%)</td>
      <td>${result.cachedTokens} (${result.cacheReuseRatio}%)</td>
      <td>${result.passed ? "통과" : `확인 필요: ${escapeHtml(issueSummary(result))}`}</td>
    `;
    el.metricsRows.append(row);
  }
}

function renderContextAnalysis() {
  const result = selectedResult();
  const utilization = clamp(result.tokenUtilization);
  el.tokenGauge.style.background = `radial-gradient(circle at center, var(--surface) 0 58%, transparent 59%), conic-gradient(var(--primary) ${utilization * 3.6}deg, var(--surface-high) 0deg)`;
  el.tokenGaugeText.textContent = `${Math.round(utilization)}%`;
  el.tokenDetails.textContent = `${result.tokens} / ${result.availableTokens} 입력 token`;
  el.tokenCaption.textContent = `캐시 후보 ${result.cachedTokens} token · 답변 예약 ${result.reservedOutputTokens} token 제외`;
  el.bundleSummary.textContent = `${result.sections.length}개 section`;

  el.sectionBreakdown.innerHTML = "";
  for (const section of result.sections) {
    const row = document.createElement("div");
    row.className = "breakdown-row";
    row.innerHTML = `
      <span>${escapeHtml(section.label)}</span>
      <span>${section.tokenShare}%</span>
      <div class="breakdown-track"><span style="width:${clamp(section.tokenShare)}%"></span></div>
    `;
    el.sectionBreakdown.append(row);
  }

  el.contextSections.innerHTML = "";
  for (const section of result.sections) {
    const details = document.createElement("details");
    details.className = "context-section";
    details.open = section.priority >= 95;
    details.innerHTML = `
      <summary><strong>${escapeHtml(section.label)}</strong><span>${section.tokens} token · 출처=${escapeHtml(section.source)} · 우선순위=${section.priority}</span></summary>
      <pre>${escapeHtml(section.content || "(비어 있음)")}</pre>
    `;
    el.contextSections.append(details);
  }
}

function renderCaptureNotes() {
  const result = selectedResult();
  const capture = state.experiment.capture;
  el.captureSummary.innerHTML = `
    <div class="capture-kicker">LLM Context Playground</div>
    <h3>${escapeHtml(capture.headline)}</h3>
    <div class="mini-metrics">
      ${metricBox("선택 실험", capture.selected)}
      ${metricBox("최고 품질", capture.bestQuality)}
      ${metricBox("최소 token", capture.lowestTokens)}
      ${metricBox("캐시 후보", capture.bestCache)}
    </div>
    <p>${escapeHtml(result.lesson)}</p>
  `;
  el.blogPoints.innerHTML = [
    `프롬프트: ${state.experiment.prompt}`,
    `설정: ${retentionLabel(result.settings.retentionTurns)} · ${compressionLabels[result.settings.compression]} · ${retrievalLabels[result.settings.retrieval]} · ${kvLabels[result.settings.kvCache]}`,
    `결과: 품질 ${result.qualityScore}, 입력 ${result.tokens} token, 캐시 후보 ${result.cachedTokens} token`,
    result.lesson,
  ].map((item) => `<div>${escapeHtml(item)}</div>`).join("");
  el.codeStrategyName.textContent = result.id;
  el.pseudoCode.textContent = pseudoCode(result);
}

function guidanceFor(result) {
  const guidance = [
    `현재 선택한 '${result.name}'은 ${retentionLabel(result.settings.retentionTurns)}를 직접 포함합니다.`,
    result.lesson,
  ];
  if (result.cachedTokens) {
    guidance.push(`KV 캐시 후보는 약 ${result.cachedTokens} token입니다. 반복되는 정책, 요약, 프로필을 prefix로 둘 때 효과가 큽니다.`);
  } else {
    guidance.push("KV 캐시를 끄면 같은 정책과 요약도 매 요청마다 다시 계산한다고 보면 됩니다.");
  }
  if (result.missing.length) {
    guidance.push(`누락된 근거: ${result.missing.join(", ")}. 유지 개수를 늘리거나 RAG를 켜서 다시 비교하세요.`);
  }
  return guidance;
}

function chartRow(label, width, value) {
  const row = document.createElement("div");
  row.className = "chart-row";
  row.innerHTML = `
    <div class="chart-label">${escapeHtml(label)}</div>
    <div class="chart-track"><span style="width:${clamp(width)}%"></span></div>
    <div class="chart-label">${escapeHtml(String(value))}</div>
  `;
  return row;
}

function metricBox(label, value) {
  return `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></div>`;
}

function passHtml(result) {
  return `<span class="pass-pill ${result.passed ? "ok" : "bad"}">${result.passed ? "통과" : "확인 필요"}</span>`;
}

function issueSummary(result) {
  const parts = [];
  if (result.missing.length) parts.push(`누락: ${result.missing.join(", ")}`);
  if (result.unsafe.length) parts.push(`위험: ${result.unsafe.join(", ")}`);
  if (result.warnings.length) parts.push(`경고: ${result.warnings.join(", ")}`);
  return parts.length ? parts.join(" · ") : "필수 맥락 보존";
}

function localizeAnswer(answer) {
  return String(answer).replace(/^Mock 답변:/, "모의 답변:");
}

function retentionLabel(value) {
  const turns = Number(value);
  if (turns <= 0) return "최근 대화 없음";
  if (turns >= 999) return "전체 대화";
  return `최근 ${turns}개 메시지`;
}

function caseLabel(id) {
  const labels = {
    support_refund: "환불 문의",
    internal_policy: "내부 정책 충돌",
    tool_result_compaction: "도구 결과 압축",
    privacy_memory: "개인정보 memory",
    long_running_session: "긴 세션",
    openai_state: "OpenAI 상태 관리",
  };
  return labels[id] ?? id;
}

function pseudoCode(result) {
  return `사용자_질문 = 입력한_프롬프트
맥락 = [
  정책,
  ${result.settings.compression === "none" ? "# 압축 section 없음" : `${compressionLabels[result.settings.compression]} section`},
  ${result.settings.retrieval === "on" ? "검색_근거," : "# 검색 근거 비활성화"}
  최근_대화(${result.settings.retentionTurns}),
  현재_사용자_질문,
]

if KV_캐시 == "${kvLabels[result.settings.kvCache]}":
  반복_prefix_캐시(정책, 요약, 프로필, 검색_근거)

답변 = 모델.generate(맥락)
측정(token=${result.tokens}, cache=${result.cachedTokens}, quality=${result.qualityScore})`;
}

function normalizeBudgetInputs() {
  const maxValue = Math.max(120, Number(el.maxTokens.value) || 900);
  const reservedValue = Math.max(20, Number(el.reservedTokens.value) || 200);
  el.maxTokens.value = String(maxValue);
  el.reservedTokens.value = String(reservedValue >= maxValue ? Math.max(20, maxValue - 20) : reservedValue);
}

function clamp(value) {
  return Math.max(0, Math.min(100, Number(value) || 0));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

el.caseSelect.addEventListener("change", async () => {
  await loadCase();
  await runExperiment();
});
el.restorePromptButton.addEventListener("click", () => {
  el.promptInput.value = state.defaultPrompt;
  runExperiment();
});
el.runButton.addEventListener("click", runExperiment);
el.resetBudgetButton.addEventListener("click", () => {
  el.retentionTurns.value = "4";
  el.compressionMode.value = "hybrid";
  el.retrievalMode.value = "on";
  el.kvCacheMode.value = "static";
  el.maxTokens.value = "900";
  el.reservedTokens.value = "200";
  runExperiment();
});
for (const input of [el.retentionTurns, el.compressionMode, el.retrievalMode, el.kvCacheMode, el.maxTokens, el.reservedTokens]) {
  input.addEventListener("change", runExperiment);
}

init().catch((error) => {
  console.error(error);
  document.body.innerHTML = `<pre style="padding:24px;color:#ffb4ab">${escapeHtml(error.message)}</pre>`;
});
