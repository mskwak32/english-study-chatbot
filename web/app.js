import {
  createAdditionalChat,
  deleteChat,
  loadChatMessages,
  loadChats,
  loadInitialState,
  sendChatMessage,
  startTodayChat,
} from "/api.js";
import { deleteConfirmedChat } from "/chat-management.js";
import {
  createMessageFlow,
  shouldSubmitMessageShortcut,
} from "/message-flow.js";

const mainContent = document.querySelector("#main-content");
const chatPanel = document.querySelector("#chat-panel");
const chatTitle = document.querySelector("#chat-title");
const chatList = document.querySelector("#chat-list");
const createChatButton = document.querySelector("#create-chat-button");
const messageList = document.querySelector("#message-list");
const loadingStatus = document.querySelector("#loading-status");
const emptyMessage = document.querySelector("#empty-message");
const startLearning = document.querySelector("#start-learning");
const startLearningButton = document.querySelector("#start-learning-button");
const startLearningStatus = document.querySelector("#start-learning-status");
const messageForm = document.querySelector("#message-form");
const messageInput = document.querySelector("#message-input");
const sendButton = document.querySelector("#send-button");

let activeChatId = null;
let chats = [];
let hasTodayChat = false;
let isMessagePending = false;
let isManagementPending = false;

/**
 * 채팅 목록에 표시할 항목을 만들고 현재 선택 상태를 반영합니다.
 *
 * @param {{id: number, title: string}} chat 표시할 채팅입니다.
 * @param {number} selectedChatId 현재 선택된 채팅 식별자입니다.
 * @returns {HTMLLIElement} 채팅 목록 항목입니다.
 */
function createChatListItem(chat, selectedChatId) {
  const item = document.createElement("li");
  const selectButton = document.createElement("button");
  const deleteButton = document.createElement("button");

  item.className = "chat-list-item";
  selectButton.className = "chat-select-button";
  selectButton.type = "button";
  selectButton.textContent = chat.title;
  selectButton.addEventListener("click", () => selectChat(chat));

  deleteButton.className = "chat-delete-button";
  deleteButton.type = "button";
  deleteButton.textContent = "삭제";
  deleteButton.setAttribute("aria-label", `${chat.title} 삭제`);
  deleteButton.addEventListener("click", () => removeChat(chat));

  if (chat.id === selectedChatId) {
    item.classList.add("is-active");
    selectButton.setAttribute("aria-current", "true");
  }

  item.append(selectButton, deleteButton);
  return item;
}

/**
 * 저장된 메시지를 안전한 텍스트 DOM 요소로 만듭니다.
 *
 * @param {{role: string, content: string}} message 표시할 메시지입니다.
 * @returns {HTMLElement} 메시지 요소입니다.
 */
function createMessageElement(message) {
  const article = document.createElement("article");
  const author = document.createElement("p");
  const content = document.createElement("p");

  article.className = "message";

  if (message.role === "user") {
    article.classList.add("is-user");
  }

  author.className = "message-author";
  author.textContent = message.role === "user" ? "나" : "영어 튜터";

  content.className = "message-content";
  content.textContent = message.content;

  article.append(author, content);

  return article;
}

/**
 * 초기 API 상태를 화면과 현재 채팅 상태에 반영합니다.
 *
 * @param {{activeChat: object | null, chats: object[], messages: object[]}} state 초기 화면 상태입니다.
 */
function renderChatState({ activeChat, chats: nextChats, messages }) {
  activeChatId = activeChat?.id ?? null;
  chats = nextChats;
  chatTitle.textContent = activeChat?.title ?? "오늘의 학습";

  chatList.replaceChildren(
    ...chats.map((chat) => createChatListItem(chat, activeChatId)),
  );

  messageList.replaceChildren(...messages.map(createMessageElement));

  const hasActiveChat = activeChat !== null;
  chatPanel.hidden = !hasActiveChat;
  messageList.hidden = !hasActiveChat;
  emptyMessage.hidden = !hasActiveChat || messages.length > 0;
  startLearning.hidden = hasActiveChat;
  startLearningStatus.hidden = true;
  startLearningStatus.classList.remove("is-error");
  loadingStatus.hidden = true;
  syncControlState();
}

