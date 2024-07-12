import pymongo, secrets, string
from datetime import datetime
from quart import Blueprint, request, jsonify, make_response, g
from functions.utilities import connect
from decorators.teams import x_super_team
from decorators.key import x_app_key
from decorators.jwt import jwt_token

tokens_bp = Blueprint('tokens', __name__)

@tokens_bp.route('/get', methods=['GET'])
@x_super_team
@x_app_key
@jwt_token
async def get():
    try:
        data = request.args

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        
        bot_id = data.get('bot_id')

        company_id = request.headers.get('x-super-team')

        db = await connect()

        bots_collections = db['bots']
        tokens_collections = db['tokens']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            token_record = await tokens_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})

            if token_record:
                token = token_record['data']
                return await make_response(jsonify(token), 200)
            
            else:
                return await make_response(jsonify(message = f'An error occurred: no token exists for this bot'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)         
               
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
        
@tokens_bp.route('/create', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def create():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        elif not data.get('expiry_date'):
            return await make_response(jsonify(message = "An error occurred: missing 'token_type' parameter"), 400)\
            
        bot_id, expiry_time = data.get('bot_id'), data.get('expiry_date')
        
        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        process_collections = db['process']  
        tokens_collections = db['tokens']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 0:

                now = datetime.now()
                date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                date_format = "%d/%m/%Y %H:%M:%S"
                created_date = datetime.strptime(date_time, date_format)
                expiry_date = datetime.strptime(expiry_time, date_format)

                if expiry_date < created_date:
                    return await make_response(jsonify(message = "An error occurred: expiry date cannot be less than created date"), 400)

                alphabet = string.ascii_letters + string.digits
                token = ''.join(secrets.choice(alphabet) for _ in range(64))

                temp = {'token': token, 'created_date': date_time, 'expiry_date': expiry_time}

                token_record = await tokens_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

                if token_record:
                    await tokens_collections.update_one({"_id": token_record["_id"]}, {"$set": {"is_active": 0}})
                    await tokens_collections.update_one({"_id": token_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await tokens_collections.update_one({"_id": token_record["_id"]}, {"$set": {"modified_by": user}})

                    document = {"company_id": company_id, 'bot_id': bot_id, 'data': temp, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await tokens_collections.insert_one(document)

                else:
                    document = {"company_id": company_id, 'bot_id': bot_id, 'data': temp, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await tokens_collections.insert_one(document) 
                
                await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})
                        
                return await make_response(jsonify(message = f'Token has been created for the bot!'), 200)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)   
            
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
        
@tokens_bp.route('/delete', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def delete():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        
        bot_id = data.get('bot_id')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        tokens_collections = db['tokens'] 
        process_collections = db['process']    

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])

            if latest_process['is_process'] == 0:
                token_record = await tokens_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

                if not token_record:
                    return await make_response(jsonify(message = f'An error occurred: no token exists for this bot'), 400)

                now = datetime.now()
                date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                await tokens_collections.update_one({"_id": token_record["_id"]}, {"$set": {"is_active": 0}})
                await tokens_collections.update_one({"_id": token_record["_id"]}, {"$set": {"modified_date": date_time}})
                await tokens_collections.update_one({"_id": token_record["_id"]}, {"$set": {"modified_by": user}})

                await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                return await make_response(jsonify(message = f'Token has been deleted for the bot!'), 200)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)   

    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)