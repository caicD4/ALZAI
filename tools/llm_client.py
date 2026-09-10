import json
import re
from typing import Any, Dict, Optional
from google import genai
from google.genai import types

from config.gemini_config import get_gemini_api_key

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
    """Simple wrapper for Google Gemini API for research planning."""

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

    def generate_json_plan(self, user_request: str, schema_dict: Dict[str, Any]) -> str:
        """Sends research prompt to Gemini and returns raw JSON text response.

        Args:
            user_request: The research topic or question from the user.
            schema_dict: JSON Schema dictionary for ResearchPlan validation.

        Returns:
            Cleaned JSON string response from Gemini.
        """
        client = self._get_client()

        prompt = (
            f"{PLANNER_SYSTEM_PROMPT}\n\n"
            f"User Research Request: {user_request}\n\n"
            f"Required JSON Schema:\n{json.dumps(schema_dict, indent=2)}\n\n"
            "Respond ONLY with the JSON ResearchPlan object:"
        )

        response = client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )

        if not response or not response.text:
            raise ValueError("Gemini API returned an empty or null response.")

        return self._clean_json_text(response.text)

    @staticmethod
    def _clean_json_text(text: str) -> str:
        """Strips markdown code fences from JSON output if present."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
        return cleaned.strip()
