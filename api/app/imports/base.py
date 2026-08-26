"""The parser contract and file-format detection."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from enum import StrEnum
from typing import ClassVar

from app.errors.app_error import ActivityImportError
from app.imports.parsed import ParsedActivity


class SourceFormat(StrEnum):
    """File formats activities can be imported from.

    Values mirror the seeded rows of the ``source_formats`` reference table
    (the schema-level source of truth, enforced by
    ``activities_source_format_fkey``).
    """

    GPX = "gpx"
    TCX = "tcx"
    FIT = "fit"
    APPLE_HEALTH = "apple_health"


class ActivityParser(ABC):
    """Turns the raw bytes of one activity file format into a ParsedActivity."""

    #: Value stored in ``activities.source_format`` for this parser.
    source_format: ClassVar[SourceFormat]

    @abstractmethod
    def parse(self, data: bytes) -> ParsedActivity:
        """Parse ``data`` into a ParsedActivity.

        Raises ActivityImportError when the file is not a readable file of
        this format at all. Partial or missing data is not an error: it
        stays None and is reported via ParsedActivity.warnings.
        """

    @abstractmethod
    def supports(self, filename: str, header: bytes) -> bool:
        """Return True when this parser can handle the file.

        ``header`` is the first bytes of the file, for magic-byte detection.
        """


class FormatDetector:
    """Chooses the parser for an uploaded file.

    Parsers are consulted in the order they were given; the first one whose
    ``supports`` returns True wins. Parsers that rely on magic bytes (FIT)
    should be listed first so the extension cannot mislead detection.
    """

    def __init__(self, parsers: Sequence[ActivityParser]) -> None:
        self._parsers = list(parsers)

    def detect(self, filename: str, data: bytes) -> ActivityParser:
        """Return the parser for ``filename``/``data``.

        Raises ActivityImportError when no parser recognizes the file.
        """
        header = data[:32]
        for parser in self._parsers:
            if parser.supports(filename, header):
                return parser
        raise ActivityImportError(
            "Unrecognised file format. Upload a GPX, TCX or FIT activity file."
        )
