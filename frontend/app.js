const chatLog = document.querySelector("#chatLog");
const chatForm = document.querySelector("#chatForm");
const chatInput = document.querySelector("#chatInput");
const sendButton = document.querySelector("#sendButton");
const face = document.querySelector("#agentFace");
const voiceButton = document.querySelector("#voiceButton");
const voiceHistory = document.querySelector("#voiceHistory");
const notesForm = document.querySelector("#notesForm");
const noteInput = document.querySelector("#noteInput");
const notesList = document.querySelector("#notesList");
const notesStatus = document.querySelector("#notesStatus");
const notesCount = document.querySelector("#notesCount");
const saveNoteButton = document.querySelector("#saveNoteButton");
let history = [];
let processing = false;
let listening = false;
let statusRefreshing = false;
let avatarTalking = false;
let hostedMode = false;
const defaultPermissions = { microphone: true, desktopControl: true, screenCapture: false, fileActions: false, powerActions: false, emailAccess: false, gemini: true };
let doPermissions = { ...defaultPermissions };
let appPreferences = { theme: "dark", enterToSend: true, showVoiceLog: true };
let siteAccessCode = sessionStorage.getItem("do-access-code") || "";
const accessGate = document.querySelector("#accessGate");
const apiFetch = (url, options = {}) => fetch(url, {
  ...options,
  headers: { ...(options.headers || {}), ...(siteAccessCode ? { "X-Do-Access-Code": siteAccessCode } : {}) },
});
function applyPreferences() {
  document.body.dataset.theme = appPreferences.theme;
  document.querySelector('meta[name="theme-color"]').content = appPreferences.theme === "light" ? "#fafafa" : "#09090b";
  document.querySelectorAll("[data-theme-choice]").forEach((button) => {
    const selected = button.dataset.themeChoice === appPreferences.theme;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  document.querySelector("#enterToSendSetting").checked = appPreferences.enterToSend;
  document.querySelector("#showVoiceLogSetting").checked = appPreferences.showVoiceLog;
  document.querySelector(".comms-foot span").innerHTML = appPreferences.enterToSend
    ? "ENTER TO SEND <i>·</i> SHIFT + ENTER FOR NEW LINE"
    : "ENTER FOR NEW LINE <i>·</i> CLICK SEND TO MESSAGE DO";
  document.querySelector("#sideRail").classList.toggle("voice-log-hidden", !appPreferences.showVoiceLog);
  localStorage.setItem("do-preferences", JSON.stringify(appPreferences));
}

try {
  const savedPreferences = JSON.parse(localStorage.getItem("do-preferences") || "{}");
  if (["light", "dark"].includes(savedPreferences.theme)) appPreferences.theme = savedPreferences.theme;
  if (typeof savedPreferences.enterToSend === "boolean") appPreferences.enterToSend = savedPreferences.enterToSend;
  if (typeof savedPreferences.showVoiceLog === "boolean") appPreferences.showVoiceLog = savedPreferences.showVoiceLog;
} catch { /* Ignore invalid browser preferences. */ }
applyPreferences();

function updatePermissionInputs() {
  document.querySelectorAll("[data-permission]").forEach((input) => { input.checked = Boolean(doPermissions[input.dataset.permission]); });
  document.querySelector("#fullAccessSetting").checked = Object.values(doPermissions).every(Boolean);
}

async function loadDoPermissions() {
  try {
    const response = await apiFetch("/api/settings");
    const payload = await response.json();
    hostedMode = Boolean(payload.hostedMode || hostedMode);
    if (!hostedMode && payload.settings) doPermissions = { ...defaultPermissions, ...payload.settings };
    if (hostedMode) {
      document.querySelector("#permissionControls").hidden = true;
      document.querySelector("#fullAccessSetting").disabled = true;
      document.querySelector("#hostedPermissionsNote").hidden = false;
      document.querySelector("#settingsSaveStatus").textContent = "Hosted mode · permissions are unavailable";
    }
    updatePermissionInputs();
  } catch { document.querySelector("#settingsSaveStatus").textContent = "Could not load permissions"; }
}

async function saveDoPermissions() {
  const status = document.querySelector("#settingsSaveStatus");
  status.textContent = "Saving…";
  try {
    const response = await apiFetch("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ settings: doPermissions }) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Could not save settings.");
    doPermissions = { ...defaultPermissions, ...payload.settings };
    updatePermissionInputs();
    status.textContent = "Permissions saved on this device.";
  } catch (error) { status.textContent = error.message; }
}

document.querySelectorAll("[data-theme-choice]").forEach((button) => button.addEventListener("click", () => {
  appPreferences.theme = button.dataset.themeChoice;
  applyPreferences();
}));
document.querySelector("#enterToSendSetting").addEventListener("change", (event) => { appPreferences.enterToSend = event.target.checked; applyPreferences(); });
document.querySelector("#showVoiceLogSetting").addEventListener("change", (event) => { appPreferences.showVoiceLog = event.target.checked; applyPreferences(); });
document.querySelectorAll("[data-settings-tab]").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll("[data-settings-tab]").forEach((tab) => tab.classList.toggle("active", tab === button));
  document.querySelectorAll("[data-settings-page]").forEach((page) => { const active = page.dataset.settingsPage === button.dataset.settingsTab; page.hidden = !active; page.classList.toggle("active", active); });
}));
document.querySelectorAll("[data-permission]").forEach((input) => input.addEventListener("change", () => {
  doPermissions[input.dataset.permission] = input.checked;
  updatePermissionInputs();
  saveDoPermissions();
}));
document.querySelector("#fullAccessSetting").addEventListener("change", (event) => {
  Object.keys(doPermissions).forEach((key) => { doPermissions[key] = event.target.checked; });
  updatePermissionInputs();
  saveDoPermissions();
});
loadDoPermissions();

