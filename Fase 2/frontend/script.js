const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const messages = document.getElementById("messages");
const statusBadge = document.getElementById("status");
const sendButton = document.getElementById("send-button");
const charCount = document.getElementById("char-count");
const clearButton = document.getElementById("clear-chat");
const topicButtons = document.querySelectorAll(".topic-chip");

const INITIAL_MESSAGE = "Hola. Puedes escribir tu consulta o seleccionar un tema del panel lateral para comenzar.";
const SCROLL_THRESHOLD = 80;

function isNearBottom() {
  return messages.scrollHeight - messages.scrollTop - messages.clientHeight < SCROLL_THRESHOLD;
}

function scrollToLatest(force = false) {
  if (!force && !isNearBottom()) return;

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      messages.scrollTo({ top: messages.scrollHeight, behavior: "auto" });
    });
  });
}

function focusInput() {
  input.focus({ preventScroll: true });
}

function addMessage(text, type = "bot") {
  const article = document.createElement("article");
  article.className = `message ${type}`;

  const avatar = document.createElement("span");
  avatar.className = "avatar";
  avatar.textContent = type === "user" ? "TU" : type === "error" ? "!" : "AI";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;

  article.appendChild(avatar);
  article.appendChild(bubble);
  messages.appendChild(article);
  scrollToLatest(true);
}

function addTypingIndicator() {
  const article = document.createElement("article");
  article.className = "message bot typing";
  article.id = "typing-indicator";

  const avatar = document.createElement("span");
  avatar.className = "avatar";
  avatar.textContent = "AI";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  for (let index = 0; index < 3; index += 1) {
    const dot = document.createElement("span");
    dot.className = "typing-dot";
    bubble.appendChild(dot);
  }

  article.appendChild(avatar);
  article.appendChild(bubble);
  messages.appendChild(article);
  scrollToLatest(true);
}

function removeTypingIndicator() {
  document.getElementById("typing-indicator")?.remove();
  scrollToLatest(true);
}

function updateCharCount() {
  charCount.textContent = `${input.value.length}/700`;
}

function resizeInput() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
}

function resetChat() {
  messages.innerHTML = "";
  addMessage(INITIAL_MESSAGE, "bot");
  scrollToLatest(true);
}

async function checkHealth() {
  try {
    const response = await fetch("/health");
    if (!response.ok) throw new Error("Backend no disponible");
    const data = await response.json();
    statusBadge.textContent = data.model || "Activo";
    statusBadge.className = "ok";
  } catch (error) {
    statusBadge.textContent = "Sin conexion";
    statusBadge.className = "error";
  }
}

async function sendMessage(message) {
  addMessage(message, "user");
  addTypingIndicator();

  sendButton.disabled = true;
  sendButton.textContent = "Enviando";

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "El backend no pudo procesar la consulta.");
    }

    removeTypingIndicator();
    addMessage(data.response, "bot");
  } catch (error) {
    removeTypingIndicator();
    addMessage(`No se pudo obtener respuesta. ${error.message}`, "error");
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = "Enviar";
    scrollToLatest(true);
    focusInput();
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();

  if (!message) {
    focusInput();
    return;
  }

  input.value = "";
  updateCharCount();
  resizeInput();
  await sendMessage(message);
});

input.addEventListener("input", updateCharCount);

input.addEventListener("input", resizeInput);

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

topicButtons.forEach((button) => {
  button.addEventListener("click", () => {
    input.value = button.dataset.prompt;
    updateCharCount();
    resizeInput();
    focusInput();
  });
});

clearButton.addEventListener("click", resetChat);

updateCharCount();
resizeInput();
checkHealth();
