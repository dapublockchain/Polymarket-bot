"""
Candidate Selector for Tail Risk Underwriting Strategy.

This module identifies markets that are suitable for tail risk underwriting.
"""
from decimal import Decimal
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from loguru import logger


class TailRiskCategory(str, Enum):
    """Categories of tail risk events."""
    GEOPOLITICAL = "geopolitical"  # Wars, conflicts
    ECONOMIC = "economic"  # Market crashes, depressions
    TECHNOLOGY = "technology"  # AI breakthroughs, failures
    ENVIRONMENTAL = "environmental"  # Natural disasters, climate
    SOCIAL = "social"  # Elections, referendums
    BLACK_SWAN = "black_swan"  # Unpredictable rare events


@dataclass
class TailRiskCandidate:
    """A market that is a candidate for tail risk underwriting.

    Attributes:
        market_id: Market identifier
        question: Market question
        category: Tail risk category
        yes_price: Current YES price
        no_price: Current NO price
        tail_probability: Estimated probability of tail event
        potential_payout: Potential payout if tail event occurs
        worst_case_loss: Worst case loss if tail event doesn't occur
        correlation_cluster: Cluster ID for correlated positions
        is_suitable: Whether this candidate is suitable
        disqualification_reason: Reason why not suitable (if any)
    """
    market_id: str
    question: str
    category: TailRiskCategory
    yes_price: Decimal
    no_price: Decimal
    tail_probability: float
    potential_payout: Decimal
    worst_case_loss: Decimal
    correlation_cluster: str
    is_suitable: bool
    disqualification_reason: Optional[str] = None


