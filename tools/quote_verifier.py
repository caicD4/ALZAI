import re
import string


class QuoteVerifier:
    """Deterministic Quote Containment Checker.

    Verifies whether an extracted verbatim quote exists within the source snapshot text.
    Uses exact matching, normalized matching (whitespace/case/quotes), and punctuation-insensitive matching.
    """

    @classmethod
    def verify(
        cls,
        verbatim_quote: str,
        source_text: str,
    ) -> bool:
        """Determines if verbatim_quote is contained in source_text.

        Args:
            verbatim_quote: The extracted quote to verify.
            source_text: The full cleaned text of the source snapshot.

        Returns:
            True if quote is verified to exist in source_text, False otherwise.
        """
        if not verbatim_quote or not source_text:
            return False

        quote = verbatim_quote.strip()
        text = source_text.strip()

        if not quote or not text:
            return False

        # Level 1: Exact Substring Match
        if quote in text:
            return True

        # Level 2: Whitespace, Quotes & Case Normalization
        norm_quote = cls._normalize_text(quote)
        norm_text = cls._normalize_text(text)

        if norm_quote in norm_text:
            return True

        # Level 3: Punctuation-Insensitive Match
        clean_quote = cls._strip_punctuation(norm_quote)
        clean_text = cls._strip_punctuation(norm_text)

        if clean_quote and clean_quote in clean_text:
            return True

        return False

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalizes quotes, case, and collapses whitespace."""
        # Replace smart / curly quotes with straight quotes
        text = text.replace("“", '"').replace("”", '"')
        text = text.replace("‘", "'").replace("’", "'")
        text = text.replace("—", "-").replace("–", "-")

        # Collapse whitespace & lowercase
        text = re.sub(r"\s+", " ", text).strip().lower()
        return text

    @staticmethod
    def _strip_punctuation(text: str) -> str:
        """Removes punctuation for fallback matching."""
        translator = str.maketrans("", "", string.punctuation)
        return text.translate(translator)


def verify_quote(verbatim_quote: str, source_text: str) -> bool:
    """Helper function to run QuoteVerifier."""
    return QuoteVerifier.verify(verbatim_quote, source_text)
