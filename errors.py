"""Expected application failures shared by CLI, HTTP and background services.

Only operational/validation failures belong here. Programming errors must retain
their original type and reach a boundary that records a traceback.
"""
import functools
import sqlite3


class ApplicationError(Exception):
    code = "application_error"
    http_status = 400


class ValidationError(ApplicationError, ValueError):
    code = "invalid_input"


class DatasetCorruptedError(ApplicationError, ValueError):
    code = "dataset_corrupted"
    http_status = 422


class IdentityModeMismatchError(ApplicationError, ValueError):
    code = "identity_mode_mismatch"
    http_status = 409


class AnonymizationRulesError(ValidationError):
    code = "invalid_anonymization_rules"


class AnonymizationMapCorruptedError(ApplicationError, ValueError):
    code = "anonymization_map_corrupted"
    http_status = 422


class AnonymizationMapLockedError(ApplicationError, RuntimeError):
    code = "anonymization_map_locked"
    http_status = 409


class ProcessAlreadyRunningError(ApplicationError, RuntimeError):
    code = "process_already_running"
    http_status = 409


class ProcessStartError(ApplicationError, RuntimeError):
    code = "process_start_failed"
    http_status = 500


class IndexUnavailableError(ApplicationError, RuntimeError):
    code = "index_unavailable"
    http_status = 503


def index_operation(operation):
    """Translate storage failures, preserving programming errors and causes."""
    @functools.wraps(operation)
    def wrapped(*args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except sqlite3.ProgrammingError:
            raise
        except (sqlite3.Error, OSError) as error:
            raise IndexUnavailableError("Local SQLite index is unavailable") from error
    return wrapped
