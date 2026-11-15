class ModerationError(Exception):
    """Base moderation exception."""


class ModerationRejected(ModerationError):
    """Content was rejected by a moderation or malware check."""


class ModerationUnavailable(ModerationError):
    """A required moderation dependency is unavailable."""
