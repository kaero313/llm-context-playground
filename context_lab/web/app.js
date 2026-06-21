const HISTORY_STORAGE_KEY = "llm-context-playground.experiment-history.v1";
const HISTORY_LIMIT = 12;

const state = {
  options: null,
  experiment: null,
  caseId: "support_refund",
  defaultPrompt: "",
  activeTab: "simulator",
  selectedId: "current",
  lastRunSnapshot: null,
  strategyDiff: null,
  history: [],
  activeHistoryId: null,
};

const tabMeta = {
  simulator: {
    title: "실험하기",
    subtitle: "프롬프트, 맥락 유지 개수, 압축 전략, RAG, KV 캐시를 바꿔 보며 결과를 비교합니다.",
    breadcrumb: "LLM Context Playground / 실험하기",
  },
  comparison: {
    title: "결과 비교",
    subtitle: "같은 프롬프트를 여러 맥락 구성 방식으로 실행하고 품질과 비용을 비교합니다.",
    breadcrumb: "LLM Context Playground / 결과 비교",
  },
  calculator: {
    title: "맥락 분석",
    subtitle: "선택한 실험에서 실제로 들어간 context section과 token 비중을 확인합니다.",
    breadcrumb: "LLM Context Playground / 맥락 분석",
  },
  learning: {
    title: "학습 가이드",
    subtitle: "케이스별 추천 실험 순서, 관찰 포인트, 블로그 정리 포인트를 확인합니다.",
    breadcrumb: "LLM Context Playground / 학습 가이드",
  },
};

const compressionLabels = {
  none: "압축 없음",
  summary: "요약 압축",
  structured: "구조화 상태",
  hybrid: "Hybrid",
};

const retrievalLabels = {
  off: "RAG 끔",
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
  modelMode: document.querySelector("#modelMode"),
  liveScope: document.querySelector("#liveScope"),
  modeNotice: document.querySelector("#modeNotice"),
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
  serverStatus: document.querySelector("#serverStatus"),
  caseStatus: document.querySelector("#caseStatus"),
  caseNotes: document.querySelector("#caseNotes"),
  experimentChecklist: document.querySelector("#experimentChecklist"),
  caseGuide: document.querySelector("#caseGuide"),
  selectedScenarioChip: document.querySelector("#selectedScenarioChip"),
  currentResult: document.querySelector("#currentResult"),
  finalConclusion: document.querySelector("#finalConclusion"),
  guidanceList: document.querySelector("#guidanceList"),
  apiPromptStats: document.querySelector("#apiPromptStats"),
  apiPromptPreview: document.querySelector("#apiPromptPreview"),
  strategyDiffPanel: document.querySelector("#strategyDiffPanel"),
  answerRequirementStatus: document.querySelector("#answerRequirementStatus"),
  historyCount: document.querySelector("#historyCount"),
  experimentHistoryList: document.querySelector("#experimentHistoryList"),
  clearHistoryButton: document.querySelector("#clearHistoryButton"),
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
};

async function init() {
  state.options = await fetchJson("/api/options");
  state.history = loadExperimentHistory();
  configureModeControls();
  renderTabs();
  renderCaseOptions();
  renderHistory();
  await loadCase();
  updateModeNotice();
  await runExperiment({ saveToHistory: false });
}

function configureModeControls() {
  const liveOption = el.modelMode.querySelector('option[value="openai"]');
  if (!state.options.openai?.enabled) {
    liveOption.disabled = true;
    el.modelMode.value = "mock";
  }
  updateServerStatus();
}

function updateServerStatus() {
  const mode = el.modelMode.value;
  el.serverStatus.classList.toggle("live", mode === "openai");
  el.serverStatus.classList.toggle("mock", mode === "mock");
  el.serverStatus.textContent =
    mode === "openai"
      ? `Live API · ${state.options.openai?.model ?? "OpenAI"}`
      : state.options.openai?.enabled
        ? "Mock mode · Live 사용 가능"
        : "Mock mode · API key 없음";
}

