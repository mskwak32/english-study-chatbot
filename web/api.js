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
