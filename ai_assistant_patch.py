"""Small Groq-powered AI assistant for the PDFMaster Pro landing page."""

import json
import os
import urllib.error
import urllib.request

from flask import jsonify, request


GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def make_ai_ask_view():
    def ai_ask():
        payload = request.get_json(silent=True) or {}
        question = str(payload.get("question", "") or "").strip()
        if not question:
            return jsonify({"success": False, "error": "Please enter a question."}), 400
        if len(question) > 2000:
            return jsonify({"success": False, "error": "Please keep your question under 2,000 characters."}), 400

        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            return jsonify({"success": False, "error": "AI Assistant is not configured yet."}), 503

        body = {
            "model": DEFAULT_GROQ_MODEL,
            "temperature": 0.35,
            "max_tokens": 700,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the built-in AI assistant for PDFMaster Pro. Answer general user questions clearly and concisely. "
                        "You can also explain PDF tasks and recommend which PDFMaster Pro tool to use. "
                        "Do not claim to have inspected a user's files unless file content was actually provided to you. "
                        "For medical, legal, financial, or other high-stakes topics, provide general information and encourage appropriate professional verification."
                    ),
                },
                {"role": "user", "content": question},
            ],
        }

        req = urllib.request.Request(
            GROQ_CHAT_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "PDFMaster-Pro/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                return jsonify({"success": False, "error": "AI service is busy. Please try again shortly."}), 429
            return jsonify({"success": False, "error": "AI service is temporarily unavailable."}), 502
        except (urllib.error.URLError, TimeoutError):
            return jsonify({"success": False, "error": "Unable to reach the AI service right now."}), 502
        except Exception:
            return jsonify({"success": False, "error": "AI Assistant could not answer this question."}), 500

        answer = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not answer:
            return jsonify({"success": False, "error": "AI Assistant returned an empty response."}), 502

        return jsonify({"success": True, "answer": answer})

    return ai_ask
