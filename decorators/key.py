from quart import request, jsonify, make_response
from functools import wraps
from decouple import config

key = config("X_APP_KEY")

def x_app_key(fn):
    @wraps(fn)
    async def appdecorator():
        x_app_key = request.headers.get('x-app-key')

        if x_app_key == key:
            return await fn()
        else:
            return await make_response(jsonify(message="An error occurred: missing or invalid 'x-app-key' header"), 401)
    return appdecorator
