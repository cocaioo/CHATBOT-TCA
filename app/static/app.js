const themeButton = document.querySelector("#theme-toggle");
function updateThemeButton() {
  const dark = document.documentElement.dataset.theme === "dark";
  themeButton.setAttribute("aria-label", dark ? "Ativar tema claro" : "Ativar tema escuro");
  themeButton.title = themeButton.getAttribute("aria-label");
}
themeButton.addEventListener("click", () => {
  const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("theme", theme); } catch { }
  updateThemeButton();
});
updateThemeButton();

const form = document.querySelector("#composer-form");
const textarea = document.querySelector("#question");
const sendButton = document.querySelector("#send-button");
const newChatButton = document.querySelector("#new-chat");
const characterCount = document.querySelector("#character-count");
const welcome = document.querySelector("#welcome");
const messages = document.querySelector("#messages");
const sessionId = document.querySelector("#session-id");

function updateSessionId(response) {
  const id = response.headers.get("X-Id-Sessao");
  if (id) {
    sessionId.querySelector("span").textContent = id;
    sessionId.hidden = false;
  }
}

let activeController = null;
let conversationVersion = 0;
let sending = false;

function scrollToLatest() {
  window.requestAnimationFrame(() => {
    window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
  });
}

function updateComposer() {
  sendButton.disabled = sending || textarea.value.trim().length === 0;
  characterCount.textContent = `${textarea.value.length} / 4000`;
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
}

function renderAssistantText(body, text) {
  body.innerHTML = DOMPurify.sanitize(marked.parse(text), { FORBID_TAGS: ["img"] });
}

function addMessage(role, text = "", pending = false) {
  const article = document.createElement("article");
  article.className = `message message-${role}${pending ? " message-pending" : ""}`;

  if (role === "assistant") {
    const avatar = document.createElement("span");
    avatar.className = "message-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = "✳";
    article.append(avatar);
  }

  const content = document.createElement("div");
  content.className = "message-content";

  const label = document.createElement("span");
  label.className = "message-role";
  label.textContent = role === "user" ? "Você" : "Assistente";

  const body = document.createElement("div");
  body.className = "message-text";
  if (role === "assistant" && !pending) renderAssistantText(body, text);
  else body.textContent = text;

  content.append(label, body);
  article.append(content);
  messages.append(article);
  welcome.hidden = true;
  scrollToLatest();

  return { article, body };
}

function renderHistory(history) {
  messages.replaceChildren();
  for (const message of history) {
    addMessage(message.papel === "usuario" ? "user" : "assistant", message.conteudo);
  }
  welcome.hidden = history.length > 0;
}

function showAssistantError(target, text) {
  target.article.classList.remove("message-pending");
  target.body.textContent = text;
  target.body.classList.add("error-text");
}

function parseSseBlock(block, onEvent) {
  let eventName = "message";
  const data = [];

  for (const line of block.split(/\r?\n/)) {
    if (!line || line.startsWith(":")) continue;
    const separator = line.indexOf(":");
    const field = separator < 0 ? line : line.slice(0, separator);
    let value = separator < 0 ? "" : line.slice(separator + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") eventName = value;
    if (field === "data") data.push(value);
  }

  if (data.length) onEvent(eventName, JSON.parse(data.join("\n")));
}

async function readStream(response, target, requestVersion) {
  if (!response.body) throw new Error("O navegador não conseguiu abrir o fluxo da resposta.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed = false;
  let receivedText = false;
  let assistantText = "";

  const handleEvent = (name, data) => {
    if (requestVersion !== conversationVersion) return;
    if (name === "trecho") {
      target.article.classList.remove("message-pending");
      assistantText += data.texto;
      renderAssistantText(target.body, assistantText);
      receivedText = true;
      scrollToLatest();
    } else if (name === "fim") {
      target.article.classList.remove("message-pending");
      completed = true;
    } else if (name === "erro") {
      showAssistantError(
        target,
        receivedText
          ? `${assistantText}\n\nNão foi possível concluir a resposta.`
          : data.detail
      );
    }
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        if (block) parseSseBlock(block, handleEvent);
      }
      if (done) break;
    }
    if (buffer.trim()) parseSseBlock(buffer, handleEvent);
  } finally {
    reader.releaseLock();
  }

  if (!completed && requestVersion === conversationVersion && !target.body.classList.contains("error-text")) {
    showAssistantError(
      target,
      receivedText ? `${assistantText}\n\nA resposta foi interrompida.` : "A resposta foi interrompida."
    );
  }
}

async function sendQuestion(question) {
  if (sending || !question.trim()) return;

  const cleanQuestion = question.trim();
  const requestVersion = conversationVersion;
  const controller = new AbortController();
  activeController = controller;
  sending = true;
  textarea.value = "";
  updateComposer();
  addMessage("user", cleanQuestion);
  const target = addMessage("assistant", "Pensando...", true);

  try {
    const response = await fetch("/conversa/mensagens", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pergunta: cleanQuestion }),
      signal: controller.signal,
    });

    if (requestVersion === conversationVersion) updateSessionId(response);

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Não foi possível enviar a mensagem (HTTP ${response.status}).`);
    }

    await readStream(response, target, requestVersion);
  } catch (error) {
    if (!controller.signal.aborted && requestVersion === conversationVersion) {
      showAssistantError(target, error.message || "Não foi possível conectar ao servidor.");
    }
  } finally {
    if (requestVersion === conversationVersion) {
      sending = false;
      activeController = null;
      updateComposer();
      textarea.focus();
    }
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  sendQuestion(textarea.value);
});

textarea.addEventListener("input", updateComposer);
textarea.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

newChatButton.addEventListener("click", async () => {
  newChatButton.disabled = true;
  try {
    const response = await fetch("/conversa/nova", { method: "POST" });
    if (!response.ok) throw new Error("Não foi possível iniciar uma nova conversa.");
    updateSessionId(response);
    const history = await response.json();

    conversationVersion += 1;
    activeController?.abort();
    activeController = null;
    sending = false;
    textarea.value = "";
    updateComposer();
    renderHistory(history.mensagens);
    textarea.focus();
  } catch (error) {
    window.alert(error.message || "Não foi possível iniciar uma nova conversa.");
  } finally {
    newChatButton.disabled = false;
  }
});

async function loadHistory() {
  try {
    const response = await fetch("/conversa");
    if (!response.ok) throw new Error("Não foi possível carregar o histórico.");
    updateSessionId(response);
    const history = await response.json();
    renderHistory(history.mensagens);
  } catch (error) {
    const target = addMessage("assistant");
    showAssistantError(target, error.message || "Não foi possível conectar ao servidor.");
  }
}

updateComposer();
loadHistory();
