async function requestJson(fetchFunction, path) {
  const response = await fetchFunction(path, {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`서버 요청에 실패했습니다: ${response.status}`);
  }

  return response.json();
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
