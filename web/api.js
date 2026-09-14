/**
 * JSON 응답을 받는 API 요청을 수행합니다.
 *
 * @param {typeof fetch} fetchFunction 요청에 사용할 fetch 함수입니다.
 * @param {string} path API 경로입니다.
 * @param {RequestInit} [options] 요청 옵션입니다.
 * @returns {Promise<unknown>} 성공 응답의 JSON 본문입니다.
 * @throws {Error} 네트워크 요청이 실패하거나 HTTP 응답이 성공 상태가 아닐 때 발생합니다.
 */
async function requestJson(fetchFunction, path, options = {}) {
  const response = await fetchFunction(path, {
    ...options,
    headers: {
      Accept: "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`서버 요청에 실패했습니다: ${response.status}`);
  }

  return response.json();
}

/**
 * 현재 채팅에 사용자 메시지를 보내고 튜터 응답을 반환합니다.
 *
 * @param {number} chatId 대상 채팅 식별자입니다.
 * @param {string} content 보낼 메시지 내용입니다.
 * @param {typeof fetch} [fetchFunction] 요청에 사용할 fetch 함수입니다.
 * @returns {Promise<unknown>} 서버가 저장한 튜터 메시지입니다.
 */
export function sendChatMessage(
  chatId,
  content,
  fetchFunction = globalThis.fetch,
) {
  return requestJson(fetchFunction, `/chats/${chatId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ content }),
  });
}

/**
 * 지정한 채팅의 저장된 메시지를 순서대로 불러옵니다.
 *
 * @param {number} chatId 대상 채팅 식별자입니다.
 * @param {typeof fetch} [fetchFunction] 요청에 사용할 fetch 함수입니다.
 * @returns {Promise<object[]>} 저장된 메시지 목록입니다.
 */
export function loadChatMessages(chatId, fetchFunction = globalThis.fetch) {
  return requestJson(fetchFunction, `/chats/${chatId}/messages`);
}

/**
 * 오늘 날짜의 추가 학습 채팅을 생성합니다.
 *
 * @param {typeof fetch} [fetchFunction] 요청에 사용할 fetch 함수입니다.
 * @returns {Promise<object>} 새로 만든 채팅입니다.
 */
export function createAdditionalChat(fetchFunction = globalThis.fetch) {
  return requestJson(fetchFunction, "/chats/additional", { method: "POST" });
}

/**
 * 오늘의 기본 학습 채팅을 명시적으로 시작하거나, 이미 있으면 해당 채팅을 반환합니다.
 *
 * @param {typeof fetch} [fetchFunction] 요청에 사용할 fetch 함수입니다.
 * @returns {Promise<object>} 오늘의 기본 학습 채팅입니다.
 */
export function startTodayChat(fetchFunction = globalThis.fetch) {
  return requestJson(fetchFunction, "/chats/today/start", { method: "POST" });
}

/**
 * 초기 실력 테스트를 시작하고 튜터의 첫 문제를 포함한 오늘 채팅을 반환합니다.
 *
 * @param {typeof fetch} [fetchFunction] 요청에 사용할 fetch 함수입니다.
 * @returns {Promise<object>} 초기 실력 테스트를 시작한 오늘의 기본 채팅입니다.
 */
export function startProfileSetupChat(fetchFunction = globalThis.fetch) {
  return requestJson(fetchFunction, "/chats/today/profile-setup", {
    method: "POST",
  });
}

/**
 * 지정한 채팅을 삭제합니다. 성공 응답은 본문이 없는 204 상태입니다.
 *
 * @param {number} chatId 대상 채팅 식별자입니다.
 * @param {typeof fetch} [fetchFunction] 요청에 사용할 fetch 함수입니다.
 * @returns {Promise<void>} 삭제가 완료되면 이행됩니다.
 */
export async function deleteChat(chatId, fetchFunction = globalThis.fetch) {
  const response = await fetchFunction(`/chats/${chatId}`, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`서버 요청에 실패했습니다: ${response.status}`);
  }
}

/**
 * 전체 채팅 목록을 불러옵니다.
 *
 * @param {typeof fetch} [fetchFunction] 요청에 사용할 fetch 함수입니다.
 * @returns {Promise<object[]>} 채팅 목록입니다.
 */
export function loadChats(fetchFunction = globalThis.fetch) {
  return requestJson(fetchFunction, "/chats");
}

/**
 * 현재 학습 프로필을 불러옵니다. 프로필이 없으면 null을 반환합니다.
 *
 * @param {typeof fetch} [fetchFunction] 요청에 사용할 fetch 함수입니다.
 * @returns {Promise<object | null>} 현재 학습 프로필 또는 빈 프로필 상태입니다.
 */
export function loadLearningProfile(fetchFunction = globalThis.fetch) {
  return requestJson(fetchFunction, "/learning/profile");
}

/**
 * 최근 학습 이력 목록을 불러옵니다.
 *
 * @param {typeof fetch} [fetchFunction] 요청에 사용할 fetch 함수입니다.
 * @returns {Promise<object[]>} 서버가 정렬한 학습 이력 목록입니다.
 */
export function loadStudyRecords(fetchFunction = globalThis.fetch) {
  return requestJson(fetchFunction, "/learning/study-records");
}

/**
 * 복습 단어와 표현 목록을 불러옵니다.
 *
 * @param {typeof fetch} [fetchFunction] 요청에 사용할 fetch 함수입니다.
 * @returns {Promise<object[]>} 서버가 정렬한 복습 단어 목록입니다.
 */
export function loadReviewWords(fetchFunction = globalThis.fetch) {
  return requestJson(fetchFunction, "/learning/review-words");
}

/**
 * 오늘의 기본 학습과 화면에 필요한 초기 목록·메시지를 함께 불러옵니다.
 * 오늘의 기본 학습이 아직 없으면 이를 만들지 않고 빈 활성 채팅 상태를 반환합니다.
 *
 * @param {typeof fetch} [fetchFunction] 요청에 사용할 fetch 함수입니다.
 * @returns {Promise<{activeChat: object | null, chats: object[], messages: object[]}>} 초기 화면 상태입니다.
 */
export async function loadInitialState(fetchFunction = globalThis.fetch) {
  const activeChat = await requestJson(fetchFunction, "/chats/today");

  if (activeChat === null) {
    return {
      activeChat: null,
      chats: await loadChats(fetchFunction),
      messages: [],
    };
  }

  const [chats, messages] = await Promise.all([
    loadChats(fetchFunction),
    loadChatMessages(activeChat.id, fetchFunction),
  ]);

  return {
    activeChat,
    chats,
    messages,
  };
}
