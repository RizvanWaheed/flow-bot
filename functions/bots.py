import time, pymongo
from datetime import datetime
from quart import Blueprint, request, jsonify, make_response, g
from functions.utilities import connect, process_name
from decorators.teams import x_super_team
from decorators.key import x_app_key
from decorators.jwt import jwt_token

bots_bp = Blueprint('bots', __name__)

@bots_bp.route('/get', methods=['GET'])
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

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            bots_record.pop('_id')
            return await make_response(jsonify(bots_record), 200)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)         
            
    except Exception as e:
        return await make_response(jsonify(message = f"An error occurred: {str(e)}"), 500)
    
@bots_bp.route('/get_all', methods=['GET'])
@x_super_team
@x_app_key
@jwt_token
async def get_all():
    try:
        company_id = request.headers.get('x-super-team')

        db = await connect()

        bots_collections = db['bots']

        bots_documents = await bots_collections.find({"company_id": company_id, "is_active": 1}).to_list(length=None)

        if bots_documents:
            result = []
            for document in bots_documents:
                document.pop('_id')
                result.append(document)

            return await make_response(jsonify(result), 200)
        else:
            return await make_response(jsonify(message = 'An error occurred: bots for this company doesn\'t exist'), 400)
            
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
        
@bots_bp.route('/create', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def create():
    try:  
        data = await request.form

        if not data.get('name'):
            return await make_response(jsonify(message="An error occurred: missing 'name' parameter"), 400)
        elif not data.get('timeout'):
            return await make_response(jsonify(message="An error occurred: missing 'timeout' parameter"), 400)
        if not data.get('strict_flow'):
            return await make_response(jsonify(message = "An error occurred: missing 'strict_flow' parameter"), 400)
        
        name, timeout, strict_flow = data.get('name'), data.get('timeout'), data.get('strict_flow')

        if not strict_flow == '1' and not strict_flow == '0':
            return await make_response(jsonify(message = "An error occurred: invalid 'strict_flow' parameter"), 400) 

        if not timeout.isdigit():
            return await make_response(jsonify(message="An error occurred: invalid 'timeout' parameter"), 400)
        
        name = process_name(name, 1)

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        process_collections = db['process']  
        nlu_collections = db['nlu']
        domain_collection = db['domain']
        rules_collections = db['rules']
        stories_collections = db['stories']
        generative_collections = db['generative']
        entities_collections = db['entities']
        slots_collections = db['slots']
        actions_collections = db['actions']

        bots_document = await bots_collections.find_one({"name": name, "is_active": 1})

        if bots_document:
            return await make_response(jsonify(message='An error occurred: bot name already exists'), 400)
        
        latest_process = await process_collections.find_one({"is_active": 1, 'type': 'creating bot'}, sort=[("_id", pymongo.DESCENDING)])
        if latest_process:
            return await make_response(jsonify(message='An error occurred: an unexpected error occured'), 400)

        bots_record = await bots_collections.find_one(sort=[("_id", pymongo.DESCENDING)])
        if bots_record:
            rasa_port = int(bots_record['rasa_port']) + 1
            function_port = int(bots_record['function_port']) + 1
            bot_id = str(int(bots_record['bot_id'])+1)

        else:
            rasa_port = 4001
            function_port = 14001
            bot_id = str(1)

        now = datetime.now()
        date_time = now.strftime("%d/%m/%Y %H:%M:%S")
            
        document = {'company_id': company_id, 'bot_id': bot_id, 'is_process': 1, 'type': 'creating bot', 'created_date': date_time, 'created_by': user}
        await process_collections.insert_one(document)

        time.sleep(1) 

        domain_json = {'version': '3.1',
            'intents': ['start_message', 'invalid_character_input', 'previous_step_option', 'restart_conversation_option'],
            'actions': ['action_previous', 'action_fallback'],
            'responses': {'utter_fallback': [{'text': "Sorry I didn't get that. Can you rephrase?"}],
            'utter_restart': [{'text': 'Say hi to begin conversation!'}],
            'utter_welcome': [{'text': 'Say hi to begin conversation!'}],
            'utter_default': [{'text': "Sorry I didn't get that. Can you rephrase?"}]},
            'session_config': {'session_expiration_time': int(timeout),
            'carry_over_slots_to_new_session': False}}
        
        nlu_json = {'version': '3.1',
            'nlu': [{'intent': 'start_message',
            'examples': '- start the conversation\n- start the conversation\n- start the conversation\n'},
            {'intent': 'previous_step_option',
            'examples': '- * for Previous\n- * for Previous\n- * for Previous\n'},
            {'intent': 'invalid_character_input',
            'examples': '- invalid character input\n- invalid character input\n- invalid character input\n'},
            {'intent': 'restart_conversation_option',
            'examples': '- # for Restart\n- # for Restart\n- # for Restart\n'}]}
        
        rules_json = {'version': '3.1',
            'rules': [
            {'rule': 'Ignore any starting message to display the first menu',
             'conversation_start': True,
            'steps': [{'intent': 'start_message'}, {'action': 'utter_welcome'}]}, 
            {'rule': 'Ask the user to rephrase whenever they send a message with low NLU confidence',
            'steps': [{'intent': 'nlu_fallback'}, {'action': 'utter_fallback'}, {'action': 'action_fallback'}]},
            {'rule': 'Invalid number or character is input',
            'steps': [{'intent': 'invalid_character_input'}, {'action': 'utter_fallback'}, {'action': 'action_fallback'}]},
            {'rule': 'Jump to previous step',
            'steps': [{'intent': 'previous_step_option'}, {'action': 'action_previous'}]},
            {'rule': 'Restart conversation',
            'steps': [{'intent': 'restart_conversation_option'}, {'action': 'action_restart'}]}]}
                    
        stories_json = {'version': '3.1', 'stories': None}

        entities_json = {'entities': None}

        slots_json = {'slots': None}

        actions_json = {'actions': 'from typing import Any, Text, Dict, List\nfrom rasa_sdk import Action, Tracker\nfrom rasa_sdk.executor import CollectingDispatcher\nfrom rasa_sdk.events import FollowupAction, UserUtteranceReverted\n\nclass ActionPrevious(Action):\n\n    def name(self) -> Text:\n        return "action_previous"\n\n    async def run(self, dispatcher: CollectingDispatcher,\n            tracker: Tracker,\n            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:       \n\n        count = 1\n        for event in tracker.events[::-1]:\n            if event[\'event\'] == \'action\' and \'action_listen\' not in event[\'name\'] and \'action_back\' not in event[\'name\'] and \'action_fallback\' not in event[\'name\'] and \'utter_fallback\' not in event[\'name\'] and \'action_default_fallback\' not in event[\'name\']:\n                if event[\'name\'] == \'action_previous\':\n                    count += 1\n                    continue\n\n                if count == 0:\n                    dispatcher.utter_message(text = domain[\'responses\'][event[\'name\']][0][\'text\'])\n                    return [FollowupAction(\'action_back\')]\n                else:\n                    count -= 1\n                    \n        return [FollowupAction(\'action_restart\')]\n    \nclass ActionFallback(Action):\n\n    def name(self) -> Text:\n        return "action_fallback"\n\n    async def run(self, dispatcher: CollectingDispatcher,\n            tracker: Tracker,\n            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:    \n        \n        return [UserUtteranceReverted()] '}

        now = datetime.now()
        date_time = now.strftime("%d/%m/%Y %H:%M:%S")

        augment_prompt = "I am creating an AI chat bot and I need examples of intents to train the bot.\nI'll provide one intent and you'll need to provide a list of 10 examples of same intent.\nYou can augment or rephrase the intent but the sense of the intent should remain same.\nReturn the examples only, do not add any prefix or numbering."
        
        document = {'company_id': company_id, 'bot_id': bot_id, 'augment_prompt': augment_prompt, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
        await generative_collections.insert_one(document)

        document = {'company_id': company_id, 'bot_id': bot_id, 'name': name, 'rasa_port': rasa_port, 'function_port': function_port, 'timeout': int(timeout), 'strict_flow': strict_flow, 'is_run': 0, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
        await bots_collections.insert_one(document)
        
        document = {'company_id': company_id, 'bot_id': bot_id, 'data': actions_json, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
        await actions_collections.insert_one(document)

        document = {'company_id': company_id, 'bot_id': bot_id, 'data': nlu_json, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
        await nlu_collections.insert_one(document)

        document = {'company_id': company_id, 'bot_id': bot_id, 'data': domain_json, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
        await domain_collection.insert_one(document)

        document = {'company_id': company_id, 'bot_id': bot_id, 'data': rules_json, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
        await rules_collections.insert_one(document)

        document = {'company_id': company_id, 'bot_id': bot_id, 'data': stories_json, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
        await stories_collections.insert_one(document)

        document = {'company_id': company_id, 'bot_id': bot_id, 'is_process': 0, 'type': 'creating bot', 'created_date': date_time, 'created_by': user}
        await process_collections.insert_one(document)

        document = {'company_id': company_id, 'bot_id': bot_id, 'data': entities_json, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
        await entities_collections.insert_one(document)

        document = {'company_id': company_id, 'bot_id': bot_id, 'data': slots_json, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
        await slots_collections.insert_one(document)

        return await make_response(jsonify(message='Bot has been created!'), 200)

    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)

@bots_bp.route('/deactivate', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def deactivate():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message="An error occurred: missing 'bot_id' parameter"), 400)
        
        bot_id = data.get('bot_id')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        process_collections = db['process']  

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 0})

        if bots_record:
            return await make_response(jsonify(message = f'An error occurred: bot id is already deactived'), 400)

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])

            if latest_process['is_process'] == 0:

                    now = datetime.now()
                    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"is_active": 0}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                    return await make_response(jsonify(message = 'Bot has been deactivated!'), 200)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)   

    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
    
@bots_bp.route('/activate', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def activate():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message="An error occurred: missing 'bot_id' parameter"), 400)
        
        bot_id = data.get('bot_id')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        process_collections = db['process']  

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            return await make_response(jsonify(message = f'An error occurred: bot id is already active'), 400)

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 0})

        if bots_record:
            
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])

            if latest_process['is_process'] == 0:

                    now = datetime.now()
                    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"is_active": 1}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})
                    
                    return await make_response(jsonify(message = 'Bot has been activated!'), 200)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)

    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)