function setAvatarTalking(active) {
  if (avatarTalking === active) return;
  avatarTalking = active;
  face.classList.toggle("speaking-state", active);
  document.body.classList.toggle("assistant-speaking", active);
}

function updateClock() {
  const now = new Date();
  const timeText = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  document.querySelector("#clock").textContent = timeText;
  document.querySelector("#clockMirror").textContent = timeText;
}
updateClock();
window.setInterval(updateClock, 1000);

function renderVoiceHistory(commands) {
  voiceHistory.replaceChildren();
  if (!commands?.length) {
    const empty = document.createElement("li");
    empty.textContent = "Recognized voice commands will appear here.";
    voiceHistory.append(empty);
    return;
  }
  for (const command of commands) {
    const item = document.createElement("li");
    const phrase = document.createElement("span");
    phrase.textContent = command.text;
    const time = document.createElement("time");
    time.dateTime = command.createdAt;
    time.textContent = new Date(command.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    item.append(phrase, time);
    voiceHistory.append(item);
  }
}

async function refreshStatus() {
  if (statusRefreshing) return;
  statusRefreshing = true;
  try {
    const response = await fetch("/api/status");
    const status = await response.json();
    const firstHostedStatus = Boolean(status.hostedMode) && !hostedMode;
    hostedMode = Boolean(status.hostedMode);
    if (hostedMode) {
      document.querySelector("#welcomeMessage").textContent = "Do is online. Enter an English request to begin.";
      document.querySelector("#notesStorageHint").textContent = "Private to this browser · stored on this device";
      document.querySelector(".notes-status").textContent = "Your notes are stored only in this browser and are not sent to the Do server.";
      document.querySelector(".stage-foot").hidden = true;
      document.querySelector(".agent-status").hidden = true;
      document.querySelector(".agent-hint").hidden = true;
      voiceButton.hidden = true;
      document.querySelector(".voice-debug").hidden = true;
      document.querySelector("#chatStatus").textContent = "PRIVATE HOSTED CHAT";
      document.querySelector(".quick-actions-bar").hidden = true;
      document.querySelector("#workspaceLink").textContent = "HOSTED CORE";
      document.querySelector('[data-view="voice"]').hidden = true;
      if (!siteAccessCode) accessGate.hidden = false;
      if (firstHostedStatus) loadNotes();
    }
    renderVoiceHistory(status.voiceCommands || []);
    document.querySelector("#aiStatus").textContent = status.aiConfigured ? "GEMINI ONLINE" : "API KEY NEEDED";
    listening = status.voiceAvailable === false ? false : status.voiceActive;
    document.body.classList.toggle("voice-listening", listening);
    document.querySelector("#voiceStatus").textContent = listening ? "VOICE LISTENER ON" : "VOICE STANDBY";
    document.querySelector("#voiceButtonText").textContent = listening ? "STOP VOICE ASSISTANT" : "START VOICE ASSISTANT";
    voiceButton.classList.toggle("active", listening);
    voiceButton.setAttribute("aria-pressed", String(listening));
    const hint = status.voiceError || status.voiceMessage || (listening ? "Listening for an English command…" : "Click start and speak English.");
    document.querySelector("#voiceHint").textContent = hint;
    setAvatarTalking(hint.toLowerCase().includes("speaking"));
  } catch {
    document.body.classList.remove("voice-listening");
    document.querySelector("#aiStatus").textContent = "LOCAL BRIDGE OFFLINE";
    document.querySelector("#voiceHint").textContent = "Restart Do to reconnect the local voice service.";
  } finally {
    statusRefreshing = false;
  }
}
refreshStatus();
window.setInterval(refreshStatus, 1100);

function renderNotes(notes) {
  notesList.replaceChildren();
  notesCount.textContent = `${notes.length} ${notes.length === 1 ? "NOTE" : "NOTES"}`;
  if (!notes.length) {
    const empty = document.createElement("p");
    empty.className = "notes-status";
    empty.textContent = "No notes saved yet.";
    notesList.append(empty);
    return;
  }
  for (const note of notes) {
    const item = document.createElement("article");
    item.className = "note-item";
    const content = document.createElement("div");
    content.className = "note-content";
    const text = document.createElement("p");
    text.textContent = note.content;
    const date = document.createElement("time");
    date.dateTime = note.createdAt;
    date.textContent = new Date(note.createdAt).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
    content.append(text, date);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "note-delete";
    remove.textContent = "DELETE";
    remove.setAttribute("aria-label", "Delete saved note");
    remove.addEventListener("click", () => deleteNote(note.id, remove));
    item.append(content, remove);
    notesList.append(item);
  }
}

async function loadNotes() {
  if (hostedMode) {
    try { renderNotes(JSON.parse(localStorage.getItem("do-private-notes") || "[]")); }
    catch { renderNotes([]); }
    return;
  }
  try {
    const response = await apiFetch("/api/notes");
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load notes.");
    renderNotes(data.notes || []);
  } catch (error) {
    notesStatus.textContent = error.message;
  }
}

notesForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const content = noteInput.value.trim();
  if (!content) {
    notesStatus.textContent = "Write a note before saving.";
    noteInput.focus();
    return;
  }
  saveNoteButton.disabled = true;
  notesStatus.textContent = "Saving note…";
  try {
    if (hostedMode) {
      const notes = JSON.parse(localStorage.getItem("do-private-notes") || "[]");
      notes.unshift({ id: crypto.randomUUID(), content, createdAt: new Date().toISOString() });
      localStorage.setItem("do-private-notes", JSON.stringify(notes.slice(0, 200)));
      noteInput.value = "";
      notesStatus.textContent = "Saved privately in this browser.";
      await loadNotes();
      return;
    }
    const response = await apiFetch("/api/notes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not save note.");
    noteInput.value = "";
    notesStatus.textContent = "Note saved on this computer.";
    await loadNotes();
  } catch (error) {
    notesStatus.textContent = error.message;
  } finally {
    saveNoteButton.disabled = false;
  }
});