/**
 * 새 메시지 하나를 대화 영역에 추가합니다.
 *
 * @param {{role: string, content: string}} message 표시할 메시지입니다.
 */
function appendMessage(message) {
  messageList.append(createMessageElement(message));
  emptyMessage.hidden = true;
}

/** 선택·전송 요청이 겹치지 않도록 모든 조작 요소의 잠금 상태를 맞춥니다. */
function syncControlState() {
  const isPending = isMessagePending || isManagementPending;

  createChatButton.disabled = isPending || !hasTodayChat;
  startLearningButton.disabled = isPending;
  chatList.querySelectorAll("button").forEach((button) => {
    button.disabled = isPending;
  });
  messageInput.disabled = isPending || activeChatId === null;
  sendButton.disabled = isPending || activeChatId === null;
  mainContent.setAttribute("aria-busy", String(isPending));
}

/**
 * 메시지 전송 대기 상태에 맞춰 입력 폼과 로딩 안내를 갱신합니다.
 *
 * @param {boolean} isPending 전송 대기 여부입니다.
 */
function setMessageFormPending(isPending) {
  isMessagePending = isPending;
  syncControlState();

  if (isPending) {
    loadingStatus.textContent = "영어 튜터의 응답을 기다리는 중입니다.";
    loadingStatus.classList.remove("is-error");
    loadingStatus.hidden = false;
    return;
  }

  if (!loadingStatus.classList.contains("is-error")) {
    loadingStatus.hidden = true;
  }
}

/**
 * 채팅 관리 요청 중에는 목록과 메시지 입력을 함께 잠급니다.
 *
 * @param {string} message 사용자에게 보일 진행 상태입니다.
 */
function startManagementRequest(message) {
  isManagementPending = true;
  loadingStatus.textContent = message;
  loadingStatus.classList.remove("is-error");
  loadingStatus.hidden = false;
  syncControlState();
}

/** 관리 요청을 끝내고 오류가 없으면 진행 상태를 숨깁니다. */
function finishManagementRequest() {
  isManagementPending = false;
  syncControlState();

  if (!loadingStatus.classList.contains("is-error")) {
    loadingStatus.hidden = true;
  }
}

/**
 * 관리 요청 실패를 사용자에게 알립니다.
 *
 * @param {string} message 사용자에게 보일 오류입니다.
 * @param {unknown} error 기록할 원본 오류입니다.
 */
function showManagementError(message, error) {
  console.error(error);
  loadingStatus.textContent = message;
  loadingStatus.classList.add("is-error");
  loadingStatus.hidden = false;
}

/**
 * 선택한 채팅의 메시지를 읽어 현재 화면으로 전환합니다.
 *
 * @param {{id: number, title: string}} chat 선택할 채팅입니다.
 */
async function selectChat(chat) {
  if (chat.id === activeChatId || isMessagePending || isManagementPending) {
    return;
  }

  startManagementRequest("학습 기록을 불러오는 중입니다.");

  try {
    const messages = await loadChatMessages(chat.id);
    renderChatState({ activeChat: chat, chats, messages });
  } catch (error) {
    showManagementError(
      "선택한 학습 기록을 불러오지 못했습니다. 다시 시도해 주세요.",
      error,
    );
  } finally {
    finishManagementRequest();
  }
}

/** 생성한 추가 학습을 목록에 반영하고 바로 엽니다. */
async function createChat() {
  if (isMessagePending || isManagementPending || !hasTodayChat) {
    return;
  }

  startManagementRequest("추가 학습을 만드는 중입니다.");

  try {
    const chat = await createAdditionalChat();
    const [nextChats, messages] = await Promise.all([
      loadChats(),
      loadChatMessages(chat.id),
    ]);

    renderChatState({ activeChat: chat, chats: nextChats, messages });
  } catch (error) {
    showManagementError(
      "추가 학습을 만들지 못했습니다. 다시 시도해 주세요.",
      error,
    );
  } finally {
    finishManagementRequest();
  }
}

