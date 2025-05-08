#chatbot/services/rag/fallback_classifier.py
import logging
import re
from typing import Dict, Any, Tuple, List

logger = logging.getLogger(__name__)


class TherapyClassifier:
    """Rule-based classifier for determining appropriate therapy approach."""

    # Keywords and phrases associated with each therapy type
    CBT_INDICATORS = [
        r"negative thought",
        r"cognitive distortion",
        r"catastrophiz(e|ing)",
        r"black and white thinking",
        r"all-or-nothing",
        r"should statements",
        r"automatic thought",
        r"challenge belief",
        r"reframe",
        r"thought record",
        r"evidence for",
        r"evidence against",
        r"logical error",
        r"cognitive restructuring",
        r"depression",
        r"anxiety disorder",
        r"phobia",
        r"obsessive",
        r"compulsive",
        r"social anxiety",
        r"generalized anxiety",
        r"panic attack",
        r"perfectionism",
    ]

    DBT_INDICATORS = [
        r"emotion(al)? regulation",
        r"mindfulness",
        r"distress tolerance",
        r"interpersonal effectiveness",
        r"dialectical",
        r"borderline",
        r"suicidal",
        r"self-harm",
        r"impulsive",
        r"intense emotion",
        r"emotional sensitivity",
        r"validation",
        r"radical acceptance",
        r"wise mind",
        r"self-soothe",
        r"dbt skills",
        r"opposite action",
        r"urge surfing",
        r"emotional vulnerability",
        r"identity confusion",
        r"emptiness",
        r"abandonment",
    ]

    # Mental health issues commonly treated with each therapy
    CBT_CONDITIONS = [
        r"depression",
        r"anxiety",
        r"panic disorder",
        r"phobia",
        r"social anxiety",
        r"ocd",
        r"ptsd",
        r"insomnia",
        r"stress",
        r"anger issues",
        r"low self-esteem",
    ]

    DBT_CONDITIONS = [
        r"borderline personality disorder",
        r"bpd",
        r"emotional dysregulation",
        r"self-harm",
        r"suicidal thoughts",
        r"suicidal ideation",
        r"substance abuse",
        r"eating disorder",
        r"bulimia",
        r"anorexia",
        r"bipolar",
    ]

    def classify(self, text: str) -> Tuple[str, float, Dict[str, Any]]:
        """Classify text to determine most appropriate therapy approach.

        Args:
            text: User query or description

        Returns:
            Tuple of (recommended_therapy_type, confidence_score, explanation)
        """
        text = text.lower()

        # Count matches for each therapy type
        cbt_score = self._count_matches(text, self.CBT_INDICATORS)
        cbt_condition_score = (
            self._count_matches(text, self.CBT_CONDITIONS) * 1.5
        )  # Weight conditions higher

        dbt_score = self._count_matches(text, self.DBT_INDICATORS)
        dbt_condition_score = (
            self._count_matches(text, self.DBT_CONDITIONS) * 1.5
        )  # Weight conditions higher

        # Calculate total scores
        total_cbt = cbt_score + cbt_condition_score
        total_dbt = dbt_score + dbt_condition_score

        # Get matched terms for explanation
        cbt_matches = self._get_matches(text, self.CBT_INDICATORS + self.CBT_CONDITIONS)
        dbt_matches = self._get_matches(text, self.DBT_INDICATORS + self.DBT_CONDITIONS)

        # Determine confidence (normalized to 0-1)
        max_score = max(total_cbt, total_dbt)
        min_score = min(total_cbt, total_dbt)
        score_diff = max_score - min_score

        # Default confidence calculation
        base_confidence = min(0.5 + (score_diff * 0.1), 0.95)  # Cap at 0.95

        # If both scores are low, reduce confidence
        if max_score < 1:
            base_confidence = max(0.3, base_confidence - 0.2)

        # If both scores are equal, use 0.5 confidence
        if total_cbt == total_dbt:
            recommended = "cbt" if len(cbt_matches) >= len(dbt_matches) else "dbt"
            confidence = 0.5
        elif total_cbt > total_dbt:
            recommended = "cbt"
            confidence = base_confidence
        else:
            recommended = "dbt"
            confidence = base_confidence

        explanation = {
            "cbt_score": total_cbt,
            "dbt_score": total_dbt,
            "cbt_matches": cbt_matches,
            "dbt_matches": dbt_matches,
            "reason": f"Selected {recommended.upper()} based on keyword matching with confidence {confidence:.2f}",
        }

        return recommended, confidence, explanation

    def _count_matches(self, text: str, patterns: List[str]) -> int:
        """Count regex matches in text.

        Args:
            text: Text to search
            patterns: List of regex patterns

        Returns:
            Number of matches found
        """
        count = 0
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            count += len(matches)
        return count

    def _get_matches(self, text: str, patterns: List[str]) -> List[str]:
        """Get actual matched terms.

        Args:
            text: Text to search
            patterns: List of regex patterns

        Returns:
            List of matched terms
        """
        matches = []
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matches.append(match.group(0))
        return matches


# Create instance
therapy_classifier = TherapyClassifier()
