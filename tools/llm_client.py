import json
import re
import time
from typing import Any, Dict, Optional
from google import genai
from google.genai import types

from config.gemini_config import get_gemini_api_key
from tools.execution_trace import (
    FailureCategory,
    classify_exception,
    get_trace,
)

PLANNER_SYSTEM_PROMPT = """You are an expert AI Research Planner.
Your task is to create a comprehensive, structured research plan for a given user request.

System Guidelines:
1. Research Questions:
   - Generate between 5 and 8 specific, independently investigable research questions.
   - Questions must be distinct and non-redundant.
   - Each question must include a unique id (e.g. 'rq-1'), question text, rationale, priority (1=highest), and 2-3 search_queries.
2. Hypotheses:
   - Provide at least 2 hypotheses to test.
   - Hypotheses are propositions to be investigated and verified during research, NOT assumed facts.
3. Contrarian Probes:
   - Provide at least 2 contrarian probes.
   - Contrarian probes must challenge obvious assumptions and test alternative explanations.
4. Search Queries:
   - Generate practical search queries suitable for actual web research later.
5. Stopping Criteria:
   - Include max_iterations (bounded between 1 and 10), min_useful_evidence (minimum 1), and saturation_threshold (0.0 to 1.0).
6. Constraints:
   - Do NOT invent research findings or pretend you have already searched the web.
   - Output MUST be valid JSON strictly matching the requested schema.
"""


class GeminiClient:
    """Wrapper for Google Gemini API with execution tracing and structured failures."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-3.6-flash",
    ) -> None:
        self.model_name = model_name
        self._api_key = api_key

    def _get_client(self) -> genai.Client:
        key = self._api_key or get_gemini_api_key()
        return genai.Client(api_key=key)

    def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        stage_label: str = "",
    ) -> str:
        """Sends a prompt to Gemini, traces the call, returns raw cleaned JSON.

        Args:
            prompt: The full prompt text including user query and schema instructions.
            system_instruction: Optional system instruction for Gemini.
            temperature: Sampling temperature (default: 0.2 for low variance).
            stage_label: Pipeline stage name for trace (e.g. 'ResearchPlanner').

        Returns:
            Cleaned JSON string response from Gemini.

        Raises:
            Exception: Re-raises after recording trace with structured failure category.
        """
        client = self._get_client()

        config_args = {
            "response_mime_type": "application/json",
            "temperature": temperature,
        }
        if system_instruction:
            config_args["system_instruction"] = system_instruction

        t0 = time.monotonic()
        try:
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(**config_args),
            )

            if not response or not response.text:
                raise ValueError("Gemini API returned an empty or null response.")

            cleaned = self._clean_json_text(response.text)

            # Basic JSON structure validation
            try:
                json.loads(cleaned)
            except json.JSONDecodeError as je:
                raise ValueError(f"Response is not valid JSON: {je}") from je

            duration_ms = (time.monotonic() - t0) * 1000
            get_trace().record(
                stage=stage_label,
                method="generate_json",
                agent="GeminiClient",
                status="success",
                duration_ms=duration_ms,
            )
            return cleaned

        except Exception as exc:
            duration_ms = (time.monotonic() - t0) * 1000
            cat = classify_exception(exc)
            get_trace().record(
                stage=stage_label,
                method="generate_json",
                agent="GeminiClient",
                status="failure",
                duration_ms=duration_ms,
                error_message=str(exc)[:200],
                failure_category=cat,
            )
            raise

    def generate_json_plan(self, user_request: str, schema_dict: Dict[str, Any]) -> str:
        """Sends research prompt to Gemini and returns raw JSON text response.

        Args:
            user_request: The research topic or question from the user.
            schema_dict: JSON Schema dictionary for ResearchPlan validation.

        Returns:
            Cleaned JSON string response from Gemini.
        """
        prompt = (
            f"User Research Request: {user_request}\n\n"
            f"Required JSON Schema:\n{json.dumps(schema_dict, indent=2)}\n\n"
            "Respond ONLY with the JSON ResearchPlan object:"
        )

        return self.generate_json(
            prompt=prompt,
            system_instruction=PLANNER_SYSTEM_PROMPT,
            temperature=0.2,
            stage_label="ResearchPlanner",
        )

    @staticmethod
    def _clean_json_text(text: str) -> str:
        """Strips markdown code fences from JSON output if present."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
        return cleaned.strip()
