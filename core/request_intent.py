import json
import re
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

from tools.llm_client import GeminiClient

IntentType = Literal[
    "topic_request",
    "question",
    "claim_investigation",
    "comparison",
    "explanation",
    "argument",
    "opinion",
    "how_to",
    "prediction",
    "critique",
    "content_request",
    "unknown",
]


class UserRequest(BaseModel):
    """Raw incoming user request representation."""

    raw_prompt: str = Field(..., description="Raw unmodified prompt typed by user")
    requested_format: str = Field(default="all", description="Target format or 'all'")
    explicit_constraints: List[str] = Field(
        default_factory=list, description="Any explicit constraints requested by user"
    )


class RequestIntent(BaseModel):
    """Semantic representation of user intent prior to research planning.

    USER FRAMING IS CREATIVE DIRECTION. A user saying "why Sam Altman is evil"
    is asking for critical/opinion content about Sam Altman — NOT asking ALZAI to
    adjudicate objective metaphysical truth. The stance, content intent, and
    research direction all follow from what content the user wants.
    """

    subject: str = Field(..., description="Main subject/entity of interest (e.g. 'Sam Altman', 'Mixture of Experts')")
    task: str = Field(..., description="Actionable task ALZAI should perform (e.g. 'Write critical analysis of Sam Altman')")
    proposition: Optional[str] = Field(
        default=None, description="User's framing/assertion if present (e.g. 'Sam Altman is secretly evil'). Treated as creative direction, not a truth claim to adjudicate."
    )
    question: Optional[str] = Field(
        default=None, description="Explicit or implied guiding question if present"
    )
    desired_content_type: str = Field(
        default="analysis", description="Targeted content type (e.g. 'critical_opinion', 'explanation', 'analysis', 'guide', 'debate')"
    )
    stance: str = Field(
        default="explanatory", description="Framing or stance for the content (e.g. 'critical', 'opinion', 'explanatory', 'balanced')"
    )
    intent_type: IntentType = Field(
        ..., description="Categorized intent type"
    )
    key_entities: List[str] = Field(
        default_factory=list, description="Extracted key entities (people, products, organizations)"
    )
    key_concepts: List[str] = Field(
        default_factory=list, description="Extracted domain concepts and technical terms"
    )
    research_goal: str = Field(
        ..., description="Objective research goal driving research planning (e.g. 'Evaluate evidence for, against, and complicating the proposition')"
    )
    ambiguity: Optional[str] = Field(
        default=None, description="Any identified ambiguity or underspecified elements"
    )
    safety_context_notes: Optional[str] = Field(
        default=None, description="Contextual notes regarding sensitive or controversial subjects"
    )


REQUEST_INTERPRETER_SYSTEM_PROMPT = """You are ALZAI's Request Understanding interpreter.
Your job is to analyze messy human requests and extract a clear, structured RequestIntent object BEFORE research planning.

CRITICAL PRINCIPLE — USER FRAMING IS CREATIVE DIRECTION:
1. The user's input tells you WHAT CONTENT they want, not necessarily a truth claim to adjudicate.
   - "why elon musk sucks" = the user wants critical content about Elon Musk. NOT "determine whether Elon Musk sucks."
   - "Sam Altman is secretly evil" = critical/opinion content about Sam Altman.
   - "remote work kills productivity" = debate/opinion content arguing the case against remote work.
   - "explain mixture of experts" = technical explanation content.
   - "write a viral LinkedIn post about remote work" = content creation request, needs topic + landscape + angle research.
2. For critical requests:
   - Extract the CLEAN entity/subject (e.g. "Elon Musk", "Sam Altman", "Tesla", "Remote Work"). NEVER include "sucks", "is bad", or "why" inside the subject string.
   - Set proposition to the user's framing.
   - Set stance to "critical" and desired_content_type to "critical_opinion".
   - Set research direction to gather documented criticisms, controversies, arguments, counterarguments, and context — the RAW MATERIAL for compelling critical content.
3. Normal factual accuracy still applies: no fabricated facts, stats, quotes, or sources. But content creation is never blocked on "insufficient evidence".

CLASSIFY INTENT TYPES:
- "topic_request": Simple topic without specific question ("multi-agent orchestration").
- "question": Direct question ("Why are AI agents moving toward multi-agent architectures?").
- "claim_investigation"/"critique": Assertive/opinionated framing requiring argument & counterargument research ("remote work kills productivity", "why elon musk sucks").
- "comparison": Comparing two or more items ("Compare Claude and Gemini for coding").
- "explanation": Request to explain how something works ("Explain mixture of experts").
- "how_to": Actionable instructional query ("How do I build an autonomous Discord moderator?").
- "content_request": Explicit content-creation ask ("write me a linkedin post about...", "give me a viral post about remote work").

DO NOT FABRICATE OR OVER-ENGINEER. Output valid JSON strictly adhering to schema.
"""


