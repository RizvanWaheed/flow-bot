import pymongo
from datetime import datetime
from quart import Blueprint, request, jsonify, make_response, g
from functions.utilities import connect, process_name
from decorators.teams import x_super_team
from decorators.key import x_app_key
from decorators.jwt import jwt_token

rules_bp = Blueprint('rules', __name__)

@rules_bp.route('/get', methods=['GET'])
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
        rules_collections = db['rules']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            rules_record = await rules_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})

            if rules_record:
                rules = rules_record['data']['rules']

                rules_to_remove = ["Ignore any starting message to display the first menu", "Ask the user to rephrase whenever they send a message with low NLU confidence", "Invalid number or character is input", "Jump to previous step", "Restart conversation"]
                filtered_rules = [rule for rule in rules if rule["rule"] not in rules_to_remove]

                if filtered_rules:
                    return await make_response(jsonify(filtered_rules), 200)
                else:
                    return await make_response(jsonify(message=f'An error occurred: no rules exist for this bot'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)  
            
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)

@rules_bp.route('/create', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def create():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        if not data.get('rule'):
            return await make_response(jsonify(message = "An error occurred: missing 'rule' parameter"), 400)
        if not data.get('intent'):
            return await make_response(jsonify(message = "An error occurred: missing 'intent' parameter"), 400)
        if not data.get('response'):
            return await make_response(jsonify(message = "An error occurred: missing 'response' parameter"), 400) 
        
        bot_id, rule, intent, response = data.get('bot_id'), data.get('rule'), data.get('intent'), data.get('response')

        rule = process_name(rule)

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        rules_collections = db['rules']
        process_collections = db['process']
        domain_collections = db['domain']
        stories_collections = db['stories']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])

            if latest_process['is_process'] == 0:
                domain_record = await domain_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
                rules_record = await rules_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
                stories_record = await stories_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})

                if rules_record and domain_record and stories_record:
                    rules = rules_record['data']
                    domain = domain_record['data']
                    stories = stories_record['data']

                    if rules['rules']:
                        for counter in rules['rules']:
                            if counter['rule'] == rule:
                                return await make_response(jsonify(message = f'An error occurred: rule name already exists'), 400)   
 
                    if not domain['intents']:
                        return await make_response(jsonify(message='An error occurred: no intent exists for this bot'), 400)
                    
                    if not domain['responses']:
                        return await make_response(jsonify(message='An error occurred: no response exists for this bot'), 400)

                    if stories['stories']:
                        for counter1 in stories['stories']:
                            for counter2 in counter1['steps']:
                                if 'intent' in counter2:
                                    if counter2['intent'] == intent:
                                        return await make_response(jsonify(message=f"An error occurred: intent '{intent}' already exists in a story"), 400)   

                    intents = domain['intents']
                    for temp1 in intents:
                        if intent == temp1:
                            responses = list(domain['responses'].keys())
                            for temp2 in responses:
                                if response == temp2 or response == 'action_back':
                                    if rules['rules']:
                                        temp1 = [{'intent': intent}, {'action': response}]
                                        for temp2 in rules['rules']:
                                            if temp2['steps'] == temp1:
                                                return await make_response(jsonify(message=f"An error occurred: rule '{temp2['rule']}' with the same intent and response already exists"), 400) 
                                            
                                        rules['rules'].append({'rule': rule, 'steps': [{'intent': intent}, {'action': response}]})  
                                    else:
                                        rules['rules'] = [{'rule': rule, 'steps': [{'intent': intent}, {'action': response}]}]

                                    now = datetime.now()
                                    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                                    await rules_collections.update_one({"_id": rules_record["_id"]}, {"$set": {"is_active": 0}})
                                    await rules_collections.update_one({"_id": rules_record["_id"]}, {"$set": {"modified_date": date_time}})
                                    await rules_collections.update_one({"_id": rules_record["_id"]}, {"$set": {"modified_by": user}})

                                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                                    document = {'company_id': company_id, 'bot_id': bot_id, 'data': rules, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                                    await rules_collections.insert_one(document)

                                    return await make_response(jsonify(message = f'Rule has been created for the bot'), 200)
                                
                            return await make_response(jsonify(message = f'An error occurred: response doesn\'t exist'), 400)
                    
                    return await make_response(jsonify(message = f'An error occurred: intent doesn\'t exist'), 400)
                else:
                    return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)  
            
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
           
@rules_bp.route('/delete', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def delete():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        elif not data.get('rule'):
            return await make_response(jsonify(message = "An error occurred: missing 'rule' parameter"), 400)
        
        bot_id, rule = data.get('bot_id'), data.get('rule')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        process_collections = db['process']
        rules_collections = db['rules']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 0:
                rules_record = await rules_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})

                if rules_record:
                    rules = rules_record['data']

                    if rules['rules']:
                        rules_list = list(rules['rules'])
                    else:
                        return await make_response(jsonify(message = f'An error occurred: no rules exists for this bot'), 400)

                    remove = 0
                    for counter in rules['rules']:
                        if counter['rule'] == rule:
                            remove = 1
                            rules_list.remove(counter)
                            break

                    if remove:
                        rules['rules'] = rules_list
                    else:
                        return await make_response(jsonify(message = f'An error occurred: rule doesn\'t exist for this bot'), 400) 

                    now = datetime.now()
                    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                    await rules_collections.update_one({"_id": rules_record["_id"]}, {"$set": {"is_active": 0}})
                    await rules_collections.update_one({"_id": rules_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await rules_collections.update_one({"_id": rules_record["_id"]}, {"$set": {"modified_by": user}})
                
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                    document = {'company_id': company_id, 'bot_id': bot_id, 'data': rules, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await rules_collections.insert_one(document)

                    return await make_response(jsonify(message=f'Rule has been deleted for the bot!'), 200) 
                else:
                    return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400) 
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)
                        
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)