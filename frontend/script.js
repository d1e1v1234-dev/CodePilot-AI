"use strict";

/* =========================================================
   Configuration
   ========================================================= */
const API_BASE_URL = "https://codepilot-ai-q2ia.onrender.com";

const SUPPORTED_LANGUAGES = [
  "python", "cpp", "java", "javascript", "typescript", "html", "css", "sql",
];

const LANGUAGE_DOT_COLORS = {
  python: "linear-gradient(135deg, #3776ab, #ffd43b)",
  cpp: "linear-gradient(135deg, #00599c, #659ad2)",
  java: "linear-gradient(135deg, #f89820, #5382a1)",
  javascript: "linear-gradient(135deg, #f7df1e, #b8ac1a)",
  typescript: "linear-gradient(135deg, #3178c6, #235a97)",
  html: "linear-gradient(135deg, #e34f26, #f06529)",
  css: "linear-gradient(135deg, #264de4, #2965f1)",
  sql: "linear-gradient(135deg, #4479a1, #6ea3cc)",
};

// Languages that actually have static validation (AST + Ruff) in the backend.
const LANGUAGES_WITH_STATIC_VALIDATION = ["python"];

const LANGUAGE_PLACEHOLDERS = {
  python: "# Paste your Python code here...",
  cpp: "// Paste your C++ code here...",
  java: "// Paste your Java code here...",
  javascript: "// Paste your JavaScript code here...",
  typescript: "// Paste your TypeScript code here...",
  html: "<!-- Paste your HTML code here... -->",
  css: "/* Paste your CSS code here... */",
  sql: "-- Paste your SQL query here...",
};
/* =========================================================
   DOM References
   ========================================================= */
const backendStatusDot = document.getElementById("backendStatusDot");
const backendStatusText = document.getElementById("backendStatusText");

const codeInput = document.getElementById("codeInput");
const editorGutter = document.getElementById("editorGutter");
const languageSelect = document.getElementById("languageSelect");
const langDot = document.getElementById("langDot");

const uploadArea = document.getElementById("uploadArea");
const fileInput = document.getElementById("fileInput");
const browseBtn = document.getElementById("browseBtn");
const uploadFilename = document.getElementById("uploadFilename");

const extractBtn = document.getElementById("extractBtn");
const reviewBtn = document.getElementById("reviewBtn");
const clearBtn = document.getElementById("clearBtn");

const errorBox = document.getElementById("errorBox");

const emptyState = document.getElementById("emptyState");
const resultsContent = document.getElementById("resultsContent");

const scoreCircle = document.getElementById("scoreCircle");
const scoreValue = document.getElementById("scoreValue");
const summaryText = document.getElementById("summaryText");

const issuesList = document.getElementById("issuesList");
const issuesCount = document.getElementById("issuesCount");

const strengthsList = document.getElementById("strengthsList");

const sourcesList = document.getElementById("sourcesList");
const sourcesCount = document.getElementById("sourcesCount");

const validationBox = document.getElementById("validationBox");

const fixExplanationBlock = document.getElementById("fixExplanationBlock");
const fixExplanationText = document.getElementById("fixExplanationText");

const codeDiffBlock = document.getElementById("codeDiffBlock");
const originalCodeBlock = document.getElementById("originalCodeBlock");
const fixedCodeBlock = document.getElementById("fixedCodeBlock");
const copyFixedBtn = document.getElementById("copyFixedBtn");
const retryInfo = document.getElementById("retryInfo");

const progressSteps = {
  retrieve: document.querySelector('.progress-step[data-step="retrieve"]'),
  review: document.querySelector('.progress-step[data-step="review"]'),
  fix: document.querySelector('.progress-step[data-step="fix"]'),
  validate: document.querySelector('.progress-step[data-step="validate"]'),
  done: document.querySelector('.progress-step[data-step="done"]'),
};

let selectedFile = null;

/* =========================================================
   Language selector
   ========================================================= */
function updateLangDot() {
  const lang = languageSelect.value;
  langDot.style.background = LANGUAGE_DOT_COLORS[lang] || LANGUAGE_DOT_COLORS.python;
}

function updatePlaceholder() {
  const lang = languageSelect.value;
  codeInput.placeholder = LANGUAGE_PLACEHOLDERS[lang] || LANGUAGE_PLACEHOLDERS.python;
}

