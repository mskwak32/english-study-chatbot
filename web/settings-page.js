/** 읽기 전용 시스템 상태를 안전한 텍스트 DOM 요소로 표시합니다. */

import { loadSettingsStatus } from "/api.js";

const main = document.querySelector(".settings-page");
const status = document.querySelector(".learning-status");
const results = document.querySelector(".settings-results");

/**
 * 서버의 선택적 문자열·숫자를 화면용 기본 문구로 바꿉니다.
 *
 * @param {unknown} value 서버 응답 값입니다.
 * @param {string} [fallback] 값을 읽을 수 없을 때 표시할 문구입니다.
 * @returns {string} 표시 가능한 값 또는 기본 문구입니다.
 */
function textOrFallback(value, fallback = "N/A") {
  if (typeof value === "string" && value.trim()) {
    return value;
  }

  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }

  return fallback;
}

/**
 * 상태값을 점과 함께 표시할 DOM 요소로 만듭니다.
 *
 * @param {boolean | null} isHealthy 정상 여부입니다. 알 수 없으면 null입니다.
 * @param {string} label 사용자에게 보일 상태 문구입니다.
 * @returns {HTMLSpanElement} 상태 점과 상태 문구를 포함한 요소입니다.
 */
function createStatusValue(isHealthy, label) {
  const value = document.createElement("span");
  const indicator = document.createElement("span");

  value.className = "status-value";
  indicator.className = "status-indicator";
  indicator.setAttribute("aria-hidden", "true");

  if (isHealthy === true) {
    value.classList.add("is-healthy");
  } else if (isHealthy === false) {
    value.classList.add("is-unhealthy");
  } else {
    value.classList.add("is-unknown");
  }

  value.append(indicator, document.createTextNode(label));
  return value;
}

/**
 * 필드 쌍을 기존 학습 정보와 같은 설명 목록으로 만듭니다.
 *
 * @param {Array<[string, string | HTMLElement]>} fields 표시할 레이블과 값 쌍입니다.
 * @returns {HTMLDListElement} 상태 정보를 담은 설명 목록입니다.
 */
function createDetailList(fields) {
  const list = document.createElement("dl");
  list.className = "learning-detail-list";

  for (const [label, value] of fields) {
    const term = document.createElement("dt");
    const description = document.createElement("dd");

    term.textContent = label;
    if (value instanceof HTMLElement) {
      description.append(value);
    } else {
      description.textContent = value;
    }
    list.append(term, description);
  }

  return list;
}

/**
 * 한 상태 영역을 기존 카드 모양으로 만듭니다.
 *
 * @param {string} title 카드 제목입니다.
 * @param {Array<[string, string | HTMLElement]>} fields 카드에 표시할 값입니다.
 * @returns {HTMLElement} 상태 카드입니다.
 */
function createStatusCard(title, fields) {
  const card = document.createElement("article");
  const heading = document.createElement("h3");

  card.className = "learning-card";
  heading.textContent = title;
  card.append(heading, createDetailList(fields));
  return card;
}

/**
 * 시스템 상태 응답을 네 영역의 읽기 전용 카드로 표시합니다.
 * 누락된 각 값은 다른 영역에 영향을 주지 않고 N/A로 표시합니다.
 *
 * @param {object} data 서버가 반환한 설정 상태입니다.
 */
function renderSettingsStatus(data) {
  const model = data?.model ?? {};
  const ollama = data?.ollama ?? {};
  const system = data?.system ?? {};
  const learningData = data?.learningData ?? {};
  const cards = document.createElement("div");

  cards.className = "learning-card-list settings-card-list";
  cards.append(
    createStatusCard("AI 모델", [
      ["현재 모델", textOrFallback(model.name)],
      ["Ollama 모델", textOrFallback(model.ollamaName)],
      ["모델 크기", textOrFallback(model.size)],
      [
        "상태",
        createStatusValue(
          typeof model.loaded === "boolean" ? model.loaded : null,
          model.loaded === true
            ? "Loaded"
            : model.loaded === false
              ? "Not Loaded"
              : "N/A",
        ),
      ],
    ]),
    createStatusCard("Ollama", [
      [
        "API",
        createStatusValue(
          typeof ollama.apiConnected === "boolean"
            ? ollama.apiConnected
            : null,
          ollama.apiConnected === true
            ? "Connected"
            : ollama.apiConnected === false
              ? "Disconnected"
              : "N/A",
        ),
      ],
      ["Ollama Version", textOrFallback(ollama.version)],
    ]),
    createStatusCard("Raspberry Pi", [
      [
        "CPU",
        typeof system.cpuUsage === "number" && Number.isFinite(system.cpuUsage)
          ? `${system.cpuUsage}%`
          : "N/A",
      ],
      [
        "Memory",
        `${textOrFallback(system.memoryUsed)} / ${textOrFallback(system.memoryTotal)}`,
      ],
      [
        "Disk",
        `${textOrFallback(system.diskUsed)} / ${textOrFallback(system.diskTotal)}`,
      ],
    ]),
    createStatusCard("학습 데이터", [
      [
        "저장된 채팅 수",
        Number.isInteger(learningData.chatCount)
          ? `${learningData.chatCount}개`
          : "N/A",
      ],
      ["학습 데이터 사용량", textOrFallback(learningData.size)],
    ]),
  );
  results.replaceChildren(cards);
}

/** 설정 상태를 한 번 읽고, 실패해도 페이지 구조는 유지합니다. */
async function initializeSettingsPage() {
  try {
    renderSettingsStatus(await loadSettingsStatus());
    status.hidden = true;
  } catch (error) {
    console.error(error);
    renderSettingsStatus({});
    status.textContent =
      "설정 상태를 불러오지 못했습니다. 확인할 수 없는 값은 N/A로 표시합니다.";
    status.classList.add("is-error");
  } finally {
    main.setAttribute("aria-busy", "false");
  }
}

initializeSettingsPage();
