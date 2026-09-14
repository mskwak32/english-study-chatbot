import assert from "node:assert/strict";
import test from "node:test";

import { deleteConfirmedChat } from "../chat-management.js";

test("채팅 삭제는 취소하면 요청하지 않고 승인하면 한 번 요청한다", async () => {
  const chat = { id: 7, title: "2026-09-12 영어 학습" };
  const deletedIds = [];

  const cancelled = await deleteConfirmedChat(chat, {
    confirmDelete: () => false,
    deleteChat: async (chatId) => deletedIds.push(chatId),
  });
  const confirmed = await deleteConfirmedChat(chat, {
    confirmDelete: () => true,
    deleteChat: async (chatId) => deletedIds.push(chatId),
  });

  assert.equal(cancelled, false);
  assert.equal(confirmed, true);
  assert.deepEqual(deletedIds, [7]);
});
