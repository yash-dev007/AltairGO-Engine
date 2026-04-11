from http import HTTPStatus

from flask import current_app, request

_ERROR_CODE_BY_STATUS = {
    400: "ERR_VALIDATION",
    401: "ERR_UNAUTHORIZED",
    403: "ERR_UNAUTHORIZED",
    404: "ERR_NOT_FOUND",
    409: "ERR_VALIDATION",
    422: "ERR_VALIDATION",
    429: "ERR_RATE_LIMIT",
}


def error_code_for_status(status_code: int) -> str:
    return _ERROR_CODE_BY_STATUS.get(status_code, "ERR_SERVER")


def normalize_api_response(response):
    """Normalize JSON API responses to include success and error code fields."""
    if request.path == "/health" or not response.is_json:
        return response

    payload = response.get_json(silent=True)
    if payload is None:
        return response

    if isinstance(payload, dict):
        normalized = dict(payload)
        normalized.setdefault("success", response.status_code < 400)
        if response.status_code >= 400:
            normalized.setdefault("code", error_code_for_status(response.status_code))
            if "error" not in normalized:
                normalized["error"] = normalized.pop(
                    "message", HTTPStatus(response.status_code).phrase
                )
    elif isinstance(payload, list):
        normalized = {
            "success": response.status_code < 400,
            "data": payload,
        }
        if response.status_code >= 400:
            normalized["code"] = error_code_for_status(response.status_code)
            normalized["error"] = HTTPStatus(response.status_code).phrase
    else:
        normalized = {
            "success": response.status_code < 400,
            "data": payload,
        }
        if response.status_code >= 400:
            normalized["code"] = error_code_for_status(response.status_code)
            normalized["error"] = HTTPStatus(response.status_code).phrase

    response.set_data(current_app.json.dumps(normalized))
    response.content_length = len(response.get_data())
    return response
