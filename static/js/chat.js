
const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const messages = document.getElementById("messages");
const welcome = document.getElementById("welcome");
const sendButton = document.getElementById("send-button");
const charCount = document.getElementById("char-count");
const chatContent = document.querySelector(".chat-content");

let isSending = false;

// --------------------------------------------------
// Scroll chat to the latest message
// --------------------------------------------------

function scrollToBottom() {
    chatContent.scrollTop = chatContent.scrollHeight;
}

// --------------------------------------------------
// Safely render inline Markdown
// Supports bold, italic, and inline code.
// Uses DOM text nodes instead of inserting HTML.
// --------------------------------------------------

function appendInlineMarkdown(container, text) {
    const pattern = /(\*\*.+?\*\*|__.+?__|`[^`\n]+`|\*[^*\n]+\*|_[^_\n]+_)/g;

    let lastIndex = 0;
    let match;

    while ((match = pattern.exec(text)) !== null) {
        // Add normal text before the Markdown token.
        if (match.index > lastIndex) {
            container.appendChild(
                document.createTextNode(
                    text.slice(lastIndex, match.index)
                )
            );
        }

        const token = match[0];
        let element;
        let content;

        if (
            (token.startsWith("**") && token.endsWith("**")) ||
            (token.startsWith("__") && token.endsWith("__"))
        ) {
            element = document.createElement("strong");
            content = token.slice(2, -2);
        } else if (token.startsWith("`") && token.endsWith("`")) {
            element = document.createElement("code");
            content = token.slice(1, -1);
        } else {
            element = document.createElement("em");
            content = token.slice(1, -1);
        }

        element.textContent = content;
        container.appendChild(element);

        lastIndex = pattern.lastIndex;
    }

    // Add remaining normal text.
    if (lastIndex < text.length) {
        container.appendChild(
            document.createTextNode(text.slice(lastIndex))
        );
    }
}

// --------------------------------------------------
// Render Markdown blocks safely
// Supports paragraphs, bullet lists, numbered lists,
// headings, blockquotes, and horizontal rules.
// --------------------------------------------------

function renderMarkdown(container, text) {
    const lines = String(text ?? "").replace(/\r\n?/g, "\n").split("\n");

    let paragraphLines = [];
    let currentList = null;
    let currentListType = null;

    function flushParagraph() {
        if (paragraphLines.length === 0) {
            return;
        }

        const paragraph = document.createElement("p");

        paragraphLines.forEach((line, index) => {
            if (index > 0) {
                paragraph.appendChild(document.createElement("br"));
            }

            appendInlineMarkdown(paragraph, line);
        });

        container.appendChild(paragraph);
        paragraphLines = [];
    }

    function flushList() {
        if (currentList) {
            container.appendChild(currentList);
        }

        currentList = null;
        currentListType = null;
    }

    function addListItem(text, type) {
        flushParagraph();

        if (!currentList || currentListType !== type) {
            flushList();

            currentListType = type;
            currentList = document.createElement(
                type === "ordered" ? "ol" : "ul"
            );
        }

        const item = document.createElement("li");
        appendInlineMarkdown(item, text);

        currentList.appendChild(item);
    }

    for (const rawLine of lines) {
        const line = rawLine.trim();

        // Blank lines separate blocks.
        if (!line) {
            flushParagraph();
            flushList();
            continue;
        }

        // Markdown headings: # Heading, ## Heading, etc.
        const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);

        if (headingMatch) {
            flushParagraph();
            flushList();

            const level = headingMatch[1].length;
            const heading = document.createElement(`h${level}`);

            appendInlineMarkdown(heading, headingMatch[2]);
            container.appendChild(heading);
            continue;
        }

        // Horizontal rule.
        if (/^(---+|\*\*\*+|___+)$/.test(line)) {
            flushParagraph();
            flushList();
            container.appendChild(document.createElement("hr"));
            continue;
        }

        // Bullet lists: -, *, or +.
        const bulletMatch = line.match(/^[-*+]\s+(.+)$/);

        if (bulletMatch) {
            addListItem(bulletMatch[1], "unordered");
            continue;
        }

        // Numbered lists: 1. Item or 1) Item.
        const orderedMatch = line.match(/^\d+[.)]\s+(.+)$/);

        if (orderedMatch) {
            addListItem(orderedMatch[1], "ordered");
            continue;
        }

        // Blockquotes.
        const quoteMatch = line.match(/^>\s?(.*)$/);

        if (quoteMatch) {
            flushParagraph();
            flushList();

            const quote = document.createElement("blockquote");
            appendInlineMarkdown(quote, quoteMatch[1]);

            container.appendChild(quote);
            continue;
        }

        // Normal paragraph text.
        flushList();
        paragraphLines.push(line);
    }

    flushParagraph();
    flushList();
}

// --------------------------------------------------
// Add a message to the conversation
// --------------------------------------------------

function addMessage(text, sender, isError = false) {
    welcome.hidden = true;

    const row = document.createElement("div");
    row.className = `message-row ${sender}`;

    if (isError) {
        row.classList.add("error");
    }

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = sender === "user" ? "You" : "AI";
    avatar.setAttribute("aria-hidden", "true");

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    if (sender === "assistant") {
        renderMarkdown(bubble, text);
    } else {
        // User messages remain plain text.
        bubble.textContent = text;
    }

    if (sender === "user") {
        row.append(bubble, avatar);
    } else {
        row.append(avatar, bubble);
    }

    messages.appendChild(row);
    scrollToBottom();

    return row;
}

// --------------------------------------------------
// Loading state
// --------------------------------------------------

function setLoading(loading) {
    isSending = loading;
    sendButton.disabled = loading;
    input.disabled = loading;

    const buttonLabel = sendButton.querySelector("span:first-child");

    if (buttonLabel) {
        buttonLabel.textContent = loading ? "Sending..." : "Send";
    }
}

// --------------------------------------------------
// Send a message to Flask
// --------------------------------------------------

async function sendMessage(message) {
    const cleanMessage = message.trim();

    if (!cleanMessage || isSending) {
        return;
    }

    if (cleanMessage.length > 4000) {
        addMessage(
            "Your message must be 4000 characters or fewer.",
            "assistant",
            true
        );
        return;
    }

    addMessage(cleanMessage, "user");

    input.value = "";
    charCount.textContent = "0 / 4000";
    input.style.height = "auto";

    setLoading(true);

    // Build the typing indicator without HTML injection.
    const typingRow = document.createElement("div");
    typingRow.className = "message-row";

    const typingAvatar = document.createElement("div");
    typingAvatar.className = "message-avatar";
    typingAvatar.textContent = "AI";
    typingAvatar.setAttribute("aria-hidden", "true");

    const typingBubble = document.createElement("div");
    typingBubble.className = "message-bubble typing";
    typingBubble.textContent = "Thinking...";

    typingRow.append(typingAvatar, typingBubble);
    messages.appendChild(typingRow);

    scrollToBottom();

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: cleanMessage
            })
        });

        let data;

        try {
            data = await response.json();
        } catch {
            data = {};
        }

        typingRow.remove();

        if (!response.ok) {
            addMessage(
                data.error || "The request could not be completed.",
                "assistant",
                true
            );
        } else {
            addMessage(
                data.reply || "I couldn't generate a response.",
                "assistant"
            );
        }
    } catch (error) {
        typingRow.remove();

        console.error("Chat request failed:", error);

        addMessage(
            "Unable to connect to the support server. Check your connection and try again.",
            "assistant",
            true
        );
    } finally {
        setLoading(false);
        input.focus();
        scrollToBottom();
    }
}

// --------------------------------------------------
// Form submission
// --------------------------------------------------

form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage(input.value);
});

// --------------------------------------------------
// Character counter and automatic textarea resizing
// --------------------------------------------------

input.addEventListener("input", () => {
    charCount.textContent = `${input.value.length} / 4000`;

    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 130)}px`;
});

// --------------------------------------------------
// Enter to send; Shift + Enter for a new line
// --------------------------------------------------

input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
    }
});

// --------------------------------------------------
// Suggested prompt buttons
// --------------------------------------------------

document.querySelectorAll(".suggestion").forEach((button) => {
    button.addEventListener("click", () => {
        sendMessage(button.dataset.message || "");
    });
});