async function deleteNote(id, button) {
  button.disabled = true;
  notesStatus.textContent = "Deleting note…";
  try {
    if (hostedMode) {
      const notes = JSON.parse(localStorage.getItem("do-private-notes") || "[]").filter((note) => note.id !== id);
      localStorage.setItem("do-private-notes", JSON.stringify(notes));
      notesStatus.textContent = "Note deleted from this browser.";
      await loadNotes();
      return;
    }
    const response = await apiFetch(`/api/notes/${encodeURIComponent(id)}`, { method: "DELETE" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not delete note.");
    notesStatus.textContent = "Note deleted.";
    await loadNotes();
  } catch (error) {
    notesStatus.textContent = error.message;
    button.disabled = false;
  }
}

loadNotes();

voiceButton.addEventListener("click", async () => {
  voiceButton.disabled = true;
  const action = listening ? "stop" : "start";
  document.querySelector("#voiceButtonText").textContent = action === "start" ? "STARTING MICROPHONE…" : "STOPPING LISTENER…";
  document.querySelector("#voiceHint").textContent = action === "start"
    ? "Starting the microphone. Speak English when it is ready…"
    : "Stopping the microphone listener…";
  try {
    const response = await apiFetch(`/api/voice/${action}`, { method: "POST" });
    if (!response.ok) throw new Error("The voice service did not accept the request.");
    await response.json();
    await refreshStatus();
  } catch (error) {
    document.querySelector("#voiceHint").textContent = `${error.message} Restart the desktop app and try again.`;
  } finally {
    voiceButton.disabled = false;
  }
});

function addMessage(role, text) {
  const article = document.createElement("article");
  article.className = `message ${role === "user" ? "user-message" : "agent-message"}`;
  const sender = document.createElement("span");
  sender.className = "sender";
  sender.append(document.createTextNode(role === "user" ? "YOU" : "DO"));
  const time = document.createElement("time");
  time.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  sender.append(time);
  const body = document.createElement("p");
  body.className = "message-text";
  body.textContent = text;
  const content = document.createElement("div");
  content.className = "message-content";
  content.append(body);
  article.append(sender, content);
  if (role !== "user") {
    const copyButton = document.createElement("button");
    copyButton.type = "button";
    copyButton.className = "message-copy";
    copyButton.textContent = "COPY";
    copyButton.setAttribute("aria-label", "Copy Do's full reply");
    copyButton.disabled = text === "Connecting to Do…";
    sender.append(copyButton);
  }
  chatLog.append(article);
  chatLog.scrollTop = chatLog.scrollHeight;
  return article;
}

async function copyChatMessage(article, button) {
  const messageText = article.dataset.copyText || article.querySelector(".message-content")?.innerText?.trim() || article.querySelector("p")?.textContent?.trim();
  if (!messageText) return;
  try {
    await navigator.clipboard.writeText(messageText);
  } catch {
    const temporaryInput = document.createElement("textarea");
    temporaryInput.value = messageText;
    temporaryInput.style.position = "fixed";
    temporaryInput.style.opacity = "0";
    document.body.append(temporaryInput);
    temporaryInput.select();
    const copied = document.execCommand("copy");
    temporaryInput.remove();
    if (!copied) {
      button.textContent = "FAILED";
      window.setTimeout(() => { button.textContent = "COPY"; }, 1600);
      return;
    }
  }
  button.textContent = "COPIED";
  window.setTimeout(() => { button.textContent = "COPY"; }, 1600);
}

function enableMessageCopy(article) {
  const button = article.querySelector(".message-copy");
  if (button) button.disabled = false;
}

function appendInlineMarkdown(container, text) {
  const tokenPattern = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let start = 0;
  for (const match of text.matchAll(tokenPattern)) {
    appendPlainText(container, text.slice(start, match.index));
    const token = match[0];
    const content = token.startsWith("**") ? token.slice(2, -2) : token.slice(1, -1);
    const element = document.createElement(token.startsWith("`") ? "code" : token.startsWith("**") ? "strong" : "em");
    element.textContent = content;
    container.append(element);
    start = match.index + token.length;
  }
  appendPlainText(container, text.slice(start));
}

function appendPlainText(container, text) {
  const lines = text.split("\n");
  lines.forEach((line, index) => {
    if (index) container.append(document.createElement("br"));
    if (line) container.append(document.createTextNode(line));
  });
}

function renderAssistantContent(article, text) {
  const content = article.querySelector(".message-content");
  if (!content) return;
  article.dataset.copyText = text;
  content.replaceChildren();
  const blocks = /```([^\r\n`]*)\r?\n([\s\S]*?)```/g;
  let cursor = 0;
  let match;
  while ((match = blocks.exec(text))) {
    if (match.index > cursor) {
      const paragraph = document.createElement("p");
      paragraph.className = "message-text";
      appendInlineMarkdown(paragraph, text.slice(cursor, match.index));
      content.append(paragraph);
    }
    const pre = document.createElement("pre");
    pre.className = "code-block";
    pre.dataset.language = match[1].trim() || "CODE";
    const code = document.createElement("code");
    code.textContent = match[2].replace(/\n$/, "");
    pre.append(code);
    content.append(pre);
    cursor = blocks.lastIndex;
  }
  if (cursor < text.length || !content.childElementCount) {
    const paragraph = document.createElement("p");
    paragraph.className = "message-text";
    appendInlineMarkdown(paragraph, text.slice(cursor));
    content.append(paragraph);
  }
}

chatLog.addEventListener("click", (event) => {
  const button = event.target.closest(".message-copy");
  if (button) copyChatMessage(button.closest(".message"), button);
});

function renderCard(card) {
  if (!card || !card.type) return null;
  const container = document.createElement("div");
  container.className = `rich-card ${card.type.replace(/_/g, "-")}`;

  if (card.type === "system_card") {
    container.innerHTML = `
      <div class="card-top">
        <span>HARDWARE TELEMETRY</span>
        <span class="card-tag">● LIVE SYS-01</span>
      </div>
      <div class="gauge-grid">
        <div class="gauge-unit">
          <div class="gauge-head">
            <span>CPU LOAD</span>
            <span>${card.cpu}%</span>
          </div>
          <div class="gauge-bar">
            <div class="gauge-fill ${card.cpu > 80 ? 'high' : ''}" style="width: ${Math.min(100, Math.max(4, card.cpu))}%"></div>
          </div>
        </div>
        <div class="gauge-unit">
          <div class="gauge-head">
            <span>RAM USAGE</span>
            <span>${card.ram_percent}%</span>
          </div>
          <div class="gauge-bar">
            <div class="gauge-fill ${card.ram_percent > 85 ? 'high' : ''}" style="width: ${Math.min(100, Math.max(4, card.ram_percent))}%"></div>
          </div>
        </div>
        <div class="gauge-unit">
          <div class="gauge-head">
            <span>RAM MEMORY</span>
            <span>${card.ram_used} / ${card.ram_total} GB</span>
          </div>
        </div>
        <div class="gauge-unit">
          <div class="gauge-head">
            <span>STORAGE FREE</span>
            <span>${card.disk_free} / ${card.disk_total} GB</span>
          </div>
        </div>
      </div>
      <div class="card-footer">
        <span>BATTERY: ${card.battery_percent !== null ? `${card.battery_percent}% ${card.battery_plugged ? '(CHARGING)' : ''}` : 'AC MAINS'}</span>
        <span>STATUS: 100% OPERATIONAL</span>
      </div>
    `;
  } else if (card.type === "media_card") {
    const title = document.createElement("div");
    title.className = "media-title";
    title.textContent = String(card.song ?? "");
    const link = document.createElement("a");
    const safeUrl = new URL(String(card.url ?? ""), window.location.href);
    if (safeUrl.protocol !== "https:" || safeUrl.hostname !== "www.youtube.com") return null;
    link.href = safeUrl.href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.className = "card-btn";
    link.textContent = "OPEN YT ↗";
    const top = document.createElement("div");
    top.className = "card-top";
    top.innerHTML = '<span>MEDIA CONTROLLER</span><span class="card-tag">YOUTUBE</span>';
    const body = document.createElement("div");
    body.className = "media-card-body";
    const info = document.createElement("div");
    info.className = "media-info";
    const disc = document.createElement("div");
    disc.className = "media-disc";
    disc.textContent = "♫";
    info.append(disc, title);
    body.append(info, link);
    container.append(top, body);
  } else if (card.type === "screenshot_card") {
    container.innerHTML = `
      <div class="card-top">
        <span>SCREEN CAPTURE</span>
        <span class="card-tag">SAVED</span>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="font-weight: 700; font-size: 11px;">${card.filename}</span>
        <span style="font-size: 8px; color: #7f6655;">SAVED IN PROJECT FOLDER</span>
      </div>
    `;
  } else if (card.type === "time_card") {
    container.innerHTML = `
      <div class="card-top">
        <span>CHRONOMETER</span>
        <span class="card-tag">LOCAL</span>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="font-size: 15px; font-weight: 700; color: var(--ink);">${card.time}</span>
        <span style="font-size: 8.5px; font-weight: 700; color: #7f6655;">${card.date}</span>
      </div>
    `;
  } else {
    return null;
  }
  return container;
}

function animateReply(element, text, cardData = null) {
  const body = element.querySelector("p");
  element.classList.remove("assistant-pending");
  body.textContent = "";
  const cursor = document.createElement("span");
  cursor.className = "typing-cursor";
  body.append(cursor);
  face.classList.add("happy-state");
  setAvatarTalking(true);
  processing = true;
  const duration = Math.min(1000, Math.max(220, text.length * 6));
  const chunkSize = Math.max(1, Math.ceil(text.length / (duration / 17)));
  let position = 0;
  return new Promise((resolve) => {
    const type = () => {
      position = Math.min(text.length, position + chunkSize);
      body.firstChild?.remove();
      body.insertBefore(document.createTextNode(text.slice(0, position)), body.firstChild);
      if (position < text.length) {
        body.append(cursor);
        chatLog.scrollTop = chatLog.scrollHeight;
        window.setTimeout(type, 17);
      } else {
        cursor.remove();
        renderAssistantContent(element, text);
        if (cardData) {
          const cardEl = renderCard(cardData);
          if (cardEl) {
            element.append(cardEl);
            chatLog.scrollTop = chatLog.scrollHeight;
          }
        }
        face.classList.remove("happy-state");
        setAvatarTalking(false);
        processing = false;
        enableMessageCopy(element);
        resetPupils();
        resolve();
      }
    };
    type();
  });
}

async function sendMessage(rawText) {
  const message = rawText.trim();
  if (!message || processing) return;
  document.querySelector("#starterSuggestions").hidden = true;
  processing = true;
  addMessage("user", message);
  history.push({ role: "user", content: message });
  chatInput.value = "";
  chatInput.style.height = "auto";
  sendButton.disabled = true;
  document.querySelector("#chatStatus").textContent = "PROCESSING REQUEST…";
  sendButton.textContent = "WAIT…";
  face.classList.add("squint-state");
  const replyElement = addMessage("assistant", "Connecting to Do…");
  replyElement.classList.add("assistant-pending");
  let waitingSeconds = 0;
  let receivedFirstToken = false;
  const waitIndicator = window.setInterval(() => {
    if (receivedFirstToken) return;
    waitingSeconds += 1;
    const statusText = waitingSeconds < 8
      ? `Do is thinking · ${waitingSeconds}s`
      : waitingSeconds < 20
      ? `Still generating a reply · ${waitingSeconds}s`
      : `Taking longer than usual · ${waitingSeconds}s`;
    replyElement.querySelector("p").textContent = statusText;
    document.querySelector("#chatStatus").textContent = waitingSeconds >= 20 ? "SLOW AI RESPONSE" : "DO IS THINKING";
  }, 1000);
  const controller = new AbortController();
  const requestTimeout = window.setTimeout(() => controller.abort(), 45000);
  try {
    const response = await apiFetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history.slice(-12) }),
      signal: controller.signal,
    });
    if (!response.ok) {
      let errorData = {};
      try { errorData = await response.json(); } catch { /* Keep the generic error below. */ }
      if (response.status === 401 && hostedMode) accessGate.hidden = false;
      throw new Error(errorData.error || "The intelligence core did not respond.");
    }
    if (response.headers.get("Content-Type")?.includes("application/x-ndjson")) {
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      const body = replyElement.querySelector("p");
      let buffer = "";
      let answer = "";
      let completed = false;
      const processEvent = (line) => {
        if (!line.trim()) return;
        const eventData = JSON.parse(line);
        if (eventData.type === "error") throw new Error(eventData.error || "The AI service ended unexpectedly.");
        if (eventData.type === "delta" && eventData.text) {
          if (!receivedFirstToken) {
            receivedFirstToken = true;
            replyElement.classList.remove("assistant-pending");
            body.textContent = "";
            face.classList.add("happy-state");
            setAvatarTalking(true);
          }
          answer += eventData.text;
          body.textContent = answer;
          chatLog.scrollTop = chatLog.scrollHeight;
        }
        if (eventData.type === "done") completed = true;
      };
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) processEvent(line);
        if (done) break;
      }
      if (buffer.trim()) processEvent(buffer);
      if (!completed || !answer) throw new Error("Do's reply ended before it was complete. Please try again.");
      renderAssistantContent(replyElement, answer);
      history.push({ role: "assistant", content: answer });
      enableMessageCopy(replyElement);
      face.classList.remove("happy-state");
      setAvatarTalking(false);
      resetPupils();
      processing = false;
    } else {
      let data;
      try { data = await response.json(); }
      catch { throw new Error("The AI service returned an unreadable response. Please try again."); }
      receivedFirstToken = true;
      replyElement.classList.remove("assistant-pending");
      history.push({ role: "assistant", content: data.reply });
      await animateReply(replyElement, data.reply, data.card);
    }
    document.querySelector("#chatStatus").textContent = "GEMINI CHAT · READY";
  } catch (error) {
    if (history.at(-1)?.role === "user" && history.at(-1)?.content === message) history.pop();
    replyElement.querySelector("p").textContent = error.name === "AbortError"
      ? "The AI service took too long to respond. Check your connection or API key, then try again."
      : error instanceof TypeError
      ? "Local AI connection unavailable. Restart the Do desktop app and try again."
      : error.message;
    replyElement.classList.remove("assistant-pending");
    enableMessageCopy(replyElement);
    document.querySelector("#chatStatus").textContent = "REQUEST FAILED";
    face.classList.remove("happy-state", "squint-state");
    setAvatarTalking(false);
    processing = false;
  } finally {
    window.clearInterval(waitIndicator);
    window.clearTimeout(requestTimeout);
    face.classList.remove("squint-state");
    sendButton.disabled = false;
    sendButton.innerHTML = 'SEND <span aria-hidden="true">↗</span>';
    chatInput.focus();
    chatLog.scrollTop = chatLog.scrollHeight;
  }
}

document.querySelectorAll(".action-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    const cmd = chip.getAttribute("data-cmd");
    if (cmd) sendMessage(cmd);
  });
});

document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => sendMessage(button.dataset.prompt)));

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(chatInput.value);
});

const initialMessage = chatLog.firstElementChild;
const initialCopyButton = document.createElement("button");
initialCopyButton.type = "button";
initialCopyButton.className = "message-copy";
initialCopyButton.textContent = "COPY";
initialCopyButton.setAttribute("aria-label", "Copy Do's full reply");
initialMessage.querySelector(".sender").append(initialCopyButton);
const openingMessage = initialMessage.cloneNode(true);
document.querySelectorAll(".nav-item").forEach((item) => {
  item.addEventListener("click", () => {
    const view = item.dataset.view;
    document.querySelectorAll(".nav-item").forEach((navItem) => navItem.classList.toggle("active", navItem === item));
    const memoryOpen = view === "memory";
    const settingsOpen = view === "settings";
    document.querySelector("#memoryView").hidden = !memoryOpen;
    document.querySelector("#settingsView").hidden = !settingsOpen;
    document.querySelector(".workspace").classList.toggle("memory-open", memoryOpen);
    document.querySelector(".workspace").classList.toggle("settings-open", settingsOpen);
    document.querySelector("#workspaceTitle").textContent = memoryOpen
      ? "Memory vault"
      : settingsOpen ? "Settings" : view === "voice" ? "Voice activity" : "New conversation";
    document.querySelector("#sideRail").classList.toggle("show-voice-log", view === "voice");
    if (memoryOpen) loadNotes();
    if (view === "voice" && !hostedMode && !listening) voiceButton.click();
    if (view === "chat") {
      if (processing) return;
      history = [];
      chatLog.replaceChildren(openingMessage.cloneNode(true));
      document.querySelector("#starterSuggestions").hidden = false;
      const welcome = chatLog.querySelector("#welcomeMessage");
      if (hostedMode && welcome) welcome.textContent = "Do is online. Enter an English request to begin.";
      document.querySelector("#workspaceTitle").textContent = "New conversation";
      document.querySelector("#chatStatus").textContent = hostedMode ? "PRIVATE HOSTED CHAT" : "GEMINI CHAT";
      chatInput.value = "";
      chatInput.style.height = "auto";
    }
  });
});

const appLayout = document.querySelector(".app-layout");
const sidebarToggle = document.querySelector("#sidebarToggle");
const commandPalette = document.querySelector("#commandPalette");
const paletteInput = document.querySelector("#paletteInput");
const paletteItems = [...document.querySelectorAll(".palette-item")];
try {
  const collapsed = localStorage.getItem("do-sidebar-collapsed") === "true";
  appLayout.classList.toggle("sidebar-collapsed", collapsed);
  sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
  sidebarToggle.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
} catch { /* Keep the sidebar expanded if storage is unavailable. */ }

sidebarToggle.addEventListener("click", () => {
  const collapsed = appLayout.classList.toggle("sidebar-collapsed");
  sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
  sidebarToggle.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
  sidebarToggle.title = collapsed ? "Expand sidebar" : "Collapse sidebar";
  try { localStorage.setItem("do-sidebar-collapsed", String(collapsed)); } catch { /* Keep the current state for this session. */ }
});

function openCommandPalette() {
  commandPalette.hidden = false;
  paletteInput.value = "";
  filterPaletteItems();
  window.requestAnimationFrame(() => paletteInput.focus());
}

function closeCommandPalette() {
  commandPalette.hidden = true;
  document.querySelector("#commandTrigger").focus();
}

function filterPaletteItems() {
  const query = paletteInput.value.trim().toLowerCase();
  paletteItems.forEach((item) => { item.hidden = !item.textContent.toLowerCase().includes(query); });
  document.querySelector("#paletteEmpty").hidden = paletteItems.some((item) => !item.hidden);
}

document.querySelector("#commandTrigger").addEventListener("click", openCommandPalette);
if (/mac/i.test(navigator.platform)) document.querySelector("#commandTrigger kbd").textContent = "⌘ K";
paletteInput.addEventListener("input", filterPaletteItems);
commandPalette.addEventListener("click", (event) => {
  if (event.target === commandPalette) closeCommandPalette();
});
commandPalette.addEventListener("keydown", (event) => {
  if (event.key !== "Tab") return;
  const focusable = [paletteInput, ...paletteItems.filter((item) => !item.hidden)];
  const first = focusable[0];
  const last = focusable.at(-1);
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
});
document.querySelectorAll(".palette-item").forEach((item) => item.addEventListener("click", () => {
  const action = item.dataset.paletteAction;
  closeCommandPalette();
  if (action.startsWith("view:")) document.querySelector(`[data-view="${action.slice(5)}"]`)?.click();
  else if (action === "voice") voiceButton.click();
  else sendMessage(action);
}));
paletteInput.addEventListener("keydown", (event) => {
  const visibleItems = paletteItems.filter((item) => !item.hidden);
  if (event.key === "Enter") {
    event.preventDefault();
    visibleItems[0]?.click();
    return;
  }
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    const current = visibleItems.indexOf(document.activeElement);
    const direction = event.key === "ArrowDown" ? 1 : -1;
    const next = current < 0 ? (direction > 0 ? 0 : visibleItems.length - 1) : (current + direction + visibleItems.length) % visibleItems.length;
    visibleItems[next]?.focus();
  }
});
document.querySelector("#paletteResults").addEventListener("keydown", (event) => {
  if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
  const visibleItems = paletteItems.filter((item) => !item.hidden);
  const current = visibleItems.indexOf(document.activeElement);
  const direction = event.key === "ArrowDown" ? 1 : -1;
  const next = current < 0 ? (direction > 0 ? 0 : visibleItems.length - 1) : (current + direction + visibleItems.length) % visibleItems.length;
  event.preventDefault();
  visibleItems[next]?.focus();
});
document.addEventListener("keydown", (event) => {
  const target = event.target;
  const editing = target instanceof HTMLElement && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    if (commandPalette.hidden) openCommandPalette();
    else closeCommandPalette();
  } else if (event.key === "Escape" && !commandPalette.hidden) {
    closeCommandPalette();
  } else if (event.key === "/" && !editing && commandPalette.hidden) {
    event.preventDefault();
    openCommandPalette();
  }
});
chatInput.addEventListener("input", () => {
  chatInput.style.height = "auto";
  chatInput.style.height = `${Math.min(chatInput.scrollHeight, 110)}px`;
  face.classList.toggle("squint-state", Boolean(chatInput.value));
  document.body.classList.toggle("composer-active", Boolean(chatInput.value));
});
chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && appPreferences.enterToSend) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});
chatInput.addEventListener("focus", () => resetPupils());
chatInput.addEventListener("blur", () => {
  face.classList.remove("squint-state");
});

function resetPupils() {}



document.querySelector("#accessForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const code = document.querySelector("#accessCodeInput").value;
  const submit = document.querySelector("#accessSubmit");
  const message = document.querySelector("#accessMessage");
  submit.disabled = true;
  message.textContent = "Checking access…";
  try {
    const response = await fetch("/api/access", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) });
    const result = await response.json();
    if (!response.ok || !result.authorized) throw new Error(result.error || "Access denied.");
    siteAccessCode = code;
    sessionStorage.setItem("do-access-code", code);
    accessGate.hidden = true;
    message.textContent = "";
  } catch (error) {
    message.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});

const installButton = document.querySelector("#installButton");
let pendingInstall = null;
window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  pendingInstall = event;
  installButton.hidden = false;
});
installButton.addEventListener("click", async () => {
  if (!pendingInstall) return;
  pendingInstall.prompt();
  await pendingInstall.userChoice;
  pendingInstall = null;
  installButton.hidden = true;
});
if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) {
  navigator.serviceWorker.register("/service-worker.js").catch(() => {});
}
