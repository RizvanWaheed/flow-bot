import pymongo
from datetime import datetime
from quart import Blueprint, request, jsonify, make_response, g
from functions.utilities import connect, process_name
from decorators.teams import x_super_team
from decorators.key import x_app_key
from decorators.jwt import jwt_token

intents_bp = Blueprint('intents', __name__)

@intents_bp.route('/get', methods=['GET'])
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
                    intents = [entry for entry in nlu['nlu'] if 'intent' in entry]

                    intents_to_remove = ["invalid_character_input", "previous_step_option", "start_message", "restart_conversation_option"]
                    filtered_intents = [intent for intent in intents if intent["intent"] not in intents_to_remove]

                    if filtered_intents:
                        return await make_response(jsonify(filtered_intents), 200)
                    else:
                        return await make_response(jsonify(message=f'An error occurred: no intents exist for this bot'), 200)
            else:
                return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)  
            
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
    
@intents_bp.route('/create', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def create():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        elif not data.get('intent'):
            return await make_response(jsonify(message = "An error occurred: missing 'intent' parameter"), 400)
        elif not data.get('examples'):
            return await make_response(jsonify(message = "An error occurred: missing 'examples' parameter"), 400)
        
        bot_id, intent, examples = data.get('bot_id'), data.get('intent'), data.getlist('examples')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        intent = process_name(intent, 1)
    
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
        domain_collections = db['domain']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 0:
                nlu_record = await nlu_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
                domain_record = await domain_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
                    
                if nlu_record and domain_record:
                    nlu = nlu_record['data']
                    domain = domain_record['data']

                    if domain['intents']:
                        if intent in domain['intents']:
                            return await make_response(jsonify(message = f'An error occurred: intent name already exists'), 400)   
                        else:
                            temp = ''  
                            for example in examples:
                                for entry in nlu['nlu']:
                                    for single in entry['examples'].split('\n'):
                                        if str(example).strip() == str(single.replace('-', '')).strip():
                                            return await make_response(jsonify(message=f"An error occurred: example '{str(example).strip()}' found in another intent '{entry['intent']}'"), 400)
                                temp += f'- {example}\n'

                            domain['intents'].append(intent)    
                            nlu['nlu'].append({'intent': intent, 'examples': temp})
                    else:
                        temp = ''
                        for example in examples:
                            temp += f'- {example}\n'

                        domain['intents'] = [intent]    
                        nlu['nlu'] = [{'intent': intent, 'examples': temp}]

                    now = datetime.now()
                    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                    await nlu_collections.update_one({"_id": nlu_record["_id"]}, {"$set": {"is_active": 0}})
                    await nlu_collections.update_one({"_id": nlu_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await nlu_collections.update_one({"_id": nlu_record["_id"]}, {"$set": {"modified_by": user}})

                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"is_active": 0}})
                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_by": user}})

                    document = {"company_id": company_id, 'bot_id': bot_id, 'data': nlu, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await nlu_collections.insert_one(document)

                    document = {"company_id": company_id, 'bot_id': bot_id, 'data': domain, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await domain_collections.insert_one(document)

                    return await make_response(jsonify(message = f'Intent has been created for the bot'), 200)
                else:
                    return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)   
            
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
       
@intents_bp.route('/delete', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def delete():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        elif not data.get('intent'):
            return await make_response(jsonify(message = "An error occurred: missing 'intent' parameter"), 400)
        
        bot_id, intent = data.get('bot_id'), data.get('intent')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        nlu_collections = db['nlu']
        process_collections = db['process']
        domain_collections = db['domain']
        stories_collections = db['stories']
        rules_collections = db['rules']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 0:
                nlu_record = await nlu_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
                domain_record = await domain_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
                stories_record = await stories_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
                rules_record = await rules_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})

                if nlu_record and domain_record and rules_record and stories_record:
                    nlu, domain, rules, stories = nlu_record['data'], domain_record['data'], rules_record['data'], stories_record['data']

                    if rules['rules']:
                        for counter in rules['rules']:
                            if counter['steps'][0]['intent'] == intent:
                                return await make_response(jsonify(message=f'''An error occurred: intent already exists in a rule '{counter["rule"]}\''''), 400)
                                
                    if stories['stories']:
                        for counter in stories['stories']:
                            temp = counter['steps'][0::2]
                            for counter1 in temp:
                                if counter1['intent'] == intent:
                                    return await make_response(jsonify(message=f'''An error occurred: intent already exists in a story '{counter["story"]}\''''), 400)
                                
                    if any(entry.get('intent') == intent for entry in nlu['nlu']):
                        nlu['nlu'] = [entry for entry in nlu['nlu'] if entry.get('intent') != intent]
                        domain['intents'].remove(intent)
                    else:
                        return await make_response(jsonify(message=f'An error occurred: intent doesn\'t exist.'), 400) 

                    now = datetime.now()
                    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                    await nlu_collections.update_one({"_id": nlu_record["_id"]}, {"$set": {"is_active": 0}})
                    await nlu_collections.update_one({"_id": nlu_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await nlu_collections.update_one({"_id": nlu_record["_id"]}, {"$set": {"modified_by": user}})

                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"is_active": 0}})
                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_by": user}})

                    document = {'company_id': company_id, 'bot_id': bot_id, 'data': nlu, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await nlu_collections.insert_one(document)

                    document = {'company_id': company_id, 'bot_id': bot_id, 'data': domain, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await domain_collections.insert_one(document)

                    return await make_response(jsonify(message=f'Intent has been deleted for the bot!'), 200)
                else:
                    return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)   

    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)