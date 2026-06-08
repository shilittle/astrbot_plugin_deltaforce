from __future__ import annotations


class DeltaForceError(Exception):
    """Base error whose message is safe for internal logs only."""


class DeltaForceUserError(DeltaForceError):
    """Error with a QQ-safe one-line Chinese message."""

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


class DeltaForceConfigError(DeltaForceUserError):
    pass


class DeltaForceUpstreamError(DeltaForceUserError):
    pass

