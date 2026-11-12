"""HTTP boundary: expected failures are actionable, bugs get a traceback."""
import functools
import logging

from errors import ApplicationError

logger = logging.getLogger(__name__)


def http_errors(handler):
    @functools.wraps(handler)
    def wrapped(self):
        try:
            return handler(self)
        except ApplicationError as error:
            self.send_json({"ok": False, "error": str(error), "error_code": error.code}, status=error.http_status)
        except Exception:
            logger.exception("Unexpected dashboard request failure")
            self.send_json({"ok": False, "error": "Internal server error", "error_code": "internal_error"}, status=500)
    return wrapped
