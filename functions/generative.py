import pymongo
from datetime import datetime
from decouple import config
from quart import Blueprint, request, jsonify, make_response, g
from functions.utilities import connect
from decorators.teams import x_super_team
from decorators.key import x_app_key
from decorators.jwt import jwt_token
from langchain_openai import ChatOpenAI

generative_bp = Blueprint('generative', __name__)

@generative_bp.route('/get', methods=['GET'])
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
        generative_collections = db['generative']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            generative_record = await generative_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})

            if generative_record:
                augment_prompt = generative_record['augment_prompt']
                return await make_response(jsonify(augment_prompt), 200)
            else:
                return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)         
               
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)

@generative_bp.route('/augment', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def augment():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message="An error occurred: missing 'bot_id' parameter"), 400)
        elif not data.get('intent'):
            return await make_response(jsonify(message="An error occurred: missing 'intent' parameter"), 400)
        
        bot_id, intent = data.get('bot_id'), data.get('intent')

        company_id = request.headers.get('x-super-team')

        db = await connect()

        bots_collections = db['bots']
        generative_collections = db['generative']
        process_collections = db['process']  

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 0:
                generative_record = await generative_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})
                    
                if generative_record:
                    template = f"{generative_record['augment_prompt']}\n\n{intent}"        
                    
                    chatGPT = ChatOpenAI(temperature = 0.3, openai_api_key = config("OPENAI_API_KEY"), model = 'gpt-3.5-turbo')
                    examples = chatGPT.invoke(template).content

                    return await make_response(jsonify(message = examples), 200)
                else:
                    return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)  
  
    except Exception as e:
        return await make_response(jsonify(message = f"An error occurred: {str(e)}"), 500)

@generative_bp.route('/prompt', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def prompt():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message="An error occurred: missing 'bot_id' parameter"), 400)
        elif not data.get('augment_prompt'):
            return await make_response(jsonify(message="An error occurred: missing 'augment_prompt' parameter"), 400)
        
        bot_id, augment_prompt = data.get('bot_id'), data.get('augment_prompt')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        generative_collections = db['generative']
        process_collections = db['process']  

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 0:
                generative_record = await generative_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

                if generative_record:

                    now = datetime.now()
                    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                    await generative_collections.update_one({"_id": generative_record["_id"]}, {"$set": {"is_active": 0}})
                    await generative_collections.update_one({"_id": generative_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await generative_collections.update_one({"_id": generative_record["_id"]}, {"$set": {"modified_by": user}})

                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                    document = {'company_id': company_id, 'bot_id': bot_id, 'augment_prompt': augment_prompt, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await generative_collections.insert_one(document)
                    
                    return await make_response(jsonify(message="Prompt has been updated for the bot!"), 200)
                else:
                    return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)  
        
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
