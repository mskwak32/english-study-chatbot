import { loadInitialState, sendChatMessage } from "/api.js";
import { createMessageFlow } from "/message-flow.js";

const chatPanel = document.querySelector("#chat-panel");
const chatTitle = document.querySelector("#chat-title");
const chatList = document.querySelector("#chat-list");
const messageList = document.querySelector("#message-list");
const loadingStatus = document.querySelector("#loading-status");
const emptyMessage = document.querySelector("#empty-message");
const messageForm = document.querySelector("#message-form");
const messageInput = document.querySelector("#message-input");
const sendButton = document.querySelector("#send-button");

let activeChatId = null;

/**
 * 채팅 목록에 표시할 항목을 만들고 현재 선택 상태를 반영합니다.
 *
 * @param {{id: number, title: string}} chat 표시할 채팅입니다.
 * @param {number} activeChatId 현재 선택된 채팅 식별자입니다.
 * @returns {HTMLLIElement} 채팅 목록 항목입니다.
 */
function createChatListItem(chat, activeChatId) {
  const item = document.createElement("li");

  item.className = "chat-list-item";
  item.textContent = chat.title;

  if (chat.id === activeChatId) {
    item.classList.add("is-active");
    item.setAttribute("aria-current", "true");
  }

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
 * @param {{activeChat: object, chats: object[], messages: object[]}} state 초기 화면 상태입니다.
 */
function renderInitialState({ activeChat, chats, messages }) {
  activeChatId = activeChat.id;
  chatTitle.textContent = activeChat.title;

  chatList.replaceChildren(
    ...chats.map((chat) => createChatListItem(chat, activeChat.id)),
  );

  messageList.replaceChildren(...messages.map(createMessageElement));

  emptyMessage.hidden = messages.length > 0;
  loadingStatus.hidden = true;
  chatPanel.setAttribute("aria-busy", "false");
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

/**
 * 메시지 전송 대기 상태에 맞춰 입력 폼과 로딩 안내를 갱신합니다.
 *
 * @param {boolean} isPending 전송 대기 여부입니다.
 */
function setMessageFormPending(isPending) {
  messageInput.disabled = isPending;
  sendButton.disabled = isPending;
  chatPanel.setAttribute("aria-busy", String(isPending));

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

  const content = messageInput.value.trim();

  if (!content) {
    return;
  }

  messageInput.value = "";
  await messageFlow.send(content);
  messageInput.focus();
});

/**
 * 초기 채팅 상태를 불러온 뒤 메시지 입력을 사용할 수 있게 합니다.
 */
async function startApplication() {
  try {
    const initialState = await loadInitialState();

    renderInitialState(initialState);
    messageInput.disabled = false;
    sendButton.disabled = false;
  } catch (error) {
    console.error(error);

    loadingStatus.textContent =
      "학습 기록을 불러오지 못했습니다. 새로고침해 주세요.";
    loadingStatus.classList.add("is-error");
    chatPanel.setAttribute("aria-busy", "false");
  }
}

startApplication();