class RequestInterpreter:
    """Interprets raw user prompts into structured RequestIntent objects."""

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

    def interpret(self, request: UserRequest) -> RequestIntent:
        """Interprets a UserRequest into a validated RequestIntent."""
        raw = request.raw_prompt.strip()
        if not raw:
            raise ValueError("User request prompt cannot be empty.")

        if self.use_llm and self.llm_client:
            try:
                intent = self._interpret_via_llm(request)
                if intent:
                    return intent
            except Exception as err:
                print(f"[Notice] LLM RequestInterpreter failed ({err}); using deterministic fallback.")

        return self._interpret_fallback(request)

    def _interpret_via_llm(self, request: UserRequest) -> Optional[RequestIntent]:
        if not self.llm_client:
            return None

        schema = RequestIntent.model_json_schema()
        prompt = (
            f"User Raw Prompt: \"{request.raw_prompt}\"\n"
            f"Requested Format: {request.requested_format}\n"
            f"Explicit Constraints: {', '.join(request.explicit_constraints) if request.explicit_constraints else 'None'}\n\n"
            f"Required JSON Schema:\n{json.dumps(schema, indent=2)}\n\n"
            "Respond ONLY with the valid JSON RequestIntent object:"
        )

        try:
            raw_json = self.llm_client.generate_json(
                prompt=prompt,
                system_instruction=REQUEST_INTERPRETER_SYSTEM_PROMPT,
                temperature=0.1,
                stage_label="RequestIntent",
            )
            data = json.loads(raw_json)
            return RequestIntent.model_validate(data)
        except Exception:
            return None

    def _interpret_fallback(self, request: UserRequest) -> RequestIntent:
        """Robust deterministic rule-based fallback interpreter."""
        raw = request.raw_prompt.strip()
        # Strip meta-prompts like "write me a linkedin post on..."
        clean_raw = re.sub(
            r"^(?:write\s+(?:me\s+)?(?:a\s+)?(?:linkedin\s+post|article|x\s+thread|newsletter|script|post)?\s+(?:on|about)\s+)",
            "",
            raw,
            flags=re.IGNORECASE,
        ).strip()
        lower = clean_raw.lower()

        def _clean_subject(s: str) -> str:
            s_clean = s.strip(" ?.")
            if not s_clean:
                return s_clean
            # If string is all lowercase, capitalize words cleanly
            if s_clean.islower():
                return " ".join([w.capitalize() if w not in {"in", "on", "at", "for", "to", "of", "and", "or", "with"} else w for w in s_clean.split()])
            return s_clean

        claim_triggers = (
            "sucks", "suck", "is bad", "are bad", "is terrible", "is shady", "is overrated",
            "are overrated", "is a scam", "kills", "is fake", "is lying", "is evil",
            "is secretly", "struggle", "fail", "failed", "overpriced", "useless",
            "can actually", "can be increased", "struggle with", "is agi", "is real"
        )

        # 0. Content creation request check (e.g. "write me a linkedin post on X")
        content_req = re.search(
            r"^(?:write\s+(?:me\s+)?(?:a\s+)?(?:\w+\s+)*(?:linkedin\s+post|article|x\s+thread|newsletter|script|viral\s+post|post|thread)\s+(?:on|about)\s+)",
            raw,
            flags=re.IGNORECASE,
        )
        is_content_request = bool(content_req) or lower.startswith(("give me a viral", "make a post", "create a post", "turn into"))

        # 1. Claim investigation / critique check
        is_claim_investigation = any(w in lower for w in claim_triggers)
        pred_match = re.search(r"^(.+?)\s+(is|are|will|can|has|causes|destroys|replaces)\s+(.+)$", clean_raw, re.IGNORECASE)
        if pred_match and not is_claim_investigation and not lower.startswith(("why", "how", "what", "compare", "explain")):
            is_claim_investigation = True

        if is_content_request:
            intent_type: IntentType = "content_request"
            subject_candidate = re.sub(
                r"^(?:write\s+(?:me\s+)?(?:a\s+)?(?:\w+\s+)*(?:linkedin\s+post|article|x\s+thread|newsletter|script|viral\s+post|post|thread)\s+(?:on|about)\s+)",
                "",
                raw,
                flags=re.IGNORECASE,
            ).strip(" ?.")
            subject = _clean_subject(subject_candidate)
            proposition = None
            task = f"Create compelling content about {subject}"
            research_goal = f"Research the topic '{subject}', the existing conversation/landscape, audience arguments, hooks, and content gaps to create standout content"
            question = f"What is the current conversation, landscape, and key angles for content about {subject}?"
            desired_content_type = "platform_post"

        elif is_claim_investigation:
            intent_type: IntentType = "critique"

            # Cleanly extract subject entity
            subject_candidate = clean_raw
            if pred_match and not lower.startswith("why"):
                subject_candidate = pred_match.group(1)
            else:
                subject_candidate = re.sub(r"^(why|why does|why do|why is|why are|how|how can)\s+", "", subject_candidate, flags=re.IGNORECASE)
                for kw in ("sucks", "suck", "is bad", "are bad", "is terrible", "is shady", "is overrated", "are overrated", "is a scam", "kills productivity", "kills", "is fake", "is lying", "is evil", "is secretly evil", "overpriced", "useless", "can actually be increased", "can actually", "can be increased", "is agi"):
                    pattern = re.compile(rf"\s+{re.escape(kw)}.*$", re.IGNORECASE)
                    subject_candidate = pattern.sub("", subject_candidate)
                    pattern_is = re.compile(rf"^(.+?)\s+(?:is|can)\s+{re.escape(kw)}.*$", re.IGNORECASE)
                    m = pattern_is.match(subject_candidate)
                    if m:
                        subject_candidate = m.group(1)

            subject = _clean_subject(subject_candidate) if subject_candidate else clean_raw

            proposition = clean_raw
            task = f"Create compelling critical content about: '{clean_raw}'"
            research_goal = f"Gather documented criticisms, controversies, arguments, counterarguments, and context regarding {subject} as raw material for critical content"
            question = f"What documented criticisms, controversies, and arguments form the basis for critical content about {subject}?"
            desired_content_type = "critical_opinion"
            stance = "critical"

        elif lower.startswith("explain ") or lower.startswith("what is ") or lower.startswith("how does "):
            intent_type = "explanation"
            subject = _clean_subject(re.sub(r"^(explain|what is|how does)\s+", "", clean_raw, flags=re.IGNORECASE))
            task = f"Explain the principles, architecture, and mechanisms of {subject}"
            research_goal = f"Investigate key mechanisms, components, and practical implications of {subject}"
            proposition = None
            question = clean_raw if clean_raw.endswith("?") else f"How does {subject} work?"
            desired_content_type = "explanation"

        elif lower.startswith("compare ") or " vs " in lower or " versus " in lower:
            intent_type = "comparison"
            subject = _clean_subject(clean_raw.replace("Compare ", "").replace("compare ", ""))
            task = f"Compare and contrast the components of {subject}"
            research_goal = f"Evaluate key tradeoffs, performance, and use cases across {subject}"
            proposition = None
            question = clean_raw
            desired_content_type = "comparison"

        elif lower.startswith("how to ") or lower.startswith("how do i ") or lower.startswith("how can i "):
            intent_type = "how_to"
            subject = _clean_subject(re.sub(r"^(how to|how do i|how can i)\s+", "", clean_raw, flags=re.IGNORECASE))
            task = f"Provide a step-by-step practical guide on how to {subject}"
            research_goal = f"Gather practical steps, best practices, and code/workflow requirements for {subject}"
            proposition = None
            question = clean_raw
            desired_content_type = "guide"

        elif lower.startswith("why ") or lower.startswith("what ") or clean_raw.endswith("?"):
            intent_type = "question"
            if " from " in clean_raw and " to " in clean_raw:
                parts = clean_raw.split(" from ")[0]
                subject = _clean_subject(re.sub(r"^(why|why are|why do|why does|what|what are)\s+(?:the\s+)?", "", parts, flags=re.IGNORECASE))
            else:
                subject = _clean_subject(re.sub(r"^(why|why are|why do|why does|what|what are|is|can|does)\s+(?:the\s+)?", "", clean_raw, flags=re.IGNORECASE))
            
            subject = re.sub(r"\s+(?:are|is)\s+shifting$", "", subject, flags=re.IGNORECASE).strip()
            task = f"Answer and analyze the question: {clean_raw}"
            research_goal = f"Investigate reasons, evidence, and architectural drivers answering '{clean_raw}'"
            proposition = None
            question = clean_raw
            desired_content_type = "analysis"

        else:
            intent_type = "topic_request"
            subject = _clean_subject(clean_raw)
            task = f"Explore foundational concepts, key trends, and practical insights on {subject}"
            research_goal = f"Gather core concepts, verifiable evidence, and strategic insights regarding {subject}"
            proposition = None
            question = f"What are the core principles and developments in {subject}?"
            desired_content_type = "overview"

        # Extract entities and key concepts
        words = [w for w in re.findall(r"\b[A-Za-z0-9\'-]+\b", clean_raw) if len(w) > 2]
        entities = [w for w in words if w[0].isupper()]
        concepts = [w.lower() for w in words if w.lower() not in {"why", "how", "what", "is", "are", "the", "and", "for", "with", "from", "about"}]

        stance_value = "critical" if intent_type in ("critique", "claim_investigation") else ("opinion" if intent_type == "content_request" else "explanatory")

        return RequestIntent(
            subject=subject or clean_raw,
            task=task,
            proposition=proposition,
            question=question,
            desired_content_type=desired_content_type,
            stance=stance_value,
            intent_type=intent_type,
            key_entities=entities or [subject],
            key_concepts=concepts[:5],
            research_goal=research_goal,
        )