class CandidateSelector:
    """
    Selects candidates for tail risk underwriting.

    Key features:
    - Identifies low-probability, high-impact events
    - Categorizes by tail risk type
    - Assigns correlation clusters
    - Estimates tail probabilities
    """

    # Keywords for each tail risk category
    CATEGORY_KEYWORDS = {
        TailRiskCategory.GEOPOLITICAL: [
            "war", "conflict", "invasion", "attack", "military", "nuclear",
            "sanctions", "tension", "crisis", "border", "sovereignty",
        ],
        TailRiskCategory.ECONOMIC: [
            "crash", "recession", "depression", "default", "inflation",
            "deflation", "bear market", "bull market", "bubble", "collapse",
        ],
        TailRiskCategory.TECHNOLOGY: [
            "AI", "artificial intelligence", "AGI", "breakthrough",
            "computing", "quantum", "robot", "automation", "singularity",
        ],
        TailRiskCategory.ENVIRONMENTAL: [
            "climate", "disaster", "hurricane", "earthquake", "flood",
            "pandemic", "virus", "temperature", "emissions", "extinction",
        ],
        TailRiskCategory.SOCIAL: [
            "election", "referendum", "vote", "protest", "revolution",
            "government", "policy", "law", "regulation", "ban",
        ],
    }

    def __init__(
        self,
        min_tail_probability: float = 0.01,  # 1% minimum
        max_tail_probability: float = 0.20,  # 20% maximum
        min_payout_ratio: float = 10.0,  # 10x minimum payout
    ):
        """
        Initialize candidate selector.

        Args:
            min_tail_probability: Minimum tail probability (0-1)
            max_tail_probability: Maximum tail probability (0-1)
            min_payout_ratio: Minimum payout ratio (potential/loss)
        """
        self.min_tail_probability = min_tail_probability
        self.max_tail_probability = max_tail_probability
        self.min_payout_ratio = min_payout_ratio

    async def select_candidates(
        self,
        markets: List[Dict[str, Any]],
    ) -> List[TailRiskCandidate]:
        """
        Select tail risk candidates from a list of markets.

        Args:
            markets: List of market dictionaries with:
                - market_id: str
                - question: str
                - yes_price: Decimal
                - no_price: Decimal

        Returns:
            List of suitable tail risk candidates
        """
        candidates = []

        for market in markets:
            candidate = await self._evaluate_market(market)
            if candidate and candidate.is_suitable:
                candidates.append(candidate)

        logger.info(f"Selected {len(candidates)} tail risk candidates from {len(markets)} markets")
        return candidates

    async def _evaluate_market(
        self,
        market: Dict[str, Any],
    ) -> Optional[TailRiskCandidate]:
        """
        Evaluate a market for tail risk suitability.

        Args:
            market: Market dictionary

        Returns:
            TailRiskCandidate if suitable, None otherwise
        """
        market_id = market.get("market_id")
        question = market.get("question", "")
        yes_price = Decimal(str(market.get("yes_price", "0")))
        no_price = Decimal(str(market.get("no_price", "0")))

        # Skip if prices are invalid
        if yes_price <= 0 or no_price <= 0 or yes_price >= 1 or no_price >= 1:
            return None

        # Determine category
        category = self._categorize_market(question)

        # Estimate tail probability
        # Tail probability is the lower of yes/no prices (whichever represents the tail event)
        # We assume the tail event is the outcome with lower probability
        tail_probability = min(float(yes_price), float(no_price))

        # Check if probability is in tail range
        if not (self.min_tail_probability <= tail_probability <= self.max_tail_probability):
            return None

        # Determine potential payout and worst case loss
        # If we bet on the tail event (low probability outcome):
        # - Potential payout = (1 / price) - 1 (as multiple of stake)
        # - Worst case loss = stake (if tail event doesn't occur)

        if yes_price < no_price:
            # YES is the tail event
            potential_payout = (Decimal("1") / yes_price) - Decimal("1")
            worst_case_loss = Decimal("1")  # Loss of stake
            tail_event = "YES"
        else:
            # NO is the tail event
            potential_payout = (Decimal("1") / no_price) - Decimal("1")
            worst_case_loss = Decimal("1")
            tail_event = "NO"

        # Calculate payout ratio
        payout_ratio = float(potential_payout) / float(worst_case_loss)

        # Check minimum payout ratio
        if payout_ratio < self.min_payout_ratio:
            return None

        # Assign correlation cluster
        # Use category as base cluster
        correlation_cluster = f"{category.value}_{self._extract_cluster_key(question)}"

        # All checks passed
        candidate = TailRiskCandidate(
            market_id=market_id,
            question=question,
            category=category,
            yes_price=yes_price,
            no_price=no_price,
            tail_probability=tail_probability,
            potential_payout=potential_payout,
            worst_case_loss=worst_case_loss,
            correlation_cluster=correlation_cluster,
            is_suitable=True,
        )

        logger.debug(
            f"Tail risk candidate: {market_id} - {category.value}, "
            f"prob={tail_probability:.3f}, payout={payout_ratio:.1f}x"
        )

        return candidate

    def _categorize_market(self, question: str) -> TailRiskCategory:
        """
        Categorize a market into tail risk type.

        Args:
            question: Market question

        Returns:
            TailRiskCategory
        """
        question_lower = question.lower()

        # Count keyword matches for each category
        category_scores = {}
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in question_lower)
            category_scores[category] = score

        # Find category with most matches
        max_score = max(category_scores.values())

        if max_score == 0:
            return TailRiskCategory.BLACK_SWAN

        # Return category with highest score
        for category, score in category_scores.items():
            if score == max_score:
                return category

        return TailRiskCategory.BLACK_SWAN

    def _extract_cluster_key(self, question: str) -> str:
        """
        Extract a cluster key from the question.

        Groups similar events together (e.g., all US elections together).

        Args:
            question: Market question

        Returns:
            Cluster key string
        """
        question_lower = question.lower()

        # Simple clustering based on common themes
        if "us" in question_lower or "united states" in question_lower:
            return "us"
        elif "china" in question_lower or "chinese" in question_lower:
            return "china"
        elif "europe" in question_lower or "eu" in question_lower:
            return "europe"
        elif "russia" in question_lower or "ukraine" in question_lower:
            return "russia-ukraine"
        elif "ai" in question_lower or "artificial intelligence" in question_lower:
            return "ai"
        elif "climate" in question_lower:
            return "climate"
        elif "election" in question_lower:
            return "elections"
        else:
            return "other"
