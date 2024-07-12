import pymongo
from datetime import datetime
from quart import Blueprint, request, jsonify, make_response, g
from functions.utilities import connect, process_name
from decorators.teams import x_super_team
from decorators.key import x_app_key
from decorators.jwt import jwt_token

responses_bp = Blueprint('responses', __name__)

@responses_bp.route('/get', methods=['GET'])
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
        domain_collections = db['domain']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            domain_record = await domain_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})

            if domain_record:
                responses = domain_record['data']['responses']

                responses_to_remove = ["utter_fallback", "utter_restart", "utter_welcome", "utter_default"]

                if responses:
                    responses_list = []
                    for response in responses:
                        temp_1 = {}

                        if response not in responses_to_remove:
                            temp_1['utterance'] = response
                        
                            temp_2 = []
                            for res in responses[response]:
                                temp_2.append(res)

                            temp_1['response'] = temp_2
                            responses_list.append(temp_1)

                    if responses_list:
                        return await make_response(jsonify(responses_list), 200)
                    else:
                        return await make_response(jsonify(message=f'An error occurred: no responses exist for this bot'), 400)
                else:
                    return await make_response(jsonify(message=f'An error occurred: no responses exist for this bot'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)  
            
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)

@responses_bp.route('/create', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def create():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        elif not data.get('response'):
            return await make_response(jsonify(message = "An error occurred: missing 'response' parameter"), 400)
        elif not data.get('text'):
            return await make_response(jsonify(message = "An error occurred: missing 'text' parameter"), 400)
        elif not data.get('previous'):
            return await make_response(jsonify(message = "An error occurred: missing 'previous' parameter"), 400)
        elif not data.get('restart'):
            return await make_response(jsonify(message = "An error occurred: missing 'restart' parameter"), 400)
        
        bot_id, response, text, previous, restart = data.get('bot_id'), data.get('response'), data.getlist('text'), int(data.get('previous')), int(data.get('restart'))

        response = process_name(response, 1)

        response = 'utter_' + response

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        process_collections = db['process']
        domain_collections = db['domain']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 0:
                domain_record = await domain_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
                    
                if domain_record:
                    domain = domain_record['data']

                    if previous == 1 and restart == 1:    
                        text_response = text[0] + '\n* for Previous\n# for Restart'
                    elif previous == 1:
                        text_response = text[0] + '\n* for Previous'
                    elif restart == 1:
                        text_response = text[0] + '\n# for Restart'
                    else:
                        text_response = text[0]
                    
                    if domain['responses']:
                        if response in domain['responses']:
                            return await make_response(jsonify(message=f'An error occurred: response name already exists'), 400)
                        else:
                            domain['responses'].update({response: [{'text': text_response}]})
                            for single in text[1:]:
                                domain['responses'][response].append({'text': single})
                    else:
                        domain['responses'] = {response: [{'text': text_response}]}
                        for single in text[1:]:
                            domain['responses'][response].append({'text': single})   

                    now = datetime.now()
                    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"is_active": 0}})
                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_by": user}})

                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                    document = {'company_id': company_id, 'bot_id': bot_id, 'data': domain, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await domain_collections.insert_one(document)

                    return await make_response(jsonify(message = f'Response has been created for the bot'), 200)
                else:
                    return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)   
    
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
        
@responses_bp.route('/delete', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def delete():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        elif not data.get('response'):
            return await make_response(jsonify(message = "An error occurred: missing 'response' parameter"), 400)
        
        bot_id, response = data.get('bot_id'), data.get('response')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        process_collections = db['process']
        domain_collections = db['domain']
        stories_collections = db['stories']
        rules_collections = db['rules']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 0:
                domain_record = await domain_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
                rules_record = await rules_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
                stories_record = await stories_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
                    
                if domain_record and rules_record and stories_record:
                    domain, rules, stories = domain_record['data'], rules_record['data'], stories_record['data']

                    if domain['responses']:
                        if response not in domain['responses']:
                            return await make_response(jsonify(message=f'An error occurred: response doesn\'t exist.'), 400)
                    else:
                        return await make_response(jsonify(message='An error occurred: no response exists for this bot'), 400)

                    if rules['rules']:
                        for counter in rules['rules']:
                            if counter['steps'][1]['action'] == response:
                                return await make_response(jsonify(message=f"An error occurred: response already exists in a rule '{counter['rule']}'"), 400)
                            
                    if stories['stories']:
                        for counter in stories['stories']:
                            temp = counter['steps'][1::2]
                            for counter1 in temp:
                                if counter1['action'] == response:
                                    return await make_response(jsonify(message=f"An error occurred: response already exists in a story '{counter['story']}'"), 400)
                    
                    domain['responses'].pop(response, None)

                    now = datetime.now()
                    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"is_active": 0}})
                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_by": user}})

                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                    document = {'company_id': company_id, 'bot_id': bot_id, 'data': domain, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await domain_collections.insert_one(document)

                    return await make_response(jsonify(message=f'Response has been deleted for the bot!'), 200)
                else:
                    return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)   
    
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
    
@responses_bp.route('/update_default', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def update_default():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        elif not data.get('response'):
            return await make_response(jsonify(message = "An error occurred: missing 'response' parameter"), 400)
        
        bot_id, response = data.get('bot_id'), data.get('response')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        process_collections = db['process']
        domain_collections = db['domain']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 0:
                domain_record = await domain_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
            
                if domain_record:
                    if 'utter_default' in domain_record['data']['responses'] and 'utter_fallback' in domain_record['data']['responses']:
                        domain_record['data']['responses']['utter_default'][0]['text'] = response
                        domain_record['data']['responses']['utter_fallback'][0]['text'] = response

                        now = datetime.now()
                        date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                        await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"is_active": 0}})
                        await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_date": date_time}})
                        await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_by": user}})

                        await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                        await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                        document = {'company_id': company_id, 'bot_id': bot_id, 'data': domain_record['data'], 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                        await domain_collections.insert_one(document)
                    else:
                        return await make_response(jsonify(message=f'An error occurred: response don\'t exist'), 400)

                    return await make_response(jsonify(message=f'Response has been updated for the bot!'), 200)
                else:
                    return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)   
            
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
    
@responses_bp.route('/update_menu', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def update_menu():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        elif not data.get('response'):
            return await make_response(jsonify(message = "An error occurred: missing 'response' parameter"), 400)
        
        bot_id, response = data.get('bot_id'), data.get('response')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        process_collections = db['process']
        domain_collections = db['domain']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 0:
                domain_record = await domain_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
            
                if domain_record:
                    if 'utter_welcome' in domain_record['data']['responses'] and 'utter_restart' in domain_record['data']['responses']:
                        domain_record['data']['responses']['utter_welcome'][0]['text'] = response
                        domain_record['data']['responses']['utter_restart'][0]['text'] = response

                        now = datetime.now()
                        date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                        await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"is_active": 0}})
                        await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_date": date_time}})
                        await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_by": user}})

                        await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                        await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                        document = {'company_id': company_id, 'bot_id': bot_id, 'data': domain_record['data'], 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                        await domain_collections.insert_one(document)

                        return await make_response(jsonify(message=f'Response has been updated for the bot!'), 200)
                    else:
                        return await make_response(jsonify(message=f'An error occurred: response don\'t exist'), 400)
                else:
                    return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)   
            
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)