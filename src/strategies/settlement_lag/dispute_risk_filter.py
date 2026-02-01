"""
Dispute Risk Filter for Settlement Lag Strategy.

This module evaluates the risk of market disputes based on public information.
"""
from decimal import Decimal
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from loguru import logger


class DisputeRiskLevel(str, Enum):
    """Dispute risk levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class DisputeRiskAssessment:
    """Assessment of dispute risk for a market.

    Attributes:
        market_id: Market identifier
        risk_score: Overall risk score (0-1, higher = riskier)
        risk_level: Categorical risk level
        dispute_keywords: List of dispute-related keywords found
        volatility_contribution: Volatility component of risk score
        uncertainty_contribution: Uncertainty component of risk score
        is_acceptable: Whether risk is acceptable for trading
        reason: Explanation of the assessment
    """
    market_id: str
    risk_score: float
    risk_level: DisputeRiskLevel
    dispute_keywords: List[str]
    volatility_contribution: float
    uncertainty_contribution: float
    is_acceptable: bool
    reason: str


class DisputeRiskFilter:
    """
    Filters markets based on dispute risk.

    Uses publicly available information to estimate dispute probability:
    - Market title/question text analysis
    - Volatility patterns
    - Resolution uncertainty
    """

    # Keywords that may indicate higher dispute risk
    HIGH_RISK_KEYWORDS = [
        "subjective",
        "interpretation",
        "opinion",
        "judgment",
        "discretion",
        "may",
        "might",
        "could",
        "undefined",
        "unclear",
        "ambiguous",
        "controversial",
        "debate",
        "disagreement",
        "definition",
        "determine",
    ]

    MEDIUM_RISK_KEYWORDS = [
        "approximately",
        "around",
        "roughly",
        "estimate",
        "projection",
        "forecast",
        "prediction",
        "expect",
        "likely",
        "probable",
    ]

    def __init__(
        self,
        max_risk_score: float = 0.3,
        max_volatility_contribution: float = 0.5,
    ):
        """
        Initialize dispute risk filter.

        Args:
            max_risk_score: Maximum acceptable risk score (0-1)
            max_volatility_contribution: Max allowed volatility contribution
        """
        self.max_risk_score = max_risk_score
        self.max_volatility_contribution = max_volatility_contribution

    async def assess_dispute_risk(
        self,
        market_id: str,
        question: str,
        volatility_score: float,
        resolution_uncertainty: float = 0.0,
        end_date: Optional[Any] = None,
    ) -> DisputeRiskAssessment:
        """
        Assess dispute risk for a market.

        Args:
            market_id: Market identifier
            question: Market question text
            volatility_score: Market volatility score (0-1)
            resolution_uncertainty: Resolution uncertainty score (0-1)
            end_date: Optional market end date

        Returns:
            DisputeRiskAssessment with detailed risk analysis
        """
        # Analyze question for risk keywords
        keywords_found, keyword_risk = self._analyze_question(question)

        # Calculate volatility contribution (capped at max)
        volatility_contrib = min(volatility_score, self.max_volatility_contribution)

        # Calculate uncertainty contribution
        uncertainty_contrib = resolution_uncertainty * (1 - volatility_contrib)

        # Calculate total risk score
        risk_score = (keyword_risk * 0.5) + (volatility_contrib * 0.3) + (uncertainty_contrib * 0.2)

        # Determine risk level
        risk_level = self._categorize_risk(risk_score)

        # Check if acceptable
        is_acceptable = risk_score <= self.max_risk_score

        # Generate reason
        if is_acceptable:
            reason = (
                f"Dispute risk acceptable: {risk_score:.2f} <= {self.max_risk_score}. "
                f"Keywords: {len(keywords_found)}, Volatility: {volatility_contrib:.2f}"
            )
        else:
            reason = (
                f"Dispute risk too high: {risk_score:.2f} > {self.max_risk_score}. "
                f"Keywords: {len(keywords_found)}, Volatility: {volatility_contrib:.2f}, "
                f"Uncertainty: {uncertainty_contrib:.2f}"
            )

        assessment = DisputeRiskAssessment(
            market_id=market_id,
            risk_score=risk_score,
            risk_level=risk_level,
            dispute_keywords=keywords_found,
            volatility_contribution=volatility_contrib,
            uncertainty_contribution=uncertainty_contrib,
            is_acceptable=is_acceptable,
            reason=reason,
        )

        if is_acceptable:
            logger.info(f"Market {market_id} passed dispute risk filter: {risk_score:.2f}")
        else:
            logger.warning(f"Market {market_id} failed dispute risk filter: {risk_score:.2f}")

        return assessment

    def _analyze_question(self, question: str) -> tuple[List[str], float]:
        """
        Analyze question text for risk keywords.

        Args:
            question: Market question text

        Returns:
            Tuple of (list_of_keywords_found, risk_score_0_to_1)
        """
        if not question:
            return [], 0.0

        question_lower = question.lower()
        keywords_found = []

        # Check for high-risk keywords
        for keyword in self.HIGH_RISK_KEYWORDS:
            if keyword in question_lower:
                keywords_found.append(f"HIGH:{keyword}")

        # Check for medium-risk keywords
        for keyword in self.MEDIUM_RISK_KEYWORDS:
            if keyword in question_lower:
                keywords_found.append(f"MED:{keyword}")

        # Calculate risk score based on keywords found
        # High-risk keywords contribute more
        high_risk_count = sum(1 for k in keywords_found if k.startswith("HIGH:"))
        medium_risk_count = sum(1 for k in keywords_found if k.startswith("MED:"))

        # Score calculation:
        # Each high-risk keyword: 0.15
        # Each medium-risk keyword: 0.05
        # Cap at 1.0
        keyword_risk = min((high_risk_count * 0.15) + (medium_risk_count * 0.05), 1.0)

        return keywords_found, keyword_risk

    def _categorize_risk(self, risk_score: float) -> DisputeRiskLevel:
        """
        Categorize risk score into discrete levels.

        Args:
            risk_score: Risk score (0-1)

        Returns:
            DisputeRiskLevel category
        """
        if risk_score <= 0.1:
            return DisputeRiskLevel.LOW
        elif risk_score <= 0.3:
            return DisputeRiskLevel.MEDIUM
        elif risk_score <= 0.6:
            return DisputeRiskLevel.HIGH
        else:
            return DisputeRiskLevel.EXTREME


def assess_dispute_risk_sync(
    filter_instance: DisputeRiskFilter,
    market_id: str,
    question: str,
    volatility_score: float,
    resolution_uncertainty: float = 0.0,
) -> DisputeRiskAssessment:
    """
    Synchronous wrapper for dispute risk assessment.

    Useful for testing and non-async contexts.

    Args:
        filter_instance: DisputeRiskFilter instance
        market_id: Market identifier
        question: Market question text
        volatility_score: Market volatility score
        resolution_uncertainty: Resolution uncertainty score

    Returns:
        DisputeRiskAssessment
    """
    import asyncio

    # Create event loop if needed
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(
        filter_instance.assess_dispute_risk(
            market_id=market_id,
            question=question,
            volatility_score=volatility_score,
            resolution_uncertainty=resolution_uncertainty,
        )
    )
