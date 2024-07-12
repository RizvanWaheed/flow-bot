import string, pymongo
from datetime import datetime
from quart import Blueprint, request, jsonify, make_response, g
from functions.utilities import connect, process_name
from decorators.teams import x_super_team
from decorators.key import x_app_key
from decorators.jwt import jwt_token

punc = string.punctuation

stories_bp = Blueprint('stories', __name__)

@stories_bp.route('/get', methods=['GET'])
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
        stories_collections = db['stories']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            stories_record = await stories_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})

            if stories_record:
                stories = stories_record['data']['stories']

                if stories:
                    return await make_response(jsonify(stories), 200)
                else:
                    return await make_response(jsonify(message=f'An error occurred: no story exists for this bot'), 400)
            else:
                return await make_response(jsonify(message=f'An error occurred: no story exists for this bot'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)  
            
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)

@stories_bp.route('/create', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def create():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        elif not data.get('story'):
            return await make_response(jsonify(message = "An error occurred: missing 'story' parameter"), 400)
        elif not data.get('storyFlow'):
            return await make_response(jsonify(message = "An error occurred: missing 'storyFlow' parameter"), 400)
        
        bot_id, story, storyFlow = data.get('bot_id'), data.get('story'), data.getlist('storyFlow')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        story = process_name(story)

        db = await connect()

        bots_collections = db['bots']
        rules_collections = db['rules']
        stories_collections = db['stories']
        domain_collections = db['domain']
        process_collections = db['process']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 0:
                stories_record = await stories_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
                domain_record = await domain_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
                rules_record = await rules_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
                    
                if stories_record and domain_record and rules_record:
                    stories = stories_record['data']
                    domain = domain_record['data']
                    rules = rules_record['data']

                    if stories['stories']:
                        for name in stories['stories']:
                            if story == name['story']:
                                return await make_response(jsonify(message = f'An error occurred: story name already exists'), 400)
                    
                    if len(storyFlow) % 2 != 0:
                        return await make_response(jsonify(message='An error occurred: invalid amount of intents and responses'), 400)
                    
                    intents_list, responses_list = [], []
                    for idx, name in enumerate(storyFlow):
                        if idx % 2 == 0:
                            intents_list.append(name)
                        else:
                            responses_list.append(name)

                    if domain['intents']:
                        for intent in intents_list:
                            if intent not in domain['intents']:
                                return await make_response(jsonify(message = f"An error occurred: intent '{intent}' doesn\'t exist"), 400)    
                    else:
                        return await make_response(jsonify(message='An error occurred: no intents exists for this bot'), 400)
                    
                    if domain['responses']:
                        for response in responses_list:
                            if response not in domain['responses']:
                                return await make_response(jsonify(message = f"An error occurred: response '{response}' doesn\'t exist"), 400)
                    else:
                        return await make_response(jsonify(message='An error occurred: no response exists for this bot'), 400)

                    if rules['rules']:
                        for rule in rules['rules']:
                            for step in rule['steps']:
                                if 'intent' in step:
                                    intent_temp = step['intent']
                                    break
                        
                            for intent in intents_list:
                                if intent_temp == intent:
                                    return await make_response(jsonify(message=f'An error occurred: intent {intent} name already exists in a rule'), 400)
                        
                    if stories['stories']:
                        stories['stories'].append({'story': story, 'steps': [{'intent': intents_list[0]}, {'action': responses_list[0]}]})

                        for counter1, counter2 in zip(intents_list[1:], responses_list[1:]):
                            for counter3 in stories['stories']:
                                if counter3['story'] == story: 
                                    counter3['steps'].append({'intent': counter1})
                                    counter3['steps'].append({'action': counter2})

                        steps = stories['stories'][-1]['steps']

                        for i in stories['stories'][0:-1]:
                            if i['steps'] == steps:
                                return await make_response(jsonify(message='An error occurred: story with the same intents and responses already exists'), 400)
                    else:
                        stories['stories'] = [{'story': story, 'steps': [{'intent': intents_list[0]}, {'action': responses_list[0]}]}]

                        for counter1, counter2 in zip(intents_list[1:], responses_list[1:]):
                            stories['stories'][0]['steps'].append({'intent': counter1})
                            stories['stories'][0]['steps'].append({'action': counter2})

                    now = datetime.now()
                    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                    await stories_collections.update_one({"_id": stories_record["_id"]}, {"$set": {"is_active": 0}})
                    await stories_collections.update_one({"_id": stories_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await stories_collections.update_one({"_id": stories_record["_id"]}, {"$set": {"modified_by": user}})

                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                    document = {'company_id': company_id, 'bot_id': bot_id, 'data': stories, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await stories_collections.insert_one(document)
                    
                    return await make_response(jsonify(message = f'Story has been created for the bot'), 200)
                else:
                    return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)   
            
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)

@stories_bp.route('/delete', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def delete():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        elif not data.get('story'):
            return await make_response(jsonify(message = "An error occurred: missing 'story' parameter"), 400)
        
        bot_id, story = data.get('bot_id'), data.get('story')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        process_collections = db['process']
        stories_collections = db['stories']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 0:
                stories_record = await stories_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})

                if stories_record:
                    stories = stories_record['data']

                    if stories['stories']:
                        stories_list = list(stories['stories'])
                    else:
                        return await make_response(jsonify(message = f'An error occurred: no story exists for this bot'), 400)

                    remove = 0
                    for counter in stories['stories']:
                        if counter['story'] == story:
                            remove = 1
                            stories_list.remove(counter)
                            break

                    if remove:
                        stories['stories'] = stories_list
                    else:
                        return await make_response(jsonify(message = f'An error occurred: story doesn\'t exist for this bot'), 400) 

                    now = datetime.now()
                    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                    await stories_collections.update_one({"_id": stories_record["_id"]}, {"$set": {"is_active": 0}})
                    await stories_collections.update_one({"_id": stories_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await stories_collections.update_one({"_id": stories_record["_id"]}, {"$set": {"modified_by": user}})

                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                    document = {'company_id': company_id, 'bot_id': bot_id, 'data': stories, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await stories_collections.insert_one(document)

                    return await make_response(jsonify(message=f'Story has been deleted for the bot!'), 200)
                else:
                    return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)  
                        
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)