function updateModeNotice() {
  const liveEnabled = Boolean(state.options.openai?.enabled);
  if (el.modelMode.value === "mock") {
    el.liveScope.disabled = true;
    el.modeNotice.textContent =
      liveEnabled
        ? "Mock mode는 비용 없이 맥락 구성, 누락 여부, token 구조를 빠르게 학습합니다. 실제 모델 검증이 필요할 때 Live API로 전환하세요."
        : "Mock mode로 실행 중입니다. Live API를 쓰려면 서버 환경변수 OPENAI_API_KEY를 설정하고 서버를 다시 시작해야 합니다.";
  } else {
    el.liveScope.disabled = false;
    el.modeNotice.textContent =
      el.liveScope.value === "all"
        ? "Live API가 비교 후보 전체를 실제 호출합니다. 현재 화면 기준 4번의 OpenAI API 호출이 발생합니다."
        : "Live API는 현재 설정만 실제 호출합니다. 비교 후보는 비용 절감을 위해 Mock mode로 계산합니다.";
  }
  updateServerStatus();
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

async function loadCase(options = {}) {
  state.caseId = el.caseSelect.value;
  const data = await fetchJson(`/api/case?case=${encodeURIComponent(state.caseId)}`);
  state.defaultPrompt = data.userTurn;
  el.promptInput.value = options.promptOverride ?? data.userTurn;
  el.caseNotes.textContent = data.notes;
  el.caseStatus.textContent = caseLabel(state.caseId);
  renderChecklist(data.expected, data.unsafe);
  renderCaseGuide(data.guide);
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

function renderCaseGuide(guide) {
  if (!guide) {
    el.caseGuide.innerHTML = "";
    return;
  }
  const recommended = (guide.recommended || []).map((item, index) => `
    <article class="guide-step">
      <div class="guide-step-number">${index + 1}</div>
      <div>
        <h5>${escapeHtml(item.title)}</h5>
        <p>${escapeHtml(item.settings)}</p>
        <span>${escapeHtml(item.observe)}</span>
      </div>
    </article>
  `).join("");
  const watch = (guide.watch || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const blog = (guide.blog || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");

  el.caseGuide.innerHTML = `
    <div class="guide-overview">
      <div>
        <span class="guide-kicker">학습 목표</span>
        <h4>${escapeHtml(guide.title)}</h4>
        <p>${escapeHtml(guide.goal)}</p>
      </div>
    </div>
    <div class="guide-layout">
      <section>
        <h4>추천 실험 순서</h4>
        <div class="guide-steps">${recommended}</div>
      </section>
      <section>
        <h4>관찰 포인트</h4>
        <ul>${watch}</ul>
      </section>
      <section>
        <h4>블로그 정리 포인트</h4>
        <ul>${blog}</ul>
      </section>
    </div>
  `;
}

async function runExperiment(options = {}) {
  const { saveToHistory = true } = options;
  normalizeBudgetInputs();
  updateModeNotice();
  if (el.modelMode.value === "openai" && !state.options.openai?.enabled) {
    renderError("OPENAI_API_KEY가 설정되어 있지 않아 Live API를 실행할 수 없습니다.");
    return;
  }

  const originalRunText = el.runButton.innerHTML;
  const nextFingerprint = experimentFingerprint();
  const previousSnapshot = state.lastRunSnapshot;
  el.runButton.disabled = true;
  el.runButton.innerHTML =
    el.modelMode.value === "openai"
      ? `<span>Live API 호출 중</span><strong>응답 대기</strong>`
      : `<span>Mock 실행 중</span><strong>결과 계산</strong>`;
  try {
    const query = new URLSearchParams({
      case: state.caseId,
      prompt: el.promptInput.value,
      mode: el.modelMode.value,
      liveVariants: el.liveScope.value,
      retentionTurns: el.retentionTurns.value,
      compression: el.compressionMode.value,
      retrieval: el.retrievalMode.value,
      kvCache: el.kvCacheMode.value,
      maxInputTokens: el.maxTokens.value,
      reservedOutputTokens: el.reservedTokens.value,
    });
    const experiment = await fetchJson(`/api/experiment?${query.toString()}`);
    const current = currentResultFrom(experiment);
    state.strategyDiff =
      previousSnapshot && previousSnapshot.fingerprint === nextFingerprint
        ? buildStrategyDiff(previousSnapshot.result, current)
        : null;
    state.experiment = experiment;
    state.selectedId = state.experiment.selectedId;
    state.lastRunSnapshot = {
      fingerprint: nextFingerprint,
      result: cloneForDiff(current),
    };
    state.activeHistoryId = null;
    if (saveToHistory) {
      saveHistoryRecord(experiment, state.strategyDiff);
    }
    renderAll();
  } catch (error) {
    renderError(error.message);
  } finally {
    el.runButton.disabled = false;
    el.runButton.innerHTML = originalRunText;
  }
}

function renderError(message) {
  el.currentResult.innerHTML = `
    <div class="error-panel">
      <strong>실험 실행 실패</strong>
      <p>${escapeHtml(message)}</p>
    </div>
  `;
  el.serverStatus.textContent = "실행 실패";
}

function renderAll() {
  renderCurrentResult();
  renderPromptInspection();
  renderStrategyDiff();
  renderFinalConclusion();
  renderComparison();
  renderContextAnalysis();
  renderHistory();
}

function selectedResult() {
  return state.experiment.results.find((item) => item.id === state.selectedId) ?? state.experiment.results[0];
}

function currentResultFrom(experiment) {
  return experiment.results.find((item) => item.id === "current") ?? experiment.results[0];
}

function loadExperimentHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((item) => item?.id && item?.experiment).slice(0, HISTORY_LIMIT) : [];
  } catch {
    return [];
  }
}

function persistExperimentHistory() {
  try {
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(state.history.slice(0, HISTORY_LIMIT)));
  } catch {
    while (state.history.length > 4) {
      state.history.pop();
      try {
        localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(state.history));
        return;
      } catch {
        // Keep shrinking until storage accepts the payload.
      }
    }
  }
}

