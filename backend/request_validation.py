from flask import jsonify, request
from marshmallow import ValidationError


def load_request_json(schema):
    payload = request.get_json(silent=True) or {}
    try:
        return schema.load(payload), None
    except ValidationError as err:
        return None, (jsonify({"errors": err.messages}), 400)
