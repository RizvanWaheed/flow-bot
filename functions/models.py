import subprocess, shutil, os, yaml, psutil, pymongo
from datetime import datetime
from decouple import config
from quart import Blueprint, request, jsonify, make_response, g
from functions.utilities import connect
from decorators.teams import x_super_team
from decorators.key import x_app_key
from decorators.jwt import jwt_token

models_bp = Blueprint('models', __name__)

username = config("DATABASE_USERNAME")
password = config("DATABASE_PASSWORD")
        
@models_bp.route('/train', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def train():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        
        bot_id = data.get('bot_id')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        nlu_collections = db['nlu']
        process_collections = db['process']
        domain_collections = db['domain']
        stories_collections = db['stories']
        rules_collections = db['rules']
        actions_collections = db['actions']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 0:
                nlu_record = await nlu_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})
                domain_record = await domain_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})             
                stories_record = await stories_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})                    
                rules_record = await rules_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})
                actions_record = await actions_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})
                    
                if nlu_record and domain_record and stories_record and rules_record and actions_record:   
                    nlu, domain, stories, rules, actions = nlu_record['data'], domain_record['data'], stories_record['data'], rules_record['data'], actions_record['data']

                    if not domain['intents']:
                        return await make_response(jsonify(message='An error occurred: no intents exists for this bot'), 400)
                    
                    if not domain['responses']:
                        return await make_response(jsonify(message='An error occurred: no response exists for this bot'), 400)

                    if not os.path.exists(f'bots/{company_id}/{bot_id}'):
                        os.makedirs(f'bots/{company_id}/{bot_id}/data')   

                    if bots_record['strict_flow'] == '1':     
                        config_json = {'recipe': 'default.v1',
                            'assistant_id': bots_record['name'],
                            'language': 'en',
                            'pipeline': [{'name': 'SpacyNLP', 'model': 'en_core_web_md', 'case_sensitive': False},
                            {'name': 'SpacyTokenizer'},
                            {'name': 'SpacyFeaturizer'},
                            {'name': 'RegexFeaturizer'},
                            {'name': 'LexicalSyntacticFeaturizer'},
                            {'name': 'CountVectorsFeaturizer', 'analyzer': 'char_wb', 'min_ngram': 1, 'max_ngram': 4},
                            {'name': 'DIETClassifier', 'epochs': 250, 'constrain_similarities': True},
                            {'name': 'SpacyEntityExtractor'},
                            {'name': 'FallbackClassifier', 'threshold': 0.7}],
                                'policies': [{'name': 'MemoizationPolicy'}, {'name': 'RulePolicy',
                                'core_fallback_threshold': 0.4,
                                'core_fallback_action_name': 'action_default_fallback',
                                'enable_fallback_prediction': True}]}
                        
                    elif bots_record['strict_flow'] == '0':
                        config_json = {'recipe': 'default.v1',
                            'assistant_id': bots_record['name'],
                            'language': 'en',
                            'pipeline': [{'name': 'SpacyNLP', 'model': 'en_core_web_md', 'case_sensitive': False},
                            {'name': 'SpacyTokenizer'},
                            {'name': 'SpacyFeaturizer'},
                            {'name': 'RegexFeaturizer'},
                            {'name': 'LexicalSyntacticFeaturizer'},
                            {'name': 'CountVectorsFeaturizer', 'analyzer': 'char_wb', 'min_ngram': 1, 'max_ngram': 4},
                            {'name': 'DIETClassifier', 'epochs': 250, 'constrain_similarities': True},
                            {'name': 'SpacyEntityExtractor'},
                            {'name': 'FallbackClassifier', 'threshold': 0.7}],
                                'policies': [{'name': 'MemoizationPolicy'}, {'name': 'RulePolicy',
                                'core_fallback_threshold': 0.4,
                                'core_fallback_action_name': 'action_default_fallback',
                                'enable_fallback_prediction': True}, {'name': 'TEDPolicy', 'epochs': 100}]}
                    
                    rasa_port = bots_record['rasa_port']
                    function_port = bots_record['function_port']

                    credentials_json = {'rest': None, 'rasa': {'url': f'http://localhost:{rasa_port}/api'}}

                    endpoints_json = {'action_endpoint': {'url': f'http://localhost:{function_port}/webhook'},
                        'tracker_store': {'type': 'mongod',
                        'url': 'mongodb://localhost:27017',
                        'db': bots_record['name'],
                        'username': username,
                        'password': password}}
                    
                    if not os.path.exists(f'bots/{company_id}/{bot_id}/actions'):
                        os.makedirs(f'bots/{company_id}/{bot_id}/actions') 

                    with open(f'bots/{company_id}/{bot_id}/actions/actions.py', 'w') as file:
                        file.write(actions['actions'])

                    with open(f'bots/{company_id}/{bot_id}/domain.yml', 'w') as file:
                        yaml.dump(domain, file, sort_keys=False)

                    with open(f'bots/{company_id}/{bot_id}/data/rules.yml', 'w') as file:
                        yaml.dump(rules, file, sort_keys=False)

                    with open(f'bots/{company_id}/{bot_id}/data/stories.yml', 'w') as file:
                        yaml.dump(stories, file, sort_keys=False)

                    with open(f'bots/{company_id}/{bot_id}/data/nlu.yml', 'w') as file:
                        yaml.dump(nlu, file, sort_keys=False)

                    with open(f'bots/{company_id}/{bot_id}/config.yml', 'w') as file:
                        yaml.dump(config_json, file, sort_keys=False)

                    with open(f'bots/{company_id}/{bot_id}/credentials.yml', 'w') as file:
                        yaml.dump(credentials_json, file, sort_keys=False)

                    with open(f'bots/{company_id}/{bot_id}/endpoints.yml', 'w') as file:
                        yaml.dump(endpoints_json, file, sort_keys=False)

                    path = f'bots/{company_id}/{bot_id}/models'

                    now = datetime.now()
                    date_time = now.strftime("%d/%m/%Y %H:%M:%S")
                    document = {'company_id': company_id, 'bot_id': bot_id, 'is_process': 1, 'type': 'training', 'created_date': date_time, 'created_by': user}
                    await process_collections.insert_one(document)

                    if os.path.exists(path):
                        shutil.rmtree(path)
                    prev_dir = os.getcwd()
                    os.chdir(f'bots/{company_id}/{bot_id}')
                    result = subprocess.run(['rasa', 'train'], capture_output=True, text=True)

                    os.chdir(prev_dir)

                    if result.returncode == 0:
                        now = datetime.now()
                        date_time = now.strftime("%d/%m/%Y %H:%M:%S")
                        document = {'company_id': company_id, 'bot_id': bot_id, 'is_process': 0, 'type': 'training', 'created_date': date_time, 'created_by': user}
                        await process_collections.insert_one(document)

                        return await make_response(jsonify(message = 'Bot has completed training'), 200)
                    else:
                        return await make_response(jsonify(message = f'An error occurred during training: {result.stderr}'), 400)
                else:
                    return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400) 
    
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)

