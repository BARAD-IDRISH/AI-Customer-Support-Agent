
import logging
import os
import secrets
from uuid import uuid4

from flask import Flask, jsonify, render_template, request, session
from werkzeug.exceptions import RequestEntityTooLarge

from app.agent import chat


app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static",
)

app.config["MAX_CONTENT_LENGTH"] = 16 * 1024  # 16 KB request limit
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)

logger = logging.getLogger(__name__)


@app.get("/")
def index():
    """Render the customer-support chat interface."""
    if "request_id" not in session:
        session["request_id"] = str(uuid4())

    return render_template("index.html")


@app.post("/api/chat")
def chat_endpoint():
    """Receive a message and return the AI agent's response."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Send a valid JSON object."}), 400

    message = data.get("message")

    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Please enter a message."}), 400

    if len(message) > 4000:
        return jsonify({"error": "Message must be 4000 characters or fewer."}), 400

    # Keep one request ID for this browser session.
    # The frontend can reuse it if the request needs to be retried.
    request_id = session.get("request_id")

    if not request_id:
        request_id = str(uuid4())
        session["request_id"] = request_id

    try:
        answer = chat(message.strip(), request_id=request_id)

        # Rotate the request ID after a successful response.
        # Do not rotate it for a rate-limit response, so a retry
        # can reuse the same idempotency key.
        if "temporarily rate-limited" not in answer.lower():
            session["request_id"] = str(uuid4())

        return jsonify({"reply": answer})

    except Exception:
        logger.exception("Flask chat endpoint failed")
        return jsonify({
            "error": "Something went wrong. Please try again."
        }), 500


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    return jsonify({"error": "Request is too large."}), 413


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)
