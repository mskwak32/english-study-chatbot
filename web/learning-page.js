/**
 * 학습 정보 단일 페이지의 탭을 전환하고, 각 데이터를 안전한 DOM 요소로 표시합니다.
 * 탭 전환은 문서 내 상태만 바꾸므로 브라우저 방문 기록을 추가하지 않습니다.
 */

import {
  loadLearningProfile,
  loadReviewWords,
  loadStudyRecords,
} from "/api.js";

const main = document.querySelector(".learning-page");
const status = document.querySelector(".learning-status");
const results = document.querySelector(".learning-results");
const title = document.querySelector("#learning-page-title");
const sectionButtons = document.querySelectorAll("[data-learning-section]");
const cachedData = new Map();
const pendingRequests = new Map();
let selectedSection = "profile";
let viewRequestId = 0;

/**
 * 비어 있거나 없는 서버 문자열을 화면용 기본 문구로 바꿉니다.
 *
 * @param {unknown} value 서버 응답의 선택적 문자열입니다.
 * @param {string} [fallback] 값이 없을 때 표시할 문구입니다.
 * @returns {string} 표시 가능한 원본 문자열 또는 기본 문구입니다.
 */
function textOrFallback(value, fallback = "미설정") {
  return typeof value === "string" && value.trim() ? value : fallback;
}

/**
 * 필드 쌍을 접근 가능한 설명 목록 DOM으로 만듭니다.
 *
 * @param {Array<[string, string]>} fields 표시할 레이블과 값 쌍입니다.
 * @returns {HTMLDListElement} 서버 문자열을 textContent로만 넣은 목록입니다.
 */
function createDetailList(fields) {
  const list = document.createElement("dl");
  list.className = "learning-detail-list";

  for (const [label, value] of fields) {
    const term = document.createElement("dt");
    const description = document.createElement("dd");

    term.textContent = label;
    description.textContent = value;
    list.append(term, description);
  }

  return list;
}

/**
 * 데이터가 없을 때 표시할 안내 DOM을 만듭니다.
 *
 * @param {string} message 사용자에게 보일 빈 상태 안내입니다.
 * @returns {HTMLParagraphElement} 빈 상태 메시지 요소입니다.
 */
function createEmptyMessage(message) {
  const empty = document.createElement("p");
  empty.className = "learning-empty-message";
  empty.textContent = message;
  return empty;
}

/**
 * 단일 프로필 또는 프로필 없음 상태를 결과 영역에 표시합니다.
 * 기존 결과 영역의 자식 요소를 교체합니다.
 *
 * @param {object | null} profile 서버가 반환한 학습 프로필입니다.
 */
function renderProfile(profile) {
  if (profile === null) {
    results.replaceChildren(createEmptyMessage("아직 학습 프로필이 없습니다."));
    return;
  }

  const card = document.createElement("article");
  card.className = "learning-card";
  card.append(
    createDetailList([
      ["학습자", textOrFallback(profile.learner_name)],
      ["목표 언어", textOrFallback(profile.target_language)],
      ["학습 목표", textOrFallback(profile.learning_goals, "없음")],
      ["학습 시작일", textOrFallback(profile.session_started_on)],
      ["현재 레벨", textOrFallback(profile.current_level)],
      ["레벨 갱신일", textOrFallback(profile.level_updated_on)],
      ["레벨 메모", textOrFallback(profile.level_note, "없음")],
      ["강점", textOrFallback(profile.strengths, "없음")],
      ["보완할 점", textOrFallback(profile.weaknesses, "없음")],
      ["최근 업데이트", textOrFallback(profile.updated_at)],
    ]),
  );
  results.replaceChildren(card);
}

/**
 * 학습 이력 배열 또는 빈 상태를 카드 목록으로 표시합니다.
 * 기존 결과 영역의 자식 요소를 교체합니다.
 *
 * @param {object[]} records 서버가 반환한 학습 이력입니다.
 */
function renderStudyRecords(records) {
  if (!records.length) {
    results.replaceChildren(createEmptyMessage("아직 학습 이력이 없습니다."));
    return;
  }

  const list = document.createElement("div");
  list.className = "learning-card-list";

  for (const record of records) {
    const card = document.createElement("article");
    const heading = document.createElement("h3");

    card.className = "learning-card";
    heading.textContent = textOrFallback(record.study_date, "학습 날짜 미설정");
    card.append(
      heading,
      createDetailList([
        ["학습 주제", textOrFallback(record.topic)],
        ["새 단어", textOrFallback(record.new_words, "없음")],
        ["표현", textOrFallback(record.expression, "없음")],
        ["메모", textOrFallback(record.notes, "없음")],
      ]),
    );
    list.append(card);
  }

  results.replaceChildren(list);
}

