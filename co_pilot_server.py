import json
import os
import re
import socket
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Load env variables manually from .env if not present
def load_env_key():
    key = os.environ.get("NVIDIA_API_KEY")
    if not key:
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("NVIDIA_API_KEY="):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass
    return key

NVIDIA_API_KEY = load_env_key()

# HTML page template served to the phone
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Aegis Hands-Free Co-Pilot</title>
    <style>
        :root {
            --bg: #090d16;
            --card: #111827;
            --border: #1f2937;
            --text: #eceff1;
            --muted: #90a4ae;
            --red: #ff3344;
            --red-glow: rgba(255, 51, 68, 0.25);
            --teal: #00e5cc;
            --teal-glow: rgba(0, 229, 204, 0.25);
        }
        body {
            margin: 0;
            padding: 15px;
            background-color: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            -webkit-tap-highlight-color: transparent;
        }
        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 10px;
        }
        .title {
            font-weight: 700;
            color: var(--red);
            font-size: 18px;
            letter-spacing: 1px;
            text-transform: uppercase;
        }
        .status-badge {
            font-size: 11px;
            color: var(--muted);
            background: rgba(31, 41, 55, 0.5);
            padding: 4px 10px;
            border-radius: 12px;
            border: 1px solid var(--border);
            font-weight: 600;
        }
        .status-active {
            color: var(--teal);
            background: rgba(0, 229, 204, 0.1);
            border-color: rgba(0, 229, 204, 0.3);
            box-shadow: 0 0 8px var(--teal-glow);
        }
        .instructions {
            font-size: 12px;
            color: var(--muted);
            margin-bottom: 15px;
            line-height: 1.4;
            background: rgba(255,255,255,0.02);
            padding: 8px 12px;
            border-radius: 6px;
            border-left: 3px solid var(--red);
        }
        .input-group {
            position: relative;
            margin-bottom: 15px;
        }
        textarea {
            width: 100%;
            height: 100px;
            box-sizing: border-box;
            background-color: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            padding: 12px;
            font-size: 14px;
            resize: none;
            outline: none;
            transition: border-color 0.2s;
        }
        textarea:focus {
            border-color: var(--red);
            box-shadow: 0 0 10px var(--red-glow);
        }
        .btn-row {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        button {
            flex: 1;
            padding: 12px;
            font-size: 14px;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            outline: none;
            border: none;
            transition: opacity 0.2s;
        }
        button.start-btn {
            background-color: var(--teal);
            color: #000000;
        }
        button.stop-btn {
            background-color: #374151;
            color: white;
        }
        button.submit-btn {
            background-color: var(--red);
            color: white;
            flex: 1.5;
        }
        button:active {
            opacity: 0.8;
        }
        .answer-container {
            background-color: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 15px;
            min-height: 120px;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.3);
        }
        .answer-label {
            font-size: 11px;
            text-transform: uppercase;
            color: var(--muted);
            letter-spacing: 0.5px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
        }
        .answer-text {
            font-size: 16px;
            line-height: 1.5;
            color: #ffffff;
            white-space: pre-wrap;
        }
        .pulse-indicator {
            width: 8px;
            height: 8px;
            background-color: var(--teal);
            border-radius: 50%;
            display: inline-block;
            margin-right: 5px;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(1); opacity: 1; box-shadow: 0 0 0 0 rgba(0, 229, 204, 0.7); }
            70% { transform: scale(1.3); opacity: 0.5; box-shadow: 0 0 0 8px rgba(0, 229, 204, 0); }
            100% { transform: scale(1); opacity: 1; box-shadow: 0 0 0 0 rgba(0, 229, 204, 0); }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">Aegis Hands-Free</div>
        <div id="status-badge" class="status-badge">Microphone Offline</div>
    </div>

    <div class="instructions">
        <strong>Hands-Free Mode:</strong> Tap "Start Listening". The phone will record continuously. When you pause speaking for 2.5 seconds, it will automatically query the LLM and display the answer.
    </div>

    <div class="input-group">
        <textarea id="question" placeholder="Transcript of judge's question will appear here in real-time..."></textarea>
    </div>

    <div class="btn-row">
        <button id="toggle-btn" class="start-btn" onclick="toggleListening()">Start Listening</button>
        <button class="submit-btn" onclick="getAnswer()">Manual Submit</button>
    </div>

    <div class="answer-container">
        <div class="answer-label">
            <span id="ans-status">Live Output</span>
            <span id="listening-indicator" style="display:none;"><span class="pulse-indicator"></span>Listening...</span>
        </div>
        <div class="answer-text" id="answer">Tap Start to begin continuous Q&A monitoring.</div>
    </div>

    <script>
        let recognition;
        let isListening = false;
        let silenceTimer = null;
        let lastQuery = '';

        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechClass = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechClass();
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = 'en-US';

            recognition.onstart = () => {
                document.getElementById('status-badge').textContent = 'Continuous Active';
                document.getElementById('status-badge').classList.add('status-active');
                document.getElementById('listening-indicator').style.display = 'inline-flex';
                document.getElementById('toggle-btn').textContent = 'Stop Listening';
                document.getElementById('toggle-btn').className = 'stop-btn';
                isListening = true;
            };

            recognition.onend = () => {
                if (isListening) {
                    try {
                        recognition.start();
                    } catch(e) {}
                } else {
                    document.getElementById('status-badge').textContent = 'Microphone Offline';
                    document.getElementById('status-badge').classList.remove('status-active');
                    document.getElementById('listening-indicator').style.display = 'none';
                    document.getElementById('toggle-btn').textContent = 'Start Listening';
                    document.getElementById('toggle-btn').className = 'start-btn';
                }
            };

            recognition.onresult = (event) => {
                let currentTranscript = '';
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    currentTranscript += event.results[i][0].transcript;
                }

                if (currentTranscript.trim()) {
                    document.getElementById('question').value = currentTranscript;
                    
                    // Reset silence timer. If user pauses for 2.5 seconds, auto-submit
                    clearTimeout(silenceTimer);
                    silenceTimer = setTimeout(() => {
                        autoSubmit(currentTranscript.trim());
                    }, 2500);
                }
            };
        } else {
            alert('Speech Recognition is not supported on this browser. Please use Chrome on Android or Safari on iOS.');
        }

        function toggleListening() {
            if (!recognition) return;
            if (isListening) {
                isListening = false;
                recognition.stop();
            } else {
                recognition.start();
            }
        }

        function autoSubmit(queryText) {
            if (!queryText || queryText === lastQuery) return;
            lastQuery = queryText;
            getAnswer();
        }

        async function getAnswer() {
            const questionEl = document.getElementById('question');
            const ansEl = document.getElementById('answer');
            const ansStatusEl = document.getElementById('ans-status');
            const q = questionEl.value.trim();
            if (!q) return;

            ansEl.textContent = 'Generating answer...';
            ansStatusEl.textContent = 'Thinking...';

            try {
                const res = await fetch('/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question: q })
                });
                const data = await res.json();
                ansEl.textContent = data.answer || 'No response received.';
                ansStatusEl.textContent = 'Stressed Response (Ready)';
            } catch(e) {
                ansEl.textContent = 'Error: ' + e;
                ansStatusEl.textContent = 'Error';
            }
        }
    </script>
