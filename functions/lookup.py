import pymongo
from datetime import datetime
from quart import Blueprint, request, jsonify, make_response, g
from functions.utilities import connect, process_name
from decorators.teams import x_super_team
from decorators.key import x_app_key
from decorators.jwt import jwt_token

lookup_bp = Blueprint('lookup', __name__)

@lookup_bp.route('/get', methods=['GET'])
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
        nlu_collections = db['nlu']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            nlu_record = await nlu_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})

            if nlu_record:
                nlu = nlu_record['data']

                if nlu:
                    lookup = [entry for entry in nlu['nlu'] if 'lookup' in entry]
                    if lookup:
                        return await make_response(jsonify(lookup), 200)
                    else:
                        return await make_response(jsonify(message=f'An error occurred: no lookup exist for this bot'), 200)
            else:
                return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)  
            
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
    
@lookup_bp.route('/create', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def create():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        elif not data.get('name'):
            return await make_response(jsonify(message = "An error occurred: missing 'name' parameter"), 400)
        elif not data.get('examples'):
            return await make_response(jsonify(message = "An error occurred: missing 'examples' parameter"), 400)
        
        bot_id, name, examples = data.get('bot_id'), data.get('name'), data.getlist('examples')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        name = process_name(name, 1)
    
        if len(examples) < 1:
            return await make_response(jsonify(message = 'An error occurred: intent examples should be more than one (1)'), 400)
        
        if len(examples) != len(set(examples)):
            return await make_response(jsonify(message = 'An error occurred: duplicate examples exist'), 400)
        
        if '' in examples:
            return await make_response(jsonify(message = 'An error occurred: examples cannot be empty'), 400)

        db = await connect()

        bots_collections = db['bots']
        nlu_collections = db['nlu']
        process_collections = db['process']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 0:
                nlu_record = await nlu_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
                    
                if nlu_record:
                    nlu = nlu_record['data']

                    temp = ''
                    for example in examples:
                        temp += f'- {example}\n'
                    
                    lookup = [entry for entry in nlu['nlu'] if 'lookup' in entry]

                    for entry in lookup:
                        if name == entry['lookup']:
                            return await make_response(jsonify(message = f'An error occurred: lookup name already exists'), 400) 

                    nlu['nlu'].append({'lookup': name, 'examples': temp})

                    now = datetime.now()
                    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                    await nlu_collections.update_one({"_id": nlu_record["_id"]}, {"$set": {"is_active": 0}})
                    await nlu_collections.update_one({"_id": nlu_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await nlu_collections.update_one({"_id": nlu_record["_id"]}, {"$set": {"modified_by": user}})

                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                    document = {"company_id": company_id, 'bot_id': bot_id, 'data': nlu, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await nlu_collections.insert_one(document)

                    return await make_response(jsonify(message = f'Lookup has been created for the bot'), 200)
                else:
                    return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)   
            
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
       
@lookup_bp.route('/delete', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def delete():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        elif not data.get('name'):
            return await make_response(jsonify(message = "An error occurred: missing 'name' parameter"), 400)
        
        bot_id, name = data.get('bot_id'), data.get('name')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        nlu_collections = db['nlu']
        process_collections = db['process']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 0:
                nlu_record = await nlu_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})

                if nlu_record:
                    nlu = nlu_record['data']

                    if any(entry.get('lookup') == name for entry in nlu['nlu']):
                        nlu['nlu'] = [entry for entry in nlu['nlu'] if entry.get('lookup') != name]
                    else:
                        return await make_response(jsonify(message = f'An error occurred: lookup doesn\'t exist'), 400) 

                    now = datetime.now()
                    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                    await nlu_collections.update_one({"_id": nlu_record["_id"]}, {"$set": {"is_active": 0}})
                    await nlu_collections.update_one({"_id": nlu_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await nlu_collections.update_one({"_id": nlu_record["_id"]}, {"$set": {"modified_by": user}})

                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                    document = {"company_id": company_id, 'bot_id': bot_id, 'data': nlu, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await nlu_collections.insert_one(document)

                    return await make_response(jsonify(message=f'Lookup has been deleted for the bot!'), 200)
                else:
                    return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)   

    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)