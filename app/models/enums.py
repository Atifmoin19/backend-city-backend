from enum import StrEnum


class Role(StrEnum):
    USER = "user"
    CONTENT_EDITOR = "content_editor"
    SUPER_ADMIN = "super_admin"


class ContentStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class EmailTokenPurpose(StrEnum):
    VERIFY = "verify"
    RESET = "reset"


class TopicProgressStatus(StrEnum):
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    PASSED = "passed"
