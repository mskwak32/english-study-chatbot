import assert from "node:assert/strict";
import test from "node:test";

import { createMessageFlow } from "../message-flow.js";

test("전송 성공 시 사용자와 assistant 메시지를 순서대로 알린다", async () => {
  const events = [];
  const assistantMessage = { role: "assistant", content: "Hello!" };
  const messageFlow = createMessageFlow({
    sendMessage: async (content) => {
      events.push(["request", content]);
      return assistantMessage;
    },
    onUserMessage: (message) => events.push(["user", message]),
    onAssistantMessage: (message) => events.push(["assistant", message]),
    onError: () => events.push(["error"]),
    onPendingChange: (isPending) => events.push(["pending", isPending]),
  });

  const sent = await messageFlow.send("Hello");

  assert.equal(sent, true);
  assert.deepEqual(events, [
    ["pending", true],
    ["user", { role: "user", content: "Hello" }],
    ["request", "Hello"],
    ["assistant", assistantMessage],
    ["pending", false],
  ]);
});

test("전송 실패 시 오류를 알리고 대기 상태를 해제한다", async () => {
  const events = [];
  const messageFlow = createMessageFlow({
    sendMessage: async () => {
      throw new Error("network error");
    },
    onUserMessage: (message) => events.push(["user", message]),
    onAssistantMessage: () => events.push(["assistant"]),
    onError: () => events.push(["error"]),
    onPendingChange: (isPending) => events.push(["pending", isPending]),
  });

  const sent = await messageFlow.send("Hello");

  assert.equal(sent, false);
  assert.deepEqual(events, [
    ["pending", true],
    ["user", { role: "user", content: "Hello" }],
    ["error"],
    ["pending", false],
  ]);
});

test("대기 중에는 두 번째 전송을 막는다", async () => {
  let resolveRequest;
  let requestCount = 0;
  const messageFlow = createMessageFlow({
    sendMessage: () => {
      requestCount += 1;
      return new Promise((resolve) => {
        resolveRequest = resolve;
      });
    },
    onUserMessage: () => {},
    onAssistantMessage: () => {},
    onError: () => {},
    onPendingChange: () => {},
  });

  const firstRequest = messageFlow.send("Hello");
  const secondRequest = await messageFlow.send("Again");

  assert.equal(secondRequest, false);
  assert.equal(requestCount, 1);

  resolveRequest({ role: "assistant", content: "Hello!" });
  await firstRequest;
});