</body>
</html>
"""

class CoPilotHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/ask":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(body)
            question = payload.get("question", "").strip()

            if not question:
                ans = "Please specify a question."
            else:
                ans = self.call_nvidia_nim(question)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"answer": ans}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def call_nvidia_nim(self, question: str) -> str:
        if not NVIDIA_API_KEY:
            return "NVIDIA_API_KEY is missing. Add it to your .env file to enable LLM answers."

        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {NVIDIA_API_KEY}"
        }

        system_prompt = (
            "You are an expert Q&A assistant helping Moosa present 'Aegis Codex' to a panel of hackathon judges. "
            "The judges are asking Moosa a question. Provide a direct, professional, 2 to 3 sentence answer "
            "written in the first-person plural ('We', 'Our platform') that Moosa can read aloud directly from "
            "his phone screen. Use precise financial terms (DCF, WACC, WFW, EBITDA) and technical terms (OTel, "
            "spans, serverless, NIM, Tavily) terminology. Keep it extremely punchy and brief so he doesn't stall."
        )

        data = {
            "model": "meta/llama-3.3-70b-instruct",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            "temperature": 0.3,
            "max_tokens": 150
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                res_body = json.loads(response.read().decode("utf-8"))
                answer = res_body["choices"][0]["message"]["content"]
                return answer.strip()
        except Exception as e:
            return f"Error contacting LLM: {str(e)}"

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def run(port=8080):
    ip = get_local_ip()
    server_address = ('0.0.0.0', port)
    httpd = ThreadingHTTPServer(server_address, CoPilotHandler)
    print(f"\n========================================================")
    print(f" Aegis Hands-Free Co-Pilot Server is Active!")
    print(f" URL FOR YOUR MOBILE PHONE: http://{ip}:{port}")
    print(f" (Make sure both phone and laptop are on the same WiFi)")
    print(f"========================================================\n")
    print("Press Ctrl+C to stop the server.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Co-Pilot server.")
        httpd.server_close()

if __name__ == "__main__":
    run()
