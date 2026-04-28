#!/usr/bin/env python3
import http.server
import json
import os
import shutil
import subprocess
from pathlib import Path

PORT = 8080

SYSTEM_PROMPTS = {
    "behavioral": (
        "You are an expert interviewer specializing in behavioral interviews using the STAR method "
        "(Situation, Task, Action, Result). Generate or evaluate responses for behavioral questions "
        "focused on leadership, teamwork, conflict resolution, and problem-solving."
    ),
    "technical": (
        "You are an expert technical interviewer covering data structures, algorithms, system design, "
        "and coding. Generate or evaluate responses for software engineering technical interviews."
    ),
    "role": (
        "You are an expert interviewer for product management, design, and program management roles. "
        "Generate or evaluate responses for role-specific interviews covering product strategy, "
        "prioritization, stakeholder management, and cross-functional leadership."
    ),
}

QUESTION_PROMPTS = {
    "behavioral": (
        "Generate a single behavioral interview question using the STAR method format. "
        "Focus on one of: leadership, conflict, failure, teamwork, or impact. "
        "Output only the question, nothing else."
    ),
    "technical": (
        "Generate a single technical interview question. Vary between: coding problems (arrays, strings, "
        "trees, graphs, DP), system design (design a URL shortener, chat system, etc.), or CS concepts. "
        "Output only the question, nothing else."
    ),
    "role": (
        "Generate a single product/program management interview question. Vary between: product design, "
        "estimation, prioritization, metrics, or strategy questions. "
        "Output only the question, nothing else."
    ),
}


def find_claude():
    claude = shutil.which("claude")
    if claude:
        return claude
    candidates = [
        "/opt/homebrew/bin/claude",
        "/usr/local/bin/claude",
        str(Path.home() / ".local/bin/claude"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    raise RuntimeError("claude CLI not found. Make sure `claude` is in your PATH.")


def call_claude(system: str, user: str) -> str:
    claude_bin = find_claude()
    prompt = f"{system}\n\n{user}"
    result = subprocess.run(
        [claude_bin, "-p", prompt],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip() or "claude CLI returned non-zero exit code"
        raise RuntimeError(err)
    return result.stdout.strip()


class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")

    def send_json(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            html = (Path(__file__).parent / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))

        try:
            if self.path == "/api/question":
                category = body.get("category", "behavioral")
                history = body.get("history", [])
                history_note = ""
                if history:
                    prev = "\n".join(f"- {q}" for q in history)
                    history_note = f"\n\nAlready asked these questions — do NOT repeat them:\n{prev}"
                prompt = QUESTION_PROMPTS[category] + history_note
                question = call_claude(SYSTEM_PROMPTS[category], prompt)
                self.send_json(200, {"question": question.strip()})

            elif self.path == "/api/evaluate":
                category = body.get("category", "behavioral")
                question = body.get("question", "")
                answer = body.get("answer", "")
                prompt = (
                    f"Interview question: {question}\n\n"
                    f"Candidate's answer: {answer}\n\n"
                    "Evaluate this answer. Respond with a JSON object (and nothing else) with these keys:\n"
                    '  "score": integer 1-10\n'
                    '  "strengths": list of 2-3 short strings\n'
                    '  "improvements": list of 2-3 short strings\n'
                    '  "idealAnswer": a concise example of a strong answer (2-4 sentences)\n'
                    "Output raw JSON only, no markdown fences."
                )
                raw = call_claude(SYSTEM_PROMPTS[category], prompt)
                feedback = json.loads(raw)
                self.send_json(200, feedback)
            else:
                self.send_error(404)

        except Exception as e:
            import traceback; traceback.print_exc()
            self.send_json(500, {"error": str(e)})


if __name__ == "__main__":
    server = http.server.HTTPServer(("", PORT), Handler)
    print(f"Interview Prep running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop.\n")
    server.serve_forever()
