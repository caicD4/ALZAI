from typing import Dict, List, Optional, Union
from core.brand_voice import BrandProfile, DefaultVoiceProfile, VoiceProfile
from core.bundle_schemas import ContentBundle, ContentPiece
from core.format_specs import FORMAT_CATALOG, ContentFormatSpec
from core.synthesis import ContentStrategy, ResearchBrief
from agents.content_quality import ContentQualityEngine
from agents.format_planner import MultiFormatPlanner
from agents.multiformat_writer import MultiFormatContentWriter
from agents.outliner import ContentOutliner
from agents.revision import TargetedRevisionWorker
from tools.llm_client import GeminiClient


class MultiFormatContentEngine:
    """Orchestrates multi-format content generation, quality auditing, and revision directly from a ResearchBrief."""

    def __init__(
        self,
        llm_client: Optional[GeminiClient] = None,
        use_llm: bool = True,
        max_revisions: int = 2,
    ) -> None:
        self.use_llm = use_llm
        self.max_revisions = max_revisions
        if use_llm:
            self.llm_client = llm_client or GeminiClient()
        else:
            self.llm_client = None

        self.planner = MultiFormatPlanner(llm_client=self.llm_client, use_llm=use_llm)
        self.outliner = ContentOutliner(llm_client=self.llm_client, use_llm=use_llm)
        self.writer = MultiFormatContentWriter(llm_client=self.llm_client, use_llm=use_llm)
        self.quality_engine = ContentQualityEngine(llm_client=self.llm_client, use_llm=use_llm)
        self.revision_worker = TargetedRevisionWorker(llm_client=self.llm_client, use_llm=use_llm, max_revisions=max_revisions)

    def generate_bundle(
        self,
        brief: ResearchBrief,
        base_strategy: ContentStrategy,
        formats: Optional[List[str]] = None,
        brand: Optional[BrandProfile] = None,
        voice: Optional[VoiceProfile] = None,
    ) -> ContentBundle:
        """Generates a ContentBundle containing platform-adapted, quality-audited ContentPiece assets for requested formats."""
        target_voice = voice or DefaultVoiceProfile()
        target_brand = brand or BrandProfile()

        # Resolve requested format list
        requested_formats = formats or ["linkedin"]
        if "all" in [f.lower() for f in requested_formats]:
            target_format_ids = list(FORMAT_CATALOG.keys())
        else:
            target_format_ids = [f.lower() for f in requested_formats if f.lower() in FORMAT_CATALOG]
            if not target_format_ids:
                target_format_ids = ["linkedin"]

        pieces: Dict[str, ContentPiece] = {}

        for fid in target_format_ids:
            spec = FORMAT_CATALOG[fid]
            piece = self.generate_single_format(brief, base_strategy, spec, target_brand, target_voice)
            pieces[fid] = piece

        bundle_id = f"bundle-{hash(brief.brief_id + ''.join(target_format_ids)) & 0xffffffff:08x}"
        return ContentBundle(
            bundle_id=bundle_id,
            brief_id=brief.brief_id,
            topic=brief.topic,
            source_strategy=base_strategy,
            pieces=pieces,
        )

    def generate_single_format(
        self,
        brief: ResearchBrief,
        base_strategy: ContentStrategy,
        spec: ContentFormatSpec,
        brand: Optional[BrandProfile] = None,
        voice: Optional[VoiceProfile] = None,
    ) -> ContentPiece:
        """Generates, audits, and revises a single format asset directly from the ResearchBrief."""
        target_voice = voice or DefaultVoiceProfile()
        target_brand = brand or BrandProfile()

        # 1. Format-specific Strategy & Outline
        format_strat = self.planner.plan_format(brief, base_strategy, spec, target_brand, target_voice)
        outline = self.outliner.create_format_outline(brief, format_strat, spec, target_brand, target_voice)

        # 2. Write initial draft piece directly from ResearchBrief
        initial_piece = self.writer.write_format(brief, format_strat, outline, spec, target_brand, target_voice)

        # Wrap in DraftContent for Quality Engine evaluation
        draft_wrapper = self._piece_to_draft(initial_piece)

        # 3. Audit via ContentQualityEngine
        quality_report = self.quality_engine.evaluate_quality(
            draft_wrapper, brief, base_strategy, outline=outline, brand=target_brand, voice=target_voice
        )

        final_piece = initial_piece
        final_report = quality_report

        # 4. Targeted Revision if needed
        if quality_report.overall_status != "passed":
            revised_draft, history = self.revision_worker.execute_targeted_quality_revision(
                draft_wrapper, quality_report, brief, base_strategy, outline=outline, brand=target_brand, voice=target_voice, quality_engine=self.quality_engine
            )
            final_report = self.quality_engine.evaluate_quality(
                revised_draft, brief, base_strategy, outline=outline, brand=target_brand, voice=target_voice
            )
            final_piece = self._draft_to_piece(revised_draft, initial_piece, final_report)
        else:
            final_piece.quality_report = quality_report

        return final_piece

    @staticmethod
    def _piece_to_draft(piece: ContentPiece) -> any:
        from core.brand_voice import DraftContent
        return DraftContent(
            draft_id=piece.content_id,
            topic=piece.title or "Untitled",
            platform=piece.platform,
            title=piece.title,
            body_text=piece.body_text,
            outline_id="out-fmt",
            brief_id=piece.brief_id or "brief-fmt",
            word_count=piece.word_count,
            version=piece.version,
        )

    @staticmethod
    def _draft_to_piece(draft: any, original_piece: ContentPiece, report: any) -> ContentPiece:
        sections = [s.strip() for s in draft.body_text.split("\n\n") if s.strip()]
        return ContentPiece(
            content_id=original_piece.content_id,
            format_id=original_piece.format_id,
            platform=original_piece.platform,
            title=draft.title or original_piece.title,
            body_text=draft.body_text,
            sections=sections,
            word_count=len(draft.body_text.split()),
            estimated_duration=original_piece.estimated_duration,
            brief_id=original_piece.brief_id,
            version=draft.version,
            quality_report=report,
        )