/** 오늘의 기본 학습을 만들고 바로 해당 대화 화면을 엽니다. */
async function startTodayLearning() {
  if (isMessagePending || isManagementPending || hasTodayChat) {
    return;
  }

  isManagementPending = true;
  startLearningStatus.textContent = "오늘의 학습을 시작하는 중입니다.";
  startLearningStatus.classList.remove("is-error");
  startLearningStatus.hidden = false;
  syncControlState();

  try {
    const chat = await startTodayChat();
    const [nextChats, messages] = await Promise.all([
      loadChats(),
      loadChatMessages(chat.id),
    ]);

    hasTodayChat = true;
    renderChatState({ activeChat: chat, chats: nextChats, messages });
  } catch (error) {
    console.error(error);
    startLearningStatus.textContent =
      "오늘의 학습을 시작하지 못했습니다. 다시 시도해 주세요.";
    startLearningStatus.classList.add("is-error");
    startLearningStatus.hidden = false;
  } finally {
    isManagementPending = false;
    syncControlState();
  }
}

/**
 * 삭제를 확인한 뒤 오늘 채팅을 기준으로 화면 전체를 안정 상태로 복원합니다.
 *
 * @param {{id: number, title: string}} chat 삭제할 채팅입니다.
 */
async function removeChat(chat) {
  if (isMessagePending || isManagementPending) {
    return;
  }

  startManagementRequest("학습 기록 삭제를 확인하는 중입니다.");

  try {
    const deleted = await deleteConfirmedChat(chat, {
      confirmDelete: (target) =>
        window.confirm(`\"${target.title}\" 학습 기록을 삭제하시겠습니까?`),
      deleteChat: async (chatId) => {
        loadingStatus.textContent = "학습 기록을 삭제하는 중입니다.";
        await deleteChat(chatId);
      },
    });

    if (!deleted) {
      return;
    }

    const initialState = await loadInitialState();
    hasTodayChat = initialState.activeChat !== null;
    renderChatState(initialState);
  } catch (error) {
    showManagementError(
      "학습 기록을 삭제하지 못했습니다. 다시 시도해 주세요.",
      error,
    );
  } finally {
    finishManagementRequest();
  }
}

const messageFlow = createMessageFlow({
  sendMessage: (content) => sendChatMessage(activeChatId, content),
  onUserMessage: appendMessage,
  onAssistantMessage: appendMessage,
  onError: (error) => {
    console.error(error);
    loadingStatus.textContent =
      "답변을 받지 못했습니다. 보낸 메시지는 학습 기록에 저장되었을 수 있으니 확인한 뒤 다시 시도해 주세요.";
    loadingStatus.classList.add("is-error");
    loadingStatus.hidden = false;
  },
  onPendingChange: setMessageFormPending,
});

messageForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (activeChatId === null || isMessagePending || isManagementPending) {
    return;
  }

  const content = messageInput.value.trim();

  if (!content) {
    return;
  }

  messageInput.value = "";
  await messageFlow.send(content);
  messageInput.focus();
});

createChatButton.addEventListener("click", createChat);
startLearningButton.addEventListener("click", startTodayLearning);

messageInput.addEventListener("keydown", (event) => {
  const hasCoarsePointer =
    window.matchMedia?.("(pointer: coarse)")?.matches ?? false;

  if (shouldSubmitMessageShortcut(event, hasCoarsePointer)) {
    event.preventDefault();
    messageForm.requestSubmit();
  }
});

/**
 * 초기 채팅 상태를 불러온 뒤 메시지 입력을 사용할 수 있게 합니다.
 */
async function startApplication() {
  try {
    const initialState = await loadInitialState();

    hasTodayChat = initialState.activeChat !== null;
    renderChatState(initialState);
  } catch (error) {
    console.error(error);

    loadingStatus.textContent =
      "학습 기록을 불러오지 못했습니다. 새로고침해 주세요.";
    loadingStatus.classList.add("is-error");
    mainContent.setAttribute("aria-busy", "false");
  }
}

startApplication();