languageSelect.addEventListener("change", () => {
  updateLangDot();
  updatePlaceholder();
});

updateLangDot();
updatePlaceholder();

function setLanguageIfSupported(detectedLanguage) {
  if (!detectedLanguage) return;
  const normalized = detectedLanguage.trim().toLowerCase();
  if (SUPPORTED_LANGUAGES.includes(normalized)) {
    languageSelect.value = normalized;
    updateLangDot();
  }
  // If the detected language isn't in our supported list, we simply
  // leave the current selector value untouched rather than guessing.
}

/* =========================================================
   Backend health check
   ========================================================= */
async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/health`);
    if (!res.ok) throw new Error("unhealthy");
    const data = await res.json();
    backendStatusDot.classList.add("online");
    backendStatusDot.classList.remove("offline");
    backendStatusText.textContent = data.service || "connected";
  } catch (err) {
    backendStatusDot.classList.add("offline");
    backendStatusDot.classList.remove("online");
    backendStatusText.textContent = "backend offline";
  }
}
checkBackendHealth();

/* =========================================================
   Code editor line numbers
   ========================================================= */
function updateGutter() {
  const lineCount = codeInput.value.split("\n").length;
  const lines = [];
  for (let i = 1; i <= lineCount; i++) lines.push(i);
  editorGutter.textContent = lines.join("\n");
}
codeInput.addEventListener("input", updateGutter);
codeInput.addEventListener("scroll", () => {
  editorGutter.scrollTop = codeInput.scrollTop;
});
updateGutter();

/* =========================================================
   File upload (browse + drag & drop)
   ========================================================= */
browseBtn.addEventListener("click", () => fileInput.click());
uploadArea.addEventListener("click", (e) => {
  if (e.target === browseBtn) return;
  fileInput.click();
});

fileInput.addEventListener("change", () => {
  if (fileInput.files.length > 0) {
    handleFileSelection(fileInput.files[0]);
  }
});

["dragenter", "dragover"].forEach((evt) => {
  uploadArea.addEventListener(evt, (e) => {
    e.preventDefault();
    uploadArea.classList.add("dragover");
  });
});

["dragleave", "drop"].forEach((evt) => {
  uploadArea.addEventListener(evt, (e) => {
    e.preventDefault();
    uploadArea.classList.remove("dragover");
  });
});

uploadArea.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) handleFileSelection(file);
});

const ALLOWED_TYPES = ["image/png", "image/jpeg", "image/webp"];
const MAX_SIZE_BYTES = 8 * 1024 * 1024;

function handleFileSelection(file) {
  clearError();

  if (!ALLOWED_TYPES.includes(file.type)) {
    showError("Unsupported file type. Please upload PNG, JPG/JPEG, or WEBP.");
    return;
  }
  if (file.size > MAX_SIZE_BYTES) {
    showError("Image is too large. Maximum allowed size is 8MB.");
    return;
  }

  selectedFile = file;
  uploadFilename.textContent = `Selected: ${file.name}`;
  extractBtn.disabled = false;
}

/* =========================================================
   Extract Code (POST /api/extract-code)
   ========================================================= */
extractBtn.addEventListener("click", async () => {
  if (!selectedFile) return;

  clearError();
  setButtonLoading(extractBtn, true);

  const formData = new FormData();
  formData.append("file", selectedFile);

  try {
    const res = await fetch(`${API_BASE_URL}/api/extract-code`, {
      method: "POST",
      body: formData,
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Failed to extract code from image.");
    }

    // ExtractCodeResponse: { code, language, confidence, notes }
    codeInput.value = data.code || "";
    updateGutter();
    setLanguageIfSupported(data.language);

    let message = `Extracted code (language: ${data.language}, confidence: ${(data.confidence * 100).toFixed(0)}%).`;
    if (data.notes) {
      message += ` Note: ${data.notes}`;
    }
    showInfo(message);
  } catch (err) {
    showError(err.message || "Something went wrong while extracting the code.");
  } finally {
    setButtonLoading(extractBtn, false);
  }
});

/* =========================================================
   Review Code (POST /api/review)
   ========================================================= */
reviewBtn.addEventListener("click", async () => {
  const code = codeInput.value.trim();
  const language = languageSelect.value;

  clearError();

  if (!code) {
    showError("Please paste or extract some code before reviewing.");
    return;
  }

  setButtonLoading(reviewBtn, true);
  resetProgress();
  hideResults();

  animateProgress();

  try {
    const res = await fetch(`${API_BASE_URL}/api/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, language }),
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Code review failed.");
    }

    completeProgress();
    renderResults(code, data);
  } catch (err) {
    errorProgress();
    showError(err.message || "Something went wrong during the review.");
  } finally {
    setButtonLoading(reviewBtn, false);
  }
});

