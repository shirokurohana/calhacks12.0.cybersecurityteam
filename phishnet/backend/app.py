# Can rename to main.py if preferred 
# There's Flask backend starter / skeleton code in ChatGPT if needed or desired (Ctrl/Cmd + F 'main.py')

import os
import json
import random
import time
from flask import Flask, jsonify, send_from_directory
import requests

app = Flask(__name__, static_folder='static')

# Load static emails as a fallback and seed dataset
STATIC_EMAIL_PATH = 'static_emails.json'
with open(STATIC_EMAIL_PATH, 'r') as f:
    STATIC_EMAILS = json.load(f)

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')  # set this in Replit env

# Anthropic endpoint (HTTP-based). If your account uses a different
# endpoint or path, replace this with the endpoint provided in your console.
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/complete"

# Simple cache to reduce API calls during demos (optional)
GENERATED_CACHE = []
CACHE_TTL = 60 * 5  # seconds
LAST_CACHE_TIME = 0

def build_generation_prompt(phish_probability=0.5):
    """
    Compose a system + user prompt that instructs Claude to return a strict JSON object.
    We ask for either a phishing or legitimate email depending on random choice.
    """
    kind = "phishing" if random.random() < phish_probability else "legitimate"
    # You can rotate themes or include more specificity here
    theme = random.choice([
        "bank account alert",
        "password reset",
        "university announcement",
        "package delivery",
        "payroll / HR",
        "social media notification"
    ])

    # We instruct the model to return strict JSON with these fields only.
    prompt = (
        f"You are generating short email examples for a cybersecurity education app. "
        f"Return exactly one JSON object (no surrounding text or commentary) with the following fields:\n"
        f"  - sender (string): the email sender address (e.g., support@bank.com)\n"
        f"  - subject (string)\n"
        f"  - body (string): the email body; keep it short (1-3 sentences)\n"
        f"  - is_phish (boolean): true if this is a phishing email, false if legitimate\n"
        f"  - why (string): one-line explanation of red flags or why it's safe\n\n"
        f"Generate a {kind} email about this theme: {theme}. Keep JSON valid and escape characters properly."
    )
    return prompt

def call_anthropic(prompt, max_tokens=300, temperature=0.6):
    """
    Send a request to Anthropic's API to generate content.
    Returns the raw text output (string) or raises an exception.
    """
    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY
    }

    payload = {
        "model": "claude-3.5-sonnet",  # change if you prefer another Anthropic model name
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature
    }

    resp = requests.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    # Anthropic responses can vary depending on API; adapt parsing as needed.
    # We try to find a text output field in likely locations.
    # Common fields: data['completion'] or data['completion']['output'] or data['choices'][0]['text']
    # We'll handle a few options defensively.
    text = None
    if 'completion' in data and isinstance(data['completion'], str):
        text = data['completion']
    elif 'choices' in data and isinstance(data['choices'], list) and len(data['choices']) > 0:
        # older/newer formats sometimes use choices[0].text or choices[0].message
        first = data['choices'][0]
        if isinstance(first, dict) and 'text' in first:
            text = first['text']
        elif isinstance(first, dict) and 'message' in first:
            # message might be dict with 'content' keys depending on API shape
            msg = first['message']
            if isinstance(msg, str):
                text = msg
            elif isinstance(msg, dict):
                # some formats: message: {"content": [{"type":"output_text","text": "..."}]}
                if 'content' in msg:
                    content = msg['content']
                    if isinstance(content, str):
                        text = content
                    elif isinstance(content, list) and len(content) > 0 and isinstance(content[0], dict):
                        text = content[0].get('text')
    elif 'text' in data:
        text = data['text']

    if text is None:
        # fallback: return raw JSON as string
        return json.dumps(data)

    return text

def parse_json_from_model(raw_text):
    """
    Try to extract a JSON object from the model output and parse it.
    If parsing fails, return None.
    """
    # Some models accidentally add backticks or triple quotes — try to extract {...}
    start = raw_text.find('{')
    end = raw_text.rfind('}')
    if start == -1 or end == -1 or end <= start:
        return None
    json_str = raw_text[start:end+1]

    try:
        parsed = json.loads(json_str)
        # Basic validation - ensure required keys exist
        if all(k in parsed for k in ("sender", "subject", "body", "is_phish", "why")):
            # sanitize types
            parsed['is_phish'] = bool(parsed['is_phish'])
            parsed['sender'] = str(parsed['sender'])
            parsed['subject'] = str(parsed['subject'])
            parsed['body'] = str(parsed['body'])
            parsed['why'] = str(parsed['why'])
            return parsed
    except Exception:
        return None
    return None

@app.route('/')
def serve_index():
    return send_from_directory('frontend', 'index.html')

@app.route('/api/email')
def get_email():
    """
    Primary endpoint for frontend.
    Returns a JSON object with fields:
      sender, subject, body, is_phish (bool), why
    This will try to use a cached generated email set, then call Anthropic, then fall back to static.
    """
    global LAST_CACHE_TIME, GENERATED_CACHE

    # Use cache if fresh
    now = time.time()
    if GENERATED_CACHE and (now - LAST_CACHE_TIME) < CACHE_TTL:
        return jsonify(random.choice(GENERATED_CACHE))

    # If no API key or empty, immediately return a static email
    if not ANTHROPIC_API_KEY:
        return jsonify(random.choice(STATIC_EMAILS))

    prompt = build_generation_prompt(phish_probability=0.5)

    try:
        raw = call_anthropic(prompt)
        parsed = parse_json_from_model(raw)
        if parsed:
            # store into cache and return
            GENERATED_CACHE.append(parsed)
            LAST_CACHE_TIME = now
            return jsonify(parsed)
        else:
            # If parsing failed, attempt to wrap the raw text safely into a returned object
            fallback = {
                "sender": "no-reply@example.com",
                "subject": "Generated Example (unstructured)",
                "body": raw,
                "is_phish": False,
                "why": "Model did not return strict JSON. This is a fallback."
            }
            return jsonify(fallback)
    except Exception as e:
        # On any error, return a random static email (ensures demo reliability)
        print("Anthropic call failed:", e)
        return jsonify(random.choice(STATIC_EMAILS))


if __name__ == '__main__':
    # For Replit/hosting: bind 0.0.0.0 and port from env if provided
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)