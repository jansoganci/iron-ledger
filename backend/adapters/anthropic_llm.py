from __future__ import annotations

import json
import subprocess
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import anthropic
from pydantic import BaseModel

from backend.domain.errors import TransientIOError
from backend.logger import get_logger

logger = get_logger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(filename: str) -> str:
    path = _PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def _json_default(obj: object) -> str:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _git_sha(filename: str) -> str:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", f"backend/prompts/{filename}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


class AnthropicLLMClient:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)

    def call(
        self,
        prompt: str,
        model: str,
        context: dict,
        schema: type[BaseModel],
    ) -> BaseModel:
        """Load *prompt* by filename, send to *model* with *context*, parse into *schema*."""
        prompt_text = _load_prompt(prompt)
        sha = _git_sha(prompt)
        logger.info(
            "llm_call start",
            extra={"prompt_file": prompt, "prompt_sha": sha, "model": model},
        )

        try:
            message = self._client.messages.create(
                model=model,
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": f"{prompt_text}\n\nInput:\n{json.dumps(context, default=_json_default)}",
                    }
                ],
            )
        except anthropic.APIConnectionError as exc:
            raise TransientIOError(f"Anthropic connection error: {exc}") from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                raise TransientIOError(f"Anthropic {exc.status_code}: {exc}") from exc
            raise

        raw = message.content[0].text
        logger.info(
            "llm_call complete",
            extra={
                "prompt_file": prompt,
                "model": model,
                "stop_reason": message.stop_reason,
            },
        )

        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text[: text.rfind("```")]

        parsed = json.loads(text)
        return schema.model_validate(parsed)
