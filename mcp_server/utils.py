
"""
utils.py - Utility functions for MCP server and agent processing.

These helpers are used across:
- MCP server (ID + timestamps)
- Agent flow (HTML cleaning + summarization)
"""

import uuid
from datetime import datetime, timezone
import re
import html


def generate_id() -> str:
    """
    Generate a unique identifier.

    Used for:
    - Notes
    - Tasks
    Ensures no collision in storage.
    """
    return str(uuid.uuid4())


def format_timestamp() -> str:
    """
    Return current timestamp in ISO 8601 format (UTC).

    Used for:
    - created_at
    - updated_at
    - completed_at
    """
    return datetime.now(timezone.utc).isoformat()


def extract_text_from_html(html_content: str) -> str:
    """
    Convert raw HTML into clean readable text.

    Removes:
    - <script> and <style>
    - HTML tags
    - comments
    - encoded entities

    Used AFTER fetch_url tool
    BEFORE saving notes or summarizing.
    """

    if not html_content or not isinstance(html_content, str):
        return ""

    html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)

    text = re.sub(r'<[^>]+>', '', html_content)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def truncate_text(text: str, max_length: int = 2000) -> str:
    """
    Truncate text safely without breaking words.

    Used for:
    - summarizing fetched content
    - limiting note size

    Ensures:
    - clean output
    - avoids mid-word cuts
    """

    if not text or not isinstance(text, str):
        return ""

    if len(text) <= max_length:
        return text

    truncated = text[:max_length]

    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]

    return truncated + "..."

