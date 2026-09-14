import assert from "node:assert/strict";
import test from "node:test";

import {
  createAdditionalChat,
  deleteChat,
  loadChatMessages,
  loadChats,
  loadInitialState,
  loadLearningProfile,
  loadReviewWords,
  loadStudyRecords,
  sendChatMessage,
  startProfileSetupChat,
  startTodayChat,
} from "../api.js";

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

test("오늘 기본 학습이 없으면 메시지를 요청하지 않고 빈 초기 상태를 반환한다", async () => {
  const requestedPaths = [];
  const chats = [];
  const fakeFetch = async (path) => {
    requestedPaths.push(path);

    return {
      ok: true,
      status: 200,
      json: async () => (path === "/chats/today" ? null : chats),
    };
  };

  const result = await loadInitialState(fakeFetch);

  assert.deepEqual(requestedPaths, ["/chats/today", "/chats"]);
  assert.deepEqual(result, { activeChat: null, chats, messages: [] });
});

test("채팅 메시지를 same-origin API에 JSON으로 전송한다", async () => {
  const assistantMessage = {
    id: 12,
    chat_id: 3,
    role: "assistant",
    content: "Hello!",
    sequence: 2,
    created_at: "2026-09-12T00:02:00+00:00",
  };
  let requestedPath;
  let requestedOptions;

  const fakeFetch = async (path, options) => {
    requestedPath = path;
    requestedOptions = options;

    return {
      ok: true,
      status: 200,
      json: async () => assistantMessage,
    };
  };

  const result = await sendChatMessage(3, "Hello", fakeFetch);

  assert.equal(requestedPath, "/chats/3/messages");
  assert.deepEqual(requestedOptions, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ content: "Hello" }),
  });
  assert.deepEqual(result, assistantMessage);
});

test("채팅 관리 API는 same-origin 경로와 HTTP 메서드를 사용한다", async () => {
  const requests = [];
  const fakeFetch = async (path, options) => {
    requests.push({ path, options });

    return {
      ok: true,
      status: path === "/chats/additional" ? 201 : 200,
      json: async () => ({ id: 7 }),
    };
  };

  await loadChatMessages(7, fakeFetch);
  await startTodayChat(fakeFetch);
  await startProfileSetupChat(fakeFetch);
  await createAdditionalChat(fakeFetch);
  await deleteChat(7, fakeFetch);
  await loadChats(fakeFetch);

  assert.deepEqual(requests, [
    {
      path: "/chats/7/messages",
      options: { headers: { Accept: "application/json" } },
    },
    {
      path: "/chats/today/start",
      options: { method: "POST", headers: { Accept: "application/json" } },
    },
    {
      path: "/chats/today/profile-setup",
      options: { method: "POST", headers: { Accept: "application/json" } },
    },
    {
      path: "/chats/additional",
      options: { method: "POST", headers: { Accept: "application/json" } },
    },
    {
      path: "/chats/7",
      options: { method: "DELETE", headers: { Accept: "application/json" } },
    },
    {
      path: "/chats",
      options: { headers: { Accept: "application/json" } },
    },
  ]);
});

test("학습 정보 API는 same-origin GET 경로를 사용한다", async () => {
  const requests = [];
  const fakeFetch = async (path, options) => {
    requests.push({ path, options });

    return {
      ok: true,
      status: 200,
      json: async () => [],
    };
  };

  await loadLearningProfile(fakeFetch);
  await loadStudyRecords(fakeFetch);
  await loadReviewWords(fakeFetch);

  assert.deepEqual(requests, [
    {
      path: "/learning/profile",
      options: { headers: { Accept: "application/json" } },
    },
    {
      path: "/learning/study-records",
      options: { headers: { Accept: "application/json" } },
    },
    {
      path: "/learning/review-words",
      options: { headers: { Accept: "application/json" } },
    },
  ]);
});