/* =========================================================
   Clear
   ========================================================= */
clearBtn.addEventListener("click", () => {
  codeInput.value = "";
  updateGutter();
  selectedFile = null;
  fileInput.value = "";
  uploadFilename.textContent = "";
  extractBtn.disabled = true;
  clearError();
  hideResults();
  resetProgress();
});

/* =========================================================
   Rendering results
   ========================================================= */
function renderResults(originalCode, data) {
  emptyState.hidden = true;
  resultsContent.hidden = false;

  renderScore(data.overall_score);
  summaryText.textContent = data.summary || "";

  renderIssues(data.issues || []);
  renderStrengths(data.strengths || []);
  renderSources(data.sources || []);
  renderValidation(data.validation || null, data.language || "python");
  renderFix(originalCode, data.fixed_code, data.fix_explanation, data.retry_count || 0);
}

function renderScore(score) {
  scoreValue.textContent = score ?? "--";
  scoreCircle.classList.remove("score-high", "score-mid", "score-low");
  if (typeof score === "number") {
    if (score >= 80) scoreCircle.classList.add("score-high");
    else if (score >= 50) scoreCircle.classList.add("score-mid");
    else scoreCircle.classList.add("score-low");
  }
}

function renderIssues(issues) {
  issuesCount.textContent = issues.length;
  issuesList.innerHTML = "";

  if (issues.length === 0) {
    issuesList.innerHTML = `<p class="no-items-text">No issues found.</p>`;
    return;
  }

  issues.forEach((issue) => {
    const card = document.createElement("div");
    card.className = `issue-card sev-${issue.severity}`;

    const lineTag = issue.line != null
      ? `<span class="tag tag-line">Line ${issue.line}</span>`
      : "";

    card.innerHTML = `
      <div class="issue-header">
        <span class="tag tag-severity-${issue.severity}">${issue.severity}</span>
        <span class="tag tag-category">${issue.category}</span>
        ${lineTag}
        <span class="issue-title">${escapeHtml(issue.title)}</span>
      </div>
      <p class="issue-desc">${escapeHtml(issue.description)}</p>
      <p class="issue-rec"><strong>Recommendation:</strong> ${escapeHtml(issue.recommendation)}</p>
    `;
    issuesList.appendChild(card);
  });
}

function renderStrengths(strengths) {
  strengthsList.innerHTML = "";
  if (strengths.length === 0) {
    strengthsList.innerHTML = `<li class="no-items-text">No notable strengths reported.</li>`;
    return;
  }
  strengths.forEach((s) => {
    const li = document.createElement("li");
    li.textContent = s;
    strengthsList.appendChild(li);
  });
}

function renderSources(sources) {
  sourcesCount.textContent = sources.length;
  sourcesList.innerHTML = "";

  if (sources.length === 0) {
    sourcesList.innerHTML = `<p class="no-items-text">No knowledge-base sources were retrieved for this review.</p>`;
    return;
  }

  sources.forEach((source) => {
    const chip = document.createElement("div");
    chip.className = "source-chip";
    chip.innerHTML = `
      <span>${escapeHtml(source.name)}</span>
      <span class="relevance">${source.relevance.toFixed(2)}</span>
    `;
    sourcesList.appendChild(chip);
  });
}

