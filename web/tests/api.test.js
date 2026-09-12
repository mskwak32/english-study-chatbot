import assert from "node:assert/strict";
import test from "node:test";

import { loadInitialState } from "../api.js";

test("오늘 채팅과 저장된 메시지를 초기 상태로 불러온다", async () => {
  const activeChat = {
    id: 3,
    study_date: "2026-09-12",
    kind: "default",
    extra_number: null,
    title: "2026-09-12 영어 학습",
    created_at: "2026-09-12T00:00:00+00:00",
  };

  const chats = [activeChat];

  const messages = [
    {
      id: 10,
      chat_id: 3,
      role: "user",
      content: "Hello",
      sequence: 1,
      created_at: "2026-09-12T00:01:00+00:00",
    },
  ];

  const responses = new Map([
    ["/chats/today", activeChat],
    ["/chats", chats],
    ["/chats/3/messages", messages],
  ]);

  const requestedPaths = [];

  const fakeFetch = async (path) => {
    requestedPaths.push(path);

    return {
      ok: true,
      status: 200,
      json: async () => responses.get(path),
    };
  };

  const result = await loadInitialState(fakeFetch);

  assert.deepEqual(requestedPaths, [
    "/chats/today",
    "/chats",
    "/chats/3/messages",
  ]);

  assert.deepEqual(result, {
    activeChat,
    chats,
    messages,
  });
});