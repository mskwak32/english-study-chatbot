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
 * 오늘의 채팅과 화면에 필요한 초기 목록·메시지를 함께 불러옵니다.
 *
 * @param {typeof fetch} [fetchFunction] 요청에 사용할 fetch 함수입니다.
 * @returns {Promise<{activeChat: object, chats: object[], messages: object[]}>} 초기 화면 상태입니다.
 */
export async function loadInitialState(fetchFunction = globalThis.fetch) {
  const activeChat = await requestJson(fetchFunction, "/chats/today");

  const [chats, messages] = await Promise.all([
    requestJson(fetchFunction, "/chats"),
    requestJson(fetchFunction, `/chats/${activeChat.id}/messages`),
  ]);

  return {
    activeChat,
    chats,
    messages,
  };
}