function renderValidation(validation, language) {
  validationBox.innerHTML = "";

  const isValidatedLanguage = LANGUAGES_WITH_STATIC_VALIDATION.includes(language);

  if (!isValidatedLanguage) {
    validationBox.innerHTML = `
      <p class="no-items-text">
        Static validation is currently available for Python only.
      </p>
    `;
    return;
  }

  if (!validation) {
    validationBox.innerHTML = `<p class="no-items-text">No fix was generated, so no validation was performed.</p>`;
    return;
  }

  const statusRow = document.createElement("div");
  statusRow.className = `validation-status-row ${validation.valid ? "valid" : "invalid"}`;
  statusRow.innerHTML = `
    <span>${validation.valid ? "✔ Passed static validation" : "✘ Failed static validation"}</span>
    <span class="validation-tool">(tool: ${escapeHtml(validation.tool)})</span>
  `;
  validationBox.appendChild(statusRow);

  if (validation.messages && validation.messages.length > 0) {
    const ul = document.createElement("ul");
    ul.className = "validation-messages";
    validation.messages.forEach((msg) => {
      const li = document.createElement("li");
      li.textContent = msg;
      ul.appendChild(li);
    });
    validationBox.appendChild(ul);
  }
}

function renderFix(originalCode, fixedCode, explanation, retryCount) {
  if (!fixedCode) {
    fixExplanationBlock.hidden = true;
    codeDiffBlock.hidden = true;
    return;
  }

  if (explanation) {
    fixExplanationBlock.hidden = false;
    fixExplanationText.textContent = explanation;
  } else {
    fixExplanationBlock.hidden = true;
  }

  codeDiffBlock.hidden = false;
  originalCodeBlock.textContent = originalCode;
  fixedCodeBlock.textContent = fixedCode;

  retryInfo.textContent = retryCount > 0
    ? `Fix required ${retryCount} retry attempt(s) before finalizing.`
    : `Fix was accepted on the first attempt (no retries needed).`;
}

/* =========================================================
   Copy button
   ========================================================= */
copyFixedBtn.addEventListener("click", async () => {
  const text = fixedCodeBlock.textContent;
  if (!text) return;

  try {
    await navigator.clipboard.writeText(text);
    copyFixedBtn.textContent = "Copied!";
    copyFixedBtn.classList.add("copied");
    setTimeout(() => {
      copyFixedBtn.textContent = "Copy";
      copyFixedBtn.classList.remove("copied");
    }, 1500);
  } catch (err) {
    showError("Could not copy to clipboard.");
  }
});

/* =========================================================
   Agent progress animation
   ========================================================= */
function resetProgress() {
  Object.values(progressSteps).forEach((el) => {
    el.classList.remove("active", "complete", "error");
  });
}

function animateProgress() {
  const order = ["retrieve", "review", "fix", "validate"];
  let i = 0;

  resetProgress();

  function step() {
    if (i > 0) {
      progressSteps[order[i - 1]].classList.remove("active");
      progressSteps[order[i - 1]].classList.add("complete");
    }
    if (i < order.length) {
      progressSteps[order[i]].classList.add("active");
      i++;
      window._progressTimer = setTimeout(step, 900);
    }
  }
  step();
}

function completeProgress() {
  clearTimeout(window._progressTimer);
  Object.values(progressSteps).forEach((el) => {
    el.classList.remove("active", "error");
    el.classList.add("complete");
  });
}

function errorProgress() {
  clearTimeout(window._progressTimer);
  Object.entries(progressSteps).forEach(([key, el]) => {
    if (el.classList.contains("active")) {
      el.classList.remove("active");
      el.classList.add("error");
    }
  });
}

/* =========================================================
   UI helpers
   ========================================================= */
function setButtonLoading(button, isLoading) {
  const spinner = button.querySelector(".btn-spinner");
  button.disabled = isLoading;
  if (spinner) spinner.hidden = !isLoading;
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function showInfo(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
  errorBox.classList.remove("alert-error");
  errorBox.style.background = "rgba(91, 141, 239, 0.12)";
  errorBox.style.border = "1px solid rgba(91, 141, 239, 0.3)";
  errorBox.style.color = "#9db8f0";

  setTimeout(() => {
    errorBox.hidden = true;
    errorBox.classList.add("alert-error");
    errorBox.style.background = "";
    errorBox.style.border = "";
    errorBox.style.color = "";
  }, 5000);
}

function clearError() {
  errorBox.hidden = true;
  errorBox.textContent = "";
  errorBox.classList.add("alert-error");
  errorBox.style.background = "";
  errorBox.style.border = "";
  errorBox.style.color = "";
}

function hideResults() {
  emptyState.hidden = false;
  resultsContent.hidden = true;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}