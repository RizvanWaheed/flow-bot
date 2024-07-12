from quart import request, jsonify, make_response
from functools import wraps

def x_super_team(fn):
    @wraps(fn)
    async def teamdecorator():
        x_super_team = request.headers.get('x-super-team')

        if x_super_team and x_super_team != 0:
            return await fn()
        else:
            return await make_response(jsonify(message="An error occurred: missing 'x-super-team' header"), 401)
    return teamdecorator
