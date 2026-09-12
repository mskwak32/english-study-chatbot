import { loadInitialState } from "/api.js";

const chatPanel = document.querySelector("#chat-panel");
const chatTitle = document.querySelector("#chat-title");
const chatList = document.querySelector("#chat-list");
const messageList = document.querySelector("#message-list");
const loadingStatus = document.querySelector("#loading-status");
const emptyMessage = document.querySelector("#empty-message");

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
  chatTitle.textContent = activeChat.title;

  chatList.replaceChildren(
    ...chats.map((chat) => createChatListItem(chat, activeChat.id)),
  );

  messageList.replaceChildren(...messages.map(createMessageElement));

  emptyMessage.hidden = messages.length > 0;
  loadingStatus.hidden = true;
  chatPanel.setAttribute("aria-busy", "false");
}

async function startApplication() {
  try {
    const initialState = await loadInitialState();

    renderInitialState(initialState);
  } catch (error) {
    console.error(error);

    loadingStatus.textContent =
      "학습 기록을 불러오지 못했습니다. 새로고침해 주세요.";
    loadingStatus.classList.add("is-error");
    chatPanel.setAttribute("aria-busy", "false");
  }
}

startApplication();
