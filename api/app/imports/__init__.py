"""Activity file import: format detection and per-format parsers.

Parsers are pure (bytes -> ParsedActivity); see the individual modules.
"""

from app.imports.base import ActivityParser, FormatDetector
from app.imports.fit_parser import FitParser
from app.imports.gpx_parser import GpxParser
from app.imports.parsed import ParsedActivity, ParsedSportMetrics, ParsedTrackpoint
from app.imports.sports import DEFAULT_SPORT, SPORT_TYPES, resolve_sport
from app.imports.tcx_parser import TcxParser

__all__ = [
    "ActivityParser",
    "DEFAULT_SPORT",
    "FitParser",
    "FormatDetector",
    "GpxParser",
    "ParsedActivity",
    "ParsedSportMetrics",
    "ParsedTrackpoint",
    "SPORT_TYPES",
    "TcxParser",
    "build_default_detector",
    "resolve_sport",
]


def build_default_detector() -> FormatDetector:
    """The detector wired with every supported format.

    FIT is listed first: it is the only format recognized by magic bytes.
    """
    return FormatDetector([FitParser(), GpxParser(), TcxParser()])
