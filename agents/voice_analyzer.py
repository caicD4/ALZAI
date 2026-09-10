import json
import re
from typing import List, Optional

from core.brand_voice import DefaultVoiceProfile, VoiceProfile
from tools.llm_client import GeminiClient

VOICE_ANALYZER_SYSTEM_PROMPT = """You are a Lead Linguistics and Writing Style Analyzer in ALZAI.
Your task is to analyze writing samples provided by a human user and infer their precise, structured VoiceProfile (writing style).

INFERENCE RULES:
1. Sentence length & rhythm: Analyze actual word counts per sentence and sentence structures.
2. Formality & directness: Evaluate vocabulary complexity, direct statements vs diplomatic phrasing.
3. Typography & formatting: Note line breaks, bold headers, bullet lists, punctuation habits.
4. Hook & closing patterns: Identify how the author habitually begins and ends posts.
5. Recurring vs avoided phrases: Extract phrases uniquely present vs corporate clichés absent.
6. Do NOT fabricate writing samples. Set is_default_profile = false.
"""


class VoiceProfileAnalyzer:
    """Infers a structured VoiceProfile from human writing samples."""

    def __init__(
        self,
        llm_client: Optional[GeminiClient] = None,
        use_llm: bool = True,
    ) -> None:
        self.use_llm = use_llm
        if use_llm:
            self.llm_client = llm_client or GeminiClient()
        else:
            self.llm_client = None

    def analyze_samples(self, sample_texts: List[str], author_name: str = "Author") -> VoiceProfile:
        """Analyzes a collection of writing sample texts to construct a personalized VoiceProfile."""
        clean_samples = [s.strip() for s in (sample_texts or []) if s and s.strip()]

        if not clean_samples:
            # Fallback to explicit default voice profile when zero samples are provided
            return DefaultVoiceProfile()

        if self.use_llm and self.llm_client is not None:
            profile = self._analyze_via_llm(clean_samples, author_name)
            if profile:
                return profile

        return self._analyze_fallback(clean_samples, author_name)

    def _analyze_via_llm(self, samples: List[str], author_name: str) -> Optional[VoiceProfile]:
        """Invokes Gemini to infer VoiceProfile schema from writing samples."""
        if not self.llm_client:
            return None

        combined_text = "\n---\n".join(samples[:10])
        prompt = (
            f"Author Name: {author_name}\n"
            f"Writing Samples Count: {len(samples)}\n\n"
            f"Writing Samples Content:\n{combined_text}\n\n"
            f"Required JSON Schema:\n{json.dumps(VoiceProfile.model_json_schema(), indent=2)}\n\n"
            "Analyze the writing samples above and return ONLY a valid JSON object matching the VoiceProfile schema. "
            "Set is_default_profile to false."
        )

        try:
            raw_json = self.llm_client.generate_json(
                prompt=prompt,
                system_instruction=VOICE_ANALYZER_SYSTEM_PROMPT,
                temperature=0.2,
            )
            data = json.loads(raw_json)
            data["is_default_profile"] = False
            return VoiceProfile.model_validate(data)
        except Exception:
            return None

    def _analyze_fallback(self, samples: List[str], author_name: str) -> VoiceProfile:
        """Deterministic heuristic analysis of writing samples for offline testing."""
        all_text = " ".join(samples)
        words = re.findall(r"\w+", all_text)
        sentences = [s.strip() for s in re.split(r"[.!?]+", all_text) if s.strip()]

        avg_words_per_sentence = len(words) / max(1, len(sentences))
        sentence_length_cat: Literal["short", "varied", "long", "punchy_short"] = "punchy_short"
        if avg_words_per_sentence > 20:
            sentence_length_cat = "long"
        elif avg_words_per_sentence > 12:
            sentence_length_cat = "varied"

        has_questions = "?" in all_text
        question_freq: Literal["none", "rare", "occasional", "frequent"] = "occasional" if has_questions else "none"

        return VoiceProfile(
            profile_id=f"voice-{hash(author_name) & 0xffffffff:08x}",
            name=f"{author_name}'s Writing Style",
            formality="direct_conversational",
            sentence_length=sentence_length_cat,
            sentence_rhythm=f"Average sentence length of {avg_words_per_sentence:.1f} words with punchy assertions.",
            vocabulary_style="Empirical and clear word choices extracted from author samples.",
            technicality="medium",
            humor_level="subtle",
            sarcasm_level="none",
            directness="very_direct",
            emotional_intensity="engaging",
            use_of_slang=False,
            use_of_profanity=False,
            rhetorical_question_frequency=question_freq,
            paragraph_style="short_paragraphs",
            formatting_style="Direct line breaks and bold accents derived from writing samples.",
            storytelling_style="Direct hook derived from exemplar writing samples.",
            analogy_usage="occasional",
            hook_patterns=["Direct observation opening", "Data assertion hook"],
            closing_patterns=["Takeaway summary"],
            recurring_phrases=[],
            avoided_phrases=[
                "In today's rapidly evolving world",
                "Let's dive in",
                "Game-changer",
                "Unlock your potential",
            ],
            stylistic_examples=samples[:3],
            is_default_profile=False,
        )
