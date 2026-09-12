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

function appendMessage(message) {
  messageList.append(createMessageElement(message));
  emptyMessage.hidden = true;
}

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
      "메시지를 보내지 못했습니다. 잠시 후 다시 시도해 주세요.";
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
