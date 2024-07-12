import pymongo, re
from datetime import datetime
from quart import Blueprint, request, jsonify, make_response, g
from functions.utilities import connect, process_name
from decorators.teams import x_super_team
from decorators.key import x_app_key
from decorators.jwt import jwt_token

actions_bp = Blueprint('actions', __name__)

@actions_bp.route('/get', methods=['GET'])
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
        actions_collections = db['actions']
        domain_collections = db['domain']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            action_record = await actions_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})
            domain_record = await domain_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

            if action_record and domain_record:
                return await make_response(jsonify(domain_record['data']['actions']), 200)
            else:
                return await make_response(jsonify(message = f'An error occurred: no actions exists for this bot'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)         
               
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
        
@actions_bp.route('/create', methods=['POST'])
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
        elif not data.get('code'):
            return await make_response(jsonify(message = "An error occurred: missing 'code' parameter"), 400)
        
        bot_id, name, code = data.get('bot_id'), data.get('name'), data.get('code')

        name = process_name(name, 1)

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        process_collections = db['process']  
        actions_collections = db['actions']
        domain_collections = db['domain']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 0:
                domain_record = await domain_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
                actions_record = await actions_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})

                if domain_record and actions_record:
                    actions = actions_record['data']
                    domain = domain_record['data']

                    if domain['actions']:
                        if name in domain['actions']:
                            return await make_response(jsonify(message='An error occurred: action name already exists'), 400)
                        
                        domain['actions'].append(name)
                        actions['actions'] += f'\n\n{code}'   
                    else:
                        return await make_response(jsonify(message='An error occurred: no intents exists for this bot'), 400)
                    
                else:
                    return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)

                now = datetime.now()
                date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                await actions_collections.update_one({"_id": actions_record["_id"]}, {"$set": {"is_active": 0}})
                await actions_collections.update_one({"_id": actions_record["_id"]}, {"$set": {"modified_date": date_time}})
                await actions_collections.update_one({"_id": actions_record["_id"]}, {"$set": {"modified_by": user}})

                await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"is_active": 0}})
                await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_date": date_time}})
                await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_by": user}})

                document = {"company_id": company_id, 'bot_id': bot_id, 'data': domain, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                await domain_collections.insert_one(document)

                document = {"company_id": company_id, 'bot_id': bot_id, 'data': actions, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                await actions_collections.insert_one(document)
                        
                return await make_response(jsonify(message = f'Action has been created for the bot!'), 200)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)   
            
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
        
@actions_bp.route('/delete', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def delete():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        if not data.get('name'):
            return await make_response(jsonify(message = "An error occurred: missing 'name' parameter"), 400)
        
        bot_id, name = data.get('bot_id'), data.get('name')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        actions_collections = db['actions']
        domain_collections = db['domain'] 
        process_collections = db['process']    

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])

            if latest_process['is_process'] == 0:
                actions_record = await actions_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})
                domain_record = await domain_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

                if actions_record and domain_record:
                    actions = actions_record['data']
                    domain = domain_record['data']

                    if not domain['actions']:
                        return await make_response(jsonify(message = f'An error occurred: no actions exists for this bot'), 400)
                    
                    if name not in domain['actions']:
                        return await make_response(jsonify(message = f'An error occurred: action doesn\'t exist'), 400)
                    
                    number = 0
                    for idx, temp in enumerate(domain['actions'], 1):
                        if name == temp:
                            number = idx

                    result = re.split(r'(class)', actions['actions'])

                    idx, count = 2, 1
                    while 1:
                        try:
                            result[idx]

                            if count == number:
                               result.pop(idx) 
                               result.pop(idx-1)
                               result = ''.join(result)
                               break
                            
                            idx += 2
                            count += 1
                        except:
                            break

                    domain['actions'].remove(name)
   
                    now = datetime.now()
                    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                    await actions_collections.update_one({"_id": actions_record["_id"]}, {"$set": {"is_active": 0}})
                    await actions_collections.update_one({"_id": actions_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await actions_collections.update_one({"_id": actions_record["_id"]}, {"$set": {"modified_by": user}})

                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"is_active": 0}})
                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_by": user}})

                    document = {"company_id": company_id, 'bot_id': bot_id, 'data': domain, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await domain_collections.insert_one(document)

                    document = {"company_id": company_id, 'bot_id': bot_id, 'data': result, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await actions_collections.insert_one(document)

                    return await make_response(jsonify(message = f'Action has been deleted for the bot!'), 200)
                else:
                    return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)                    
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)   

    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)