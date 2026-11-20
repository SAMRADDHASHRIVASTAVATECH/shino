"""LM Studio local API client for Nova.

Chat model (Nemotron) drives conversation. Vision model (Qwen multimodal)
answers "what's on the screen". All calls are local to 127.0.0.1:1234.

Nothing here ever returns a model's hidden reasoning. Only final answer text
is allowed to reach the visible chat, so Nova never "thinks out loud".
"""
import base64
import io
import json
import re
import urllib.request
import urllib.error

API = "http://127.0.0.1:1234/v1"
CHAT_MODEL = "nvidia/nemotron-3-nano-4b"
# Instruct model with no chain-of-thought. Used only when Nemotron burns its
# whole token budget on hidden reasoning and leaves `content` empty.
FALLBACK_MODEL = "olmoe-1b-7b-0125-instruct"

# This directive is what actually stops the leak. `chat_template_kwargs.
# enable_thinking` is NOT reliably honoured by every LM Studio model build.
FINAL_ONLY = (
    "OUTPUT RULES: Reply with ONLY your final answer, as the character you are "
    "playing. Never reveal reasoning, analysis, planning, meta-commentary, or "
    "quoted instructions. Do not narrate what you are doing. Just the answer text."
)

# If a model slips reasoning into `content`, catch it here rather than show it.
_LEAK = re.compile(
    r"(?im)^\s*(we need to|we are|we have|we must|the user (asks|says|wants|provided)|"
    r"i (must|need to|should|am an ai|am a language model)|as an ai|"
    r"so\s*:?\s*$|note\s*:|remember\s*:|analysis\s*:|reasoning\s*:|"
    r"thought process\s*:|let me (think|analyze)|output rules|system prompt|"
    r"instructions\s*:)"
)


def _post(path, payload, timeout=120):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def available():
    try:
        with urllib.request.urlopen(API + "/models", timeout=4) as resp:
            json.loads(resp.read().decode("utf-8"))
        return True
    except Exception:
        return False


def _clean(text):
    """Return only real answer text; drop reasoning-shaped output."""
    t = (text or "").strip()
    if not t:
        return ""
    m = _LEAK.search(t)
    if not m:
        return t
    # A reasoning block sometimes ends with the answer in quotes — keep only that.
    quoted = re.findall(r'"([^"\n]{2,300})"', t[m.start():])
    return quoted[-1].strip() if quoted else ""


def _content(result):
    """Extract visible answer. NEVER falls back to reasoning_content."""
    try:
        msg = result["choices"][0]["message"]
    except (KeyError, IndexError):
        return ""
    return _clean(msg.get("content") or "")


def _call(messages, model, max_tokens, temperature, timeout=120, think=False):
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if think:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    return _content(_post("/chat/completions", payload, timeout=timeout))


def _guarded(messages):
    msgs = list(messages)
    if msgs and msgs[0].get("role") == "system":
        msgs = [{"role": "system",
                 "content": FINAL_ONLY + "\n" + str(msgs[0].get("content", ""))}] + msgs[1:]
    else:
        msgs = [{"role": "system", "content": FINAL_ONLY}] + msgs
    return msgs


def chat(messages, model=CHAT_MODEL, max_tokens=220, temperature=0.8):
    """Conversation reply: final text only, never inner reasoning."""
    msgs = _guarded(messages)
    text = ""
    try:
        # Generous budget: Nemotron reasons internally even when told not to,
        # so the real answer needs room after that hidden reasoning.
        text = _call(msgs, model, max(360, int(max_tokens)), temperature,
                     think=True)
    except Exception:
        pass
    if not text and model != FALLBACK_MODEL:
        try:
            text = _call(msgs, FALLBACK_MODEL, max(220, int(max_tokens)),
                         temperature, timeout=60)
        except Exception:
            pass
    return text or "(no response)"


def describe_image(pil_image, question, model="qwen3.5-0.8b", max_tokens=300):
    """Send a PIL image to the multimodal model; return the visible answer."""
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    messages = [
        {"role": "system", "content": FINAL_ONLY},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url",
                 "image_url": {"url": "data:image/png;base64," + b64}},
            ],
        },
    ]
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max(400, int(max_tokens)),
        "temperature": 0.5,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    try:
        return _content(_post("/chat/completions", payload, timeout=150)) or "(no response)"
    except Exception:
        return "(no response)"


def classify_tone(text, model=CHAT_MODEL):
    """Ask the model which expression Nova should show. Returns a short token."""
    prompt = (
        "Classify the emotion of this message into exactly one word: "
        "happy, sad, angry, surprised, thinking, or neutral. Reply with only that word.\n\n"
        "Message: " + text[:400]
    )
    raw = chat([{"role": "user", "content": prompt}],
               model=model, max_tokens=12, temperature=0).strip().lower()
    for word in ("happy", "sad", "angry", "surprised", "thinking", "neutral"):
        if word in raw:
            return word
    return "neutral"


if __name__ == "__main__":
    print("LM Studio available:", available())
    print(chat([{"role": "user", "content": "Say hi in one word."}]))