/**
 * 복습 단어 배열 또는 빈 상태를 카드 목록으로 표시합니다.
 * 기존 결과 영역의 자식 요소를 교체합니다.
 *
 * @param {object[]} words 서버가 반환한 복습 단어와 표현입니다.
 */
function renderReviewWords(words) {
  if (!words.length) {
    results.replaceChildren(createEmptyMessage("복습할 단어가 아직 없습니다."));
    return;
  }

  const list = document.createElement("div");
  list.className = "learning-card-list";

  for (const word of words) {
    const card = document.createElement("article");
    const heading = document.createElement("h3");

    card.className = "learning-card";
    heading.textContent = textOrFallback(word.term, "단어 미설정");
    card.append(
      heading,
      createDetailList([
        ["설명", textOrFallback(word.explanation, "없음")],
        ["최근 오답일", textOrFallback(word.last_wrong_on, "없음")],
        [
          "연속 정답",
          Number.isInteger(word.correct_streak)
            ? `${word.correct_streak}회`
            : "미설정",
        ],
      ]),
    );
    list.append(card);
  }

  results.replaceChildren(list);
}

const sectionConfig = {
  profile: {
    title: "학습 프로필",
    loadingMessage: "학습 프로필을 불러오는 중입니다.",
    errorMessage: "학습 프로필을 불러오지 못했습니다. 다시 선택해 주세요.",
    load: loadLearningProfile,
    render: renderProfile,
  },
  "study-records": {
    title: "학습 이력",
    loadingMessage: "학습 이력을 불러오는 중입니다.",
    errorMessage: "학습 이력을 불러오지 못했습니다. 다시 선택해 주세요.",
    load: loadStudyRecords,
    render: renderStudyRecords,
  },
  "review-words": {
    title: "복습 단어",
    loadingMessage: "복습 단어를 불러오는 중입니다.",
    errorMessage: "복습 단어를 불러오지 못했습니다. 다시 선택해 주세요.",
    load: loadReviewWords,
    render: renderReviewWords,
  },
};

/**
 * 탭별 데이터 요청을 한 번만 시작하고, 성공한 응답만 캐시합니다.
 * 진행 중인 같은 요청은 재사용하며 실패한 요청은 즉시 제거해 다음 선택에서 재시도합니다.
 *
 * @param {string} section 읽을 탭의 식별자입니다.
 * @returns {Promise<unknown>} 해당 탭의 서버 데이터입니다.
 */
function loadSectionData(section) {
  if (cachedData.has(section)) {
    return Promise.resolve(cachedData.get(section));
  }

  if (pendingRequests.has(section)) {
    return pendingRequests.get(section);
  }

  const request = sectionConfig[section]
    .load()
    .then((data) => {
      cachedData.set(section, data);
      return data;
    })
    .finally(() => {
      pendingRequests.delete(section);
    });

  pendingRequests.set(section, request);
  return request;
}

/**
 * 선택된 탭의 제목·버튼 상태·결과 영역을 갱신합니다.
 * 요청 번호를 비교해, 이전 탭의 늦은 응답이 현재 화면을 덮지 않도록 막습니다.
 *
 * @param {string} section 선택할 탭의 식별자입니다.
 */
async function selectLearningSection(section) {
  const config = sectionConfig[section];

  if (!config) {
    return;
  }

  const requestId = ++viewRequestId;
  selectedSection = section;
  title.textContent = config.title;
  main.setAttribute("aria-busy", "true");
  status.hidden = false;
  status.classList.remove("is-error");
  status.textContent = config.loadingMessage;
  results.replaceChildren();

  for (const button of sectionButtons) {
    button.setAttribute(
      "aria-pressed",
      String(button.dataset.learningSection === section),
    );
  }

  try {
    const data = await loadSectionData(section);

    if (requestId !== viewRequestId || section !== selectedSection) {
      return;
    }

    config.render(data);
    status.hidden = true;
  } catch (error) {
    if (requestId !== viewRequestId || section !== selectedSection) {
      return;
    }

    console.error(error);
    status.textContent = config.errorMessage;
    status.classList.add("is-error");
  } finally {
    if (requestId === viewRequestId && section === selectedSection) {
      main.setAttribute("aria-busy", "false");
    }
  }
}

for (const button of sectionButtons) {
  button.addEventListener("click", () => {
    selectLearningSection(button.dataset.learningSection);
  });
}

selectLearningSection(selectedSection);