@models_bp.route('/run', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def run():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        
        bot_id = data.get('bot_id')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        process_collections = db['process']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 0:
                function_port = bots_record['function_port']
                command = f'cd bots/{company_id}/{bot_id} && rasa run actions -p {function_port}'
                subprocess.Popen([command, '&'], shell=True)
                
                rasa_port = bots_record['rasa_port']
                command = f'cd bots/{company_id}/{bot_id} && rasa run -p {rasa_port}'
                subprocess.Popen([command, '&'], shell=True)

                now = datetime.now()
                date_time = now.strftime("%d/%m/%Y %H:%M:%S")
                document = {'company_id': company_id, 'bot_id': bot_id, 'is_process': 1, 'type': 'running', 'created_date': date_time, 'created_by': user}
                await process_collections.insert_one(document)

                await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})
                await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"is_run": 1}})

                return await make_response(jsonify(message = 'Bot has started running'), 200)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400) 
    
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)

@models_bp.route('/stop', methods=['GET', 'POST'])
@x_super_team
@x_app_key
@jwt_token
async def stop():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        
        bot_id = data.get('bot_id')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        process_collections = db['process']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 1 and latest_process['type'] == 'running':

                if os.path.exists(f'bots/{company_id}/{bot_id}'):
                    rasa_port = bots_record['rasa_port']
                    function_port = bots_record['function_port']

                    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):                        
                        if 'rasa' in proc.info['name'] and str(rasa_port) in proc.info['cmdline']:
                            proc.terminate()

                    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                        if 'rasa' in proc.info['name'] and str(function_port) in proc.info['cmdline']:
                            proc.terminate()

                    now = datetime.now()
                    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"is_run": 0}})

                    document = {'company_id': company_id, 'bot_id': bot_id, 'is_process': 0, 'type': 'running', 'created_date': date_time, 'created_by': user}
                    await process_collections.insert_one(document)
            
                    return await make_response(jsonify(message = 'Bot has stopped running'), 200)
                                
                else:
                    return await make_response(jsonify(message = 'An error occurred: create data before running the bot'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is not running at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)    
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
    
@models_bp.route('/status', methods=['GET', 'POST'])
@x_super_team
@x_app_key
@jwt_token
async def status():
    try:
        data = await request.form

        if not data.get('bot_id'):
            return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
        
        bot_id = data.get('bot_id')

        company_id = request.headers.get('x-super-team')
        user = g.current_user

        db = await connect()

        bots_collections = db['bots']
        process_collections = db['process']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 1 and latest_process['type'] == 'running':
                return await make_response(jsonify(message = 'Active'), 200)
            else:
                return await make_response(jsonify(message = 'Inactive'), 200)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)    
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)

