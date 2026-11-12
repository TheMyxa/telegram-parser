"""MCP tool boundary; framework handles serialization of raised tool errors."""
import functools
import logging

from errors import ApplicationError

logger = logging.getLogger(__name__)


def tool_errors(tool):
    @functools.wraps(tool)
    def wrapped(*args, **kwargs):
        try:
            return tool(*args, **kwargs)
        except ApplicationError as error:
            raise ValueError(f"{error.code}: {error}") from error
        except (ValueError, OSError):
            raise
        except Exception as error:
            logger.exception("Unexpected MCP tool failure")
            raise RuntimeError("Internal tool error") from error
    return wrapped