function saveHistoryRecord(experiment, strategyDiff) {
  const record = createHistoryRecord(experiment, strategyDiff);
  const existingIndex = state.history.findIndex((item) => item.signature === record.signature);
  if (existingIndex >= 0) {
    state.history.splice(existingIndex, 1);
  }
  state.history.unshift(record);
  state.history = state.history.slice(0, HISTORY_LIMIT);
  state.activeHistoryId = record.id;
  persistExperimentHistory();
}

function createHistoryRecord(experiment, strategyDiff) {
  const current = currentResultFrom(experiment);
  const settings = experiment.settings;
  const savedAt = new Date().toISOString();
  const prompt = el.promptInput.value;
  return {
    id: `history-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    signature: historySignature(experiment, strategyDiff, prompt),
    savedAt,
    caseId: state.caseId,
    caseLabel: caseLabel(state.caseId),
    prompt,
    selectedId: state.selectedId,
    settings: cloneForDiff(settings),
    strategyDiff: strategyDiff ? cloneForDiff(strategyDiff) : null,
    experiment: cloneForDiff(experiment),
    summary: {
      name: current.name,
      mode: modeLabel(current),
      compression: compressionLabels[current.settings.compression],
      retrieval: retrievalLabels[current.settings.retrieval],
      kvCache: kvLabels[current.settings.kvCache],
      retention: retentionLabel(current.settings.retentionTurns),
      tokens: current.tokens,
      cachedTokens: current.cachedTokens,
      qualityScore: current.qualityScore,
      passed: current.passed,
      issue: issueSummary(current),
    },
  };
}

function historySignature(experiment, strategyDiff, prompt) {
  const current = currentResultFrom(experiment);
  return JSON.stringify({
    caseId: state.caseId,
    prompt: normalizeDiffText(prompt),
    settings: experiment.settings,
    resultSettings: current.settings,
    mode: current.mode,
    diff: strategyDiff ? Boolean(strategyDiff.hasChanges) : false,
  });
}

function renderHistory() {
  if (!el.experimentHistoryList) return;
  const count = state.history.length;
  el.historyCount.textContent = `${count}개 기록`;
  el.clearHistoryButton.disabled = count === 0;

  if (!count) {
    el.experimentHistoryList.innerHTML = `
      <div class="history-empty">
        <strong>저장된 실험이 없습니다.</strong>
        <p>설정을 바꿔 실행하면 프롬프트, 응답, 평가, 결론이 여기에 저장됩니다.</p>
      </div>
    `;
    return;
  }

  el.experimentHistoryList.innerHTML = state.history.map(historyCardHtml).join("");
  for (const button of el.experimentHistoryList.querySelectorAll("[data-history-id]")) {
    button.addEventListener("click", () => {
      openHistoryRecord(button.dataset.historyId);
    });
  }
}

function historyCardHtml(record) {
  const summary = record.summary;
  const isActive = record.id === state.activeHistoryId;
  const diffLabel = record.strategyDiff?.hasChanges ? "diff 있음" : "기준 실행";
  return `
    <button class="history-card ${isActive ? "active" : ""}" type="button" data-history-id="${escapeHtml(record.id)}">
      <div class="history-card-head">
        <span>${escapeHtml(formatHistoryTime(record.savedAt))}</span>
        <strong>${escapeHtml(record.caseLabel)}</strong>
      </div>
      <p>${escapeHtml(truncateText(record.prompt, 92))}</p>
      <div class="history-chip-row">
        <span class="small-chip">${escapeHtml(summary.mode)}</span>
        <span class="small-chip">${escapeHtml(summary.retention)}</span>
        <span class="small-chip">${escapeHtml(summary.compression)}</span>
        <span class="small-chip">${escapeHtml(summary.retrieval)}</span>
        <span class="small-chip">${escapeHtml(diffLabel)}</span>
      </div>
      <div class="history-metrics">
        <span>품질 ${summary.qualityScore}</span>
        <span>${summary.tokens}t · cache ${summary.cachedTokens}t</span>
        <span>${summary.passed ? "통과" : `확인 필요: ${escapeHtml(summary.issue)}`}</span>
      </div>
    </button>
  `;
}

async function openHistoryRecord(recordId) {
  const record = state.history.find((item) => item.id === recordId);
  if (!record) return;
  state.activeHistoryId = record.id;
  state.caseId = record.caseId;
  el.caseSelect.value = record.caseId;
  await loadCase({ promptOverride: record.prompt });
  applyExperimentSettings(record.settings);
  state.experiment = cloneForDiff(record.experiment);
  state.selectedId = record.selectedId || state.experiment.selectedId;
  state.strategyDiff = record.strategyDiff ? cloneForDiff(record.strategyDiff) : null;
  state.lastRunSnapshot = {
    fingerprint: experimentFingerprint(),
    result: cloneForDiff(currentResultFrom(state.experiment)),
  };
  updateModeNotice();
  renderAll();
}

function applyExperimentSettings(settings) {
  el.modelMode.value = settings.mode ?? "mock";
  el.liveScope.value = settings.liveVariants ?? "current";
  el.retentionTurns.value = String(settings.retentionTurns ?? 4);
  el.compressionMode.value = settings.compression ?? "hybrid";
  el.retrievalMode.value = settings.retrieval ?? "on";
  el.kvCacheMode.value = settings.kvCache ?? "static";
  el.maxTokens.value = String(settings.maxInputTokens ?? 900);
  el.reservedTokens.value = String(settings.reservedOutputTokens ?? 200);
}

function renderCurrentResult() {
  const result = selectedResult();
  el.selectedScenarioChip.textContent = result.name;
  el.currentResult.innerHTML = `
    <div class="answer-head">
      <div>
        <span class="small-chip">${escapeHtml(modeLabel(result))}</span>
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
      ${metricBox("실제 API token", actualTokenText(result))}
      ${metricBox("지연 시간", `${result.latencyMs} ms`)}
    </div>
    <pre>${escapeHtml(localizeAnswer(result.answer, result.mode))}</pre>
    <p>${escapeHtml(result.lesson)}</p>
  `;
}

function renderFinalConclusion() {
  const result = selectedResult();
  const outcome = conclusionOutcome(result);
  const evidenceStatus = result.missing.length ? "확인 필요" : "통과";
  const safetyStatus = result.unsafe.length ? "위험 정보 노출" : "차단";
  const insights = conclusionInsights(result);

  el.finalConclusion.innerHTML = `
    <div class="conclusion-status ${outcome.tone}">
      <span>원했던 결과</span>
      <strong>${escapeHtml(outcome.label)}</strong>
      <p>${escapeHtml(outcome.description)}</p>
    </div>
    <div class="conclusion-grid">
      ${conclusionMetric("근거 유지", evidenceStatus, result.missing.length ? result.missing.join(", ") : "필수 정보가 답변 경로에 유지됐습니다.", result.missing.length ? "bad" : "ok")}
      ${conclusionMetric("위험 정보", safetyStatus, result.unsafe.length ? result.unsafe.join(", ") : "노출 금지 정보가 답변에 포함되지 않았습니다.", result.unsafe.length ? "bad" : "ok")}
      ${conclusionMetric("Token / Cache", `${result.tokens}t · cache ${result.cachedTokens}t`, `입력 예산 ${result.availableTokens} token 중 ${result.tokenUtilization}%를 사용했습니다.`, "neutral")}
      ${conclusionMetric("실행 방식", modeLabel(result), actualTokenText(result), result.mode === "openai" ? "ok" : "neutral")}
    </div>
    <section class="conclusion-notes">
      <h4>특이점</h4>
      <ul>${insights.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </section>
  `;
  el.guidanceList.innerHTML = guidanceFor(result).map((item) => `<div>${escapeHtml(item)}</div>`).join("");
}

function conclusionOutcome(result) {
  if (result.unsafe.length) {
    return {
      tone: "bad",
      label: "실패",
      description: "응답에 노출되면 안 되는 정보가 포함됐습니다. privacy memory와 redaction 조건을 먼저 조정해야 합니다.",
    };
  }
  if (result.missing.length) {
    return {
      tone: "warn",
      label: "부분 충족",
      description: "응답은 생성됐지만 유지해야 할 핵심 근거가 일부 빠졌습니다. 맥락 유지 개수, 압축, RAG 설정을 바꿔 비교하세요.",
    };
  }
  return {
    tone: "ok",
    label: "충족",
    description: "필수 근거를 유지했고 노출 금지 정보도 차단했습니다. 현재 설정은 이 케이스의 기준 실험으로 사용할 수 있습니다.",
  };
}

function conclusionMetric(label, value, detail, tone) {
  return `
    <article class="conclusion-metric ${tone}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <p>${escapeHtml(detail)}</p>
    </article>
  `;
}

function conclusionInsights(result) {
  const insights = [];
  if (result.warnings.length) {
    insights.push(`Context budget 경고: ${result.warnings.join(", ")}`);
  }
  if (result.settings.retrieval === "off") {
    insights.push("RAG가 꺼져 있어 검색 근거 section이 최종 프롬프트에서 제외됩니다.");
  } else {
    insights.push("RAG가 켜져 있어 검색 근거가 최종 프롬프트에 포함됩니다.");
  }
  if (result.settings.compression === "none") {
    insights.push("압축이 꺼져 있어 오래된 대화나 구조화 상태가 별도 section으로 보존되지 않습니다.");
  } else {
    insights.push(`${compressionLabels[result.settings.compression]} 설정으로 요약 또는 구조화 상태가 프롬프트에 반영됩니다.`);
  }
  if (result.cachedTokens) {
    insights.push(`KV cache 후보 ${result.cachedTokens} token은 반복 prefix 비용을 줄이는 학습 포인트입니다.`);
  } else {
    insights.push("KV cache가 꺼져 있어 모든 context를 매 요청마다 다시 처리하는 기준선입니다.");
  }
  if (result.tokenUtilization >= 80) {
    insights.push("입력 예산에 가까워졌으므로 응답 품질보다 trimming 위험을 먼저 확인해야 합니다.");
  }
  return insights;
}

function renderPromptInspection() {
  const result = selectedResult();
  el.apiPromptStats.textContent = `${result.tokens} token · ${result.sections.length}개 section · ${modeLabel(result)}`;
  el.apiPromptPreview.innerHTML = markedApiPromptHtml(result);

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

function renderStrategyDiff() {
  if (!el.strategyDiffPanel) return;
  const diff = state.strategyDiff;
  if (!diff) {
    el.strategyDiffPanel.innerHTML = `
      <section class="diff-card diff-empty">
        <div>
          <h4>전략 변경 diff</h4>
          <p>같은 케이스에서 설정을 바꿔 다시 실행하면 변경점이 표시됩니다.</p>
        </div>
      </section>
    `;
    return;
  }

  const sectionItems = [
    ...diff.sections.added.map((item) => sectionDiffItemHtml("added", item)),
    ...diff.sections.removed.map((item) => sectionDiffItemHtml("removed", item)),
    ...diff.sections.changed.map((item) => sectionDiffItemHtml("changed", item)),
  ].join("");

  el.strategyDiffPanel.innerHTML = `
    <section class="diff-card">
      <div class="diff-head">
        <div>
          <h4>전략 변경 diff</h4>
          <p>직전 현재 설정 실행과 이번 현재 설정 실행을 비교합니다.</p>
        </div>
        <span class="diff-run-chip">${diff.hasChanges ? "변경 감지" : "동일 실행"}</span>
      </div>
      <div class="diff-layout">
        <div class="diff-column">
          <h5>변경된 설정</h5>
          <div class="diff-change-list">
            ${
              diff.settings.length
                ? diff.settings.map(settingDiffHtml).join("")
                : `<div class="diff-muted">변경된 설정이 없습니다.</div>`
            }
          </div>
        </div>
        <div class="diff-column">
          <h5>프롬프트 구성 변화</h5>
          <div class="diff-change-list">
            ${sectionItems || `<div class="diff-muted">section 추가, 제거, 내용 변경이 없습니다.</div>`}
          </div>
        </div>
      </div>
      <div class="diff-metric-grid">
        ${diff.metrics.map(metricDiffHtml).join("")}
      </div>
      <div class="diff-issue-grid">
        ${issueDiffHtml("지켜야 했던 것", diff.issues.missing, "새로 누락", "해결")}
        ${issueDiffHtml("노출되면 안 되는 것", diff.issues.unsafe, "새로 노출", "차단됨")}
        ${issueDiffHtml("특이점 / 경고", diff.issues.warnings, "새 경고", "해결")}
      </div>
    </section>
  `;
}

function buildStrategyDiff(before, after) {
  const settings = settingDiffs(before, after);
  const sections = sectionDiffs(before.sections, after.sections);
  const metrics = metricDiffs(before, after);
  const issues = {
    missing: arrayDiff(before.missing, after.missing),
    unsafe: arrayDiff(before.unsafe, after.unsafe),
    warnings: arrayDiff(before.warnings, after.warnings),
  };
  const hasIssueChanges = Object.values(issues).some((item) => item.added.length || item.removed.length);
  return {
    settings,
    sections,
    metrics,
    issues,
    hasChanges:
      settings.length ||
      sections.added.length ||
      sections.removed.length ||
      sections.changed.length ||
      metrics.some((item) => item.delta !== 0) ||
      hasIssueChanges,
  };
}

function settingDiffs(before, after) {
  return [
    ["실행 모드", modeLabel(before), modeLabel(after)],
    ["최근 대화 유지", retentionLabel(before.settings.retentionTurns), retentionLabel(after.settings.retentionTurns)],
    ["압축 전략", compressionLabels[before.settings.compression], compressionLabels[after.settings.compression]],
    ["검색 근거", retrievalLabels[before.settings.retrieval], retrievalLabels[after.settings.retrieval]],
    ["KV 캐시", kvLabels[before.settings.kvCache], kvLabels[after.settings.kvCache]],
    ["최대 입력 token", `${before.maxInputTokens}t`, `${after.maxInputTokens}t`],
    ["응답 예약 token", `${before.reservedOutputTokens}t`, `${after.reservedOutputTokens}t`],
  ]
    .filter(([, beforeValue, afterValue]) => beforeValue !== afterValue)
    .map(([label, beforeValue, afterValue]) => ({ label, beforeValue, afterValue }));
}

function sectionDiffs(beforeSections, afterSections) {
  const beforeMap = new Map(beforeSections.map((section) => [sectionKey(section), section]));
  const afterMap = new Map(afterSections.map((section) => [sectionKey(section), section]));
  const added = [];
  const removed = [];
  const changed = [];

  for (const [key, section] of afterMap) {
    const previous = beforeMap.get(key);
    if (!previous) {
      added.push(section);
    } else if (normalizeDiffText(previous.content) !== normalizeDiffText(section.content) || previous.tokens !== section.tokens) {
      changed.push({ ...section, beforeTokens: previous.tokens, afterTokens: section.tokens });
    }
  }
  for (const [key, section] of beforeMap) {
    if (!afterMap.has(key)) removed.push(section);
  }
  return { added, removed, changed };
}

function metricDiffs(before, after) {
  return [
    ["입력 token", before.tokens, after.tokens, "t"],
    ["청구 대상 token", billableMetric(before), billableMetric(after), "t"],
    ["KV cache", before.cachedTokens, after.cachedTokens, "t"],
    ["품질 점수", before.qualityScore, after.qualityScore, ""],
    ["지연 시간", before.latencyMs, after.latencyMs, "ms"],
    ["예산 사용률", before.tokenUtilization, after.tokenUtilization, "%"],
  ].map(([label, beforeValue, afterValue, suffix]) => ({
    label,
    beforeValue,
    afterValue,
    suffix,
    delta: Number(afterValue) - Number(beforeValue),
  }));
}

function settingDiffHtml(item) {
  return `
    <div class="diff-change">
      <span>${escapeHtml(item.label)}</span>
      <strong><b>${escapeHtml(item.beforeValue)}</b><i>→</i><b>${escapeHtml(item.afterValue)}</b></strong>
    </div>
  `;
}

function sectionDiffItemHtml(kind, item) {
  const labels = {
    added: "추가",
    removed: "제거",
    changed: "변경",
  };
  const tokenText =
    kind === "changed"
      ? `${item.beforeTokens}t → ${item.afterTokens}t`
      : `${kind === "added" ? "+" : "-"}${item.tokens}t`;
  return `
    <div class="diff-section-item ${kind}">
      <span>${labels[kind]}</span>
      <strong>[${escapeHtml(item.label)}]</strong>
      <p>${escapeHtml(tokenText)} · 출처=${escapeHtml(item.source)}</p>
    </div>
  `;
}

function metricDiffHtml(item) {
  const tone = item.delta > 0 ? "increase" : item.delta < 0 ? "decrease" : "neutral";
  return `
    <div class="diff-metric ${tone}">
      <span>${escapeHtml(item.label)}</span>
      <strong>${escapeHtml(formatMetricValue(item.afterValue, item.suffix))}</strong>
      <p>${escapeHtml(formatMetricValue(item.beforeValue, item.suffix))} 대비 ${escapeHtml(formatDelta(item.delta, item.suffix))}</p>
    </div>
  `;
}

function issueDiffHtml(title, diff, addedLabel, removedLabel) {
  const items = [
    ...diff.added.map((item) => `<span class="diff-tag bad">${escapeHtml(addedLabel)} · ${escapeHtml(item)}</span>`),
    ...diff.removed.map((item) => `<span class="diff-tag good">${escapeHtml(removedLabel)} · ${escapeHtml(item)}</span>`),
  ].join("");
  return `
    <section class="diff-issue">
      <h5>${escapeHtml(title)}</h5>
      <div>${items || `<span class="diff-tag neutral">변화 없음</span>`}</div>
    </section>
  `;
}

function arrayDiff(beforeItems, afterItems) {
  const beforeSet = new Set(beforeItems);
  const afterSet = new Set(afterItems);
  return {
    added: afterItems.filter((item) => !beforeSet.has(item)),
    removed: beforeItems.filter((item) => !afterSet.has(item)),
  };
}

function sectionKey(section) {
  return `${section.label}::${section.source}`;
}

function billableMetric(result) {
  return result.actualTotalTokens ?? result.billableTokens ?? result.tokens;
}

function experimentFingerprint() {
  return JSON.stringify({
    caseId: state.caseId,
    prompt: normalizeDiffText(el.promptInput.value),
  });
}

function cloneForDiff(result) {
  return JSON.parse(JSON.stringify(result));
}

function normalizeDiffText(value) {
  return String(value ?? "").replace(/\r\n/g, "\n").trim();
}

function formatMetricValue(value, suffix) {
  const number = Number(value);
  const formatted = Number.isInteger(number) ? String(number) : number.toFixed(1).replace(/\.0$/, "");
  return suffix ? `${formatted}${suffix}` : formatted;
}

function formatDelta(delta, suffix) {
  if (delta === 0) return suffix ? `0${suffix}` : "0";
  const sign = delta > 0 ? "+" : "";
  return `${sign}${formatMetricValue(delta, suffix)}`;
}

function formatHistoryTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "시간 정보 없음";
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function truncateText(value, maxLength) {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}...` : text;
}

function markedApiPromptHtml(result) {
  return result.sections.map((section) => {
    const isUserInput = section.label === "현재 사용자 질문";
    const marker = isUserInput ? "*** 사용자 입력값 ***" : "*** 고정 컨텍스트 ***";
    const typeLabel = isUserInput ? "입력 프롬프트" : fixedSectionType(section);
    return `
      <section class="prompt-section ${isUserInput ? "user-input" : "fixed-context"}">
        <div class="prompt-marker">${marker}</div>
        <div class="prompt-label">
          <strong>[${escapeHtml(section.label)}]</strong>
          <span>${escapeHtml(typeLabel)} · ${section.tokens} token · 출처=${escapeHtml(section.source)}</span>
        </div>
        <pre>${escapeHtml(section.content || "(비어 있음)")}</pre>
      </section>
    `;
  }).join("");
}

function fixedSectionType(section) {
  if (section.source === "retriever") return "검색/RAG 근거";
  if (section.source === "tool") return "도구 결과 요약";
  if (section.label === "최근 대화") return "이전 대화";
  return "시스템/저장 상태";
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
      <div class="chip-row">
        <span class="small-chip">${escapeHtml(modeLabel(result))}</span>
        <span class="small-chip">${escapeHtml(actualTokenText(result))}</span>
      </div>
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
      <td>${escapeHtml(modeLabel(result))}</td>
      <td>${escapeHtml(retentionLabel(result.settings.retentionTurns))}</td>
      <td>${escapeHtml(compressionLabels[result.settings.compression])}</td>
      <td>${result.tokens} (${result.tokenUtilization}%)</td>
      <td>${escapeHtml(actualTokenText(result))}</td>
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
  el.tokenCaption.textContent = `KV cache 절감 ${result.cachedTokens} token · 응답 예약 ${result.reservedOutputTokens} token 제외`;
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

function guidanceFor(result) {
  const guidance = [
    `현재 선택한 '${result.name}'은 ${retentionLabel(result.settings.retentionTurns)}를 직접 포함합니다.`,
    result.mode === "openai"
      ? `이 답변은 ${result.model} Live API에서 받은 실제 응답입니다. Mock 점수는 보조 평가로만 해석하세요.`
      : "이 답변은 mock provider가 만든 모의 응답입니다. 실제 모델 품질 검증은 Live API로 확인하세요.",
    result.lesson,
  ];
  if (result.cachedTokens) {
    guidance.push(`KV cache 절감 추정치는 ${result.cachedTokens} token입니다. 반복되는 정책, 요약, 프로필을 prefix로 둘수록 효과가 커집니다.`);
  } else {
    guidance.push("KV cache를 끄면 같은 정책과 요약도 매 요청마다 다시 계산된다고 보면 됩니다.");
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

function modeLabel(result) {
  return result.mode === "openai" ? `Live API · ${result.model}` : "Mock mode";
}

function actualTokenText(result) {
  if (result.actualTotalTokens) {
    return `${result.actualTotalTokens} total`;
  }
  return result.mode === "openai" ? "usage 대기" : "mock";
}

function issueSummary(result) {
  const parts = [];
  if (result.missing.length) parts.push(`누락: ${result.missing.join(", ")}`);
  if (result.unsafe.length) parts.push(`위험: ${result.unsafe.join(", ")}`);
  if (result.warnings.length) parts.push(`경고: ${result.warnings.join(", ")}`);
  return parts.length ? parts.join(" · ") : "필수 맥락 보존";
}

function localizeAnswer(answer, mode) {
  if (mode === "openai") return String(answer);
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

function normalizeBudgetInputs() {
  const maxValue = Math.max(120, Number(el.maxTokens.value) || 900);
  const reservedValue = Math.max(20, Number(el.reservedTokens.value) || 200);
  el.maxTokens.value = String(maxValue);
  el.reservedTokens.value = String(reservedValue >= maxValue ? Math.max(20, maxValue - 20) : reservedValue);
}

function shouldAutoRun() {
  return el.modelMode.value === "mock";
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
  if (response.ok) {
    return response.json();
  }
  let message = await response.text();
  try {
    const parsed = JSON.parse(message);
    message = parsed.error || message;
  } catch {
    // Keep raw response text.
  }
  throw new Error(message);
}

el.caseSelect.addEventListener("change", async () => {
  await loadCase();
  await runExperiment();
});
el.restorePromptButton.addEventListener("click", () => {
  el.promptInput.value = state.defaultPrompt;
  if (shouldAutoRun()) runExperiment();
});
el.modelMode.addEventListener("change", () => {
  updateModeNotice();
  if (shouldAutoRun()) runExperiment();
});
el.liveScope.addEventListener("change", updateModeNotice);
el.runButton.addEventListener("click", runExperiment);
el.clearHistoryButton.addEventListener("click", () => {
  state.history = [];
  state.activeHistoryId = null;
  persistExperimentHistory();
  renderHistory();
});
el.resetBudgetButton.addEventListener("click", () => {
  el.retentionTurns.value = "4";
  el.compressionMode.value = "hybrid";
  el.retrievalMode.value = "on";
  el.kvCacheMode.value = "static";
  el.maxTokens.value = "900";
  el.reservedTokens.value = "200";
  if (shouldAutoRun()) runExperiment();
});
for (const input of [el.retentionTurns, el.compressionMode, el.retrievalMode, el.kvCacheMode, el.maxTokens, el.reservedTokens]) {
  input.addEventListener("change", () => {
    if (shouldAutoRun()) runExperiment();
    else updateModeNotice();
  });
}

init().catch((error) => {
  console.error(error);
  document.body.innerHTML = `<pre style="padding:24px;color:#ffb4ab">${escapeHtml(error.message)}</pre>`;
});
