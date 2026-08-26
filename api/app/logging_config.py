"""Central logging configuration for the application.

Every module that logs does so through ``logging.getLogger(__name__)``. Because
all application modules live under the ``app`` package, every application log
record carries a name like ``app.services.import_service`` and therefore
propagates to the ``app`` logger. :func:`configure_logging` gives that single
``app`` logger one consistently-formatted handler, without touching the
framework's (uvicorn's) own loggers or the root logger.
"""

import logging
import sys

#: One consistent line format for all application logs.
LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Attach a single, consistently-formatted handler to the ``app`` logger.

    Safe to call more than once: an existing handler is reused rather than
    duplicated. ``propagate`` is disabled so application records are emitted
    exactly once, by this handler, in this format.
    """
    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)
    app_logger.propagate = False
    if not app_logger.handlers:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        app_logger.addHandler(handler)
