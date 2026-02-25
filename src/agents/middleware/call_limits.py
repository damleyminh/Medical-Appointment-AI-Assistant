"""
CallLimitMiddleware — enforces a hard cap on the number of LLM calls
within a single workflow run to prevent runaway loops and cost overruns.
"""


class CallLimitMiddleware:
    """
    Tracks per-run call counts and raises a RuntimeError if the limit
    is exceeded. The graph checks this before each model invocation.
    """

    def __init__(self, max_calls: int = 5):
        self.max_calls = max_calls

    def check_and_increment(self, current_count: int) -> int:
        """
        Returns the incremented count, or raises RuntimeError if the cap
        would be exceeded.
        """
        if current_count >= self.max_calls:
            raise RuntimeError(
                f"CallLimitMiddleware: maximum LLM call limit of "
                f"{self.max_calls} reached for this run."
            )
        return current_count + 1
