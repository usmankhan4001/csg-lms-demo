"""Turning poll answers into percentages.

The one rule that matters here: a poll nobody has answered has NO
percentages, not 0%. These are classes full of children and the number is
often read as "how the class did" -- printing 0% for every option of a poll
that was never answered states a result that did not happen. A count of zero
is a fact; a share of zero answers is not.

Kept separate from the router so the rule is testable without a database.
"""

from dataclasses import dataclass
from typing import Dict, Mapping, Optional


@dataclass(frozen=True)
class PollTally:
    """The answer counts for one poll, and what may be said about them."""

    total_responses: int
    # Empty when `total_responses` is 0 -- see the module docstring. Callers
    # must read it with `.get()`, never `[]`.
    percentages: Dict[int, float]

    def percentage_for(self, option_id: int) -> Optional[float]:
        """This option's share of the answers, or None if there are none.

        None means "no percentage exists", which is not the same as 0.0.
        """
        return self.percentages.get(option_id)


def tally_poll(counts: Mapping[int, int]) -> PollTally:
    """Percentages per option id, rounded to one decimal place.

    With no answers at all this returns an empty mapping rather than a
    mapping of zeroes.
    """
    total = sum(counts.values())
    if total == 0:
        return PollTally(total_responses=0, percentages={})
    return PollTally(
        total_responses=total,
        percentages={
            option_id: round(count * 100.0 / total, 1)
            for option_id, count in counts.items()
        },
    )
