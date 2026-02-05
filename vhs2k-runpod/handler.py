import json
import time

from pipeline import pipeline, PipelineError, ERR_INTERNAL


def handler(event, context=None):
    logs = []
    try:
        request = event.get("input", {}) if isinstance(event, dict) else {}
        result = pipeline(request)
        return result
    except PipelineError as pe:
        return {
            "status": "failed",
            "error_code": pe.code,
            "error_message": pe.message,
            "logs": pe.logs,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "error_code": ERR_INTERNAL,
            "error_message": "Internal error",
            "logs": ["Unhandled error: %s" % exc],
        }
