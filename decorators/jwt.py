from quart import request, jsonify, make_response, g
import jwt
from functools import wraps
from decouple import config

salt = config("TOKEN_SALT")

def jwt_token(fn):
    @wraps(fn)
    async def decorated():

        headers = request.headers

        if "Authorization" in headers:
            token_from_request = headers.get('Authorization').split(" ")[1]

        if not token_from_request:
            return await make_response(jsonify(message="An error occurred: missing authorization token"), 401)
      
        try:
            options = {
            'verify_exp': False, 
            'verify_aud': False 
            }

            payload = jwt.decode(token_from_request, salt, 'HS256', options)
            g.current_user = payload['UserId']

        except:
           return await make_response(jsonify(message="An error occurred: invalid authorization token"), 401)
        
        return await fn()

    return decorated