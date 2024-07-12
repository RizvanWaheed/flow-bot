import string, pymongo, os, re, requests
from datetime import datetime, timedelta
from quart import Blueprint, request, jsonify, make_response
from functions.utilities import connect, number_to_option
from decorators.teams import x_super_team
from decorators.key import x_app_key
from decorators.jwt import jwt_token

punc = string.punctuation

chats_bp = Blueprint('chats', __name__)

@chats_bp.route('/chat', methods=['POST'])
@x_super_team
@x_app_key
async def chat():
    if request.method == 'POST':
        try:
            data = await request.form

            if not data.get('bot_id'):
                return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
            if not data.get('message'):
                return await make_response(jsonify(message = "An error occurred: missing 'message' parameter"), 400)
            if not data.get('sender_id'):
                return await make_response(jsonify(message = "An error occurred: missing 'sender_id' parameter"), 400)
            if not data.get('token'):
                return await make_response(jsonify(message = "An error occurred: missing 'token' parameter"), 400)
            
            bot_id, message, sender_id, token = data.get('bot_id'), data.get('message'), data.get('sender_id'), data.get('token')

            company_id = request.headers.get('x-super-team')

            temp_punc = punc.replace('*', '').replace('#', '')
            message = message.translate(str.maketrans('', '', temp_punc)).strip()
            message = ' '.join(message.split())

            db = await connect()

            bots_collections = db['bots']
            domain_collections = db['domain']
            process_collections = db['process']
            tokens_collections = db['tokens']

            user_message = message

            bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

            if bots_record:
                latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])

                if os.path.exists(f'bots/{company_id}/{bot_id}'):
                    if os.path.isdir(f'bots/{company_id}/{bot_id}/models'):
                        if latest_process['is_process'] == 1 and latest_process['type'] == 'running':
                            rasa_port = bots_record['rasa_port']
                            rasa_url = f"http://localhost:{rasa_port}/webhooks/rest/webhook"

                            token_record = await tokens_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})
                            if token_record:
                                stored_token = token_record['data']['token']
                                if token != stored_token:
                                    return await make_response(jsonify(message = "An error occurred: invalid token"), 400)

                                now = datetime.now()
                                date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                                date_format = "%d/%m/%Y %H:%M:%S"
                                created_date = datetime.strptime(date_time, date_format)
                                expiry_date = datetime.strptime(token_record['data']['expiry_date'], date_format)

                                if expiry_date < created_date:
                                    return await make_response(jsonify(message = "An error occurred: token has expired"), 400) 
                            else:
                                return await make_response(jsonify(message = "An error occurred: no token exist\'s for the bot"), 400)
                        
                            db_bot = await connect(bots_record['name'])
                            message_collections = db_bot['conversations']
                            chat_history_collections = db_bot['chat_history']

                            conversation_records = await message_collections.find_one({"sender_id": sender_id})
                            domain_records = await domain_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

                            if conversation_records:
                                last_timestamp = conversation_records['latest_event_time']
                                sender_id = conversation_records['sender_id']

                                current_datetime  = datetime.now()
                                last_timestamp = datetime.fromtimestamp(last_timestamp)
                                last_timestamp = last_timestamp + timedelta(minutes = int(bots_record['timeout']))

                                if last_timestamp < current_datetime:
                                    message = '/restart'
                                else:
                                    for record in conversation_records['events'][::-1]:
                                        if record['event'] == 'bot':
                                            if domain_records['data']['responses']['utter_fallback'][0]['text'] != record['text'] or domain_records['data']['responses']['utter_default'][0]['text'] != record['text']:
                                                bot_response = record['text']
                                                break
                                        
                                    numbers = re.findall(r'\d+', message)
                                    special_characters = re.findall(r'[^a-zA-Z0-9\s\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]', message)
                                    if numbers and special_characters:
                                        message = 'invalid character input'
                                    else:
                                        if len(numbers) > 1 or len(special_characters) > 1: 
                                            message = 'invalid character input'
                                        else:
                                            if numbers:
                                                message = number_to_option(bot_response, numbers[0]) 
                                            elif special_characters:
                                                message = number_to_option(bot_response, special_characters[0]) 
                            else:
                                message = 'start the conversation'

                            rasa_response = requests.post(rasa_url, json={"sender": sender_id, "message": message})
                            response_dict = rasa_response.json()

                            if response_dict:
                                response = []
                                for temp in response_dict:
                                    response.append(temp['text'])

                                response = '\n\n'.join(response)

                                if response == domain_records['data']['responses']['utter_fallback'][0]['text'] or response == domain_records['data']['responses']['utter_default'][0]['text']:
                                    response = response + '\n\n' + bot_response
                            else:
                                response = domain_records['data']['responses']['utter_fallback'][0]['text']

                            now = datetime.now()
                            date_time = now.strftime("%d/%m/%Y %H:%M:%S")
                            document = {'sender_id': sender_id, 'timestamp': date_time, 'token': token, 'user': user_message, 'bot': response}
                            chat_history_collections.insert_one(document)
                            
                            return await make_response(jsonify(message = response), 200)
                        else:
                            return await make_response(jsonify(message = f'An error occurred: bot is not running at the moment'), 400)
                    else:
                        return await make_response(jsonify(message = f'An error occurred: train the bot before running it.'), 400)   
                else:    
                    return await make_response(jsonify(message = f'An error occurred: create data before running the bot'), 400)
            else:    
                return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)
        
        except Exception as e:
            if 'No connection could be made because the target machine actively refused it' in str(e) or 'Failed to establish a new connection:' in str(e):
                return await make_response(jsonify(message = f"An error occurred: wait for the bot to start"), 400)
            else:
                return await make_response(jsonify(message = f"An error occurred: {str(e)}"), 500)
            
@chats_bp.route('/delete', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def delete():
    if request.method == 'POST':
        try:     
            data = await request.form

            if not data.get('bot_id'):
                return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400) 

            bot_id = data.get('bot_id')
            
            company_id = request.headers.get('x-super-team')

            db = await connect()

            bots_collections = db['bots']
            bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

            if bots_record:    
                db = await connect(database = bots_record['name'])
                conversations_collections = db['conversations']

                conversation_records = await conversations_collections.find().to_list(length=None)

                if conversation_records:

                    enteries = 0
                    for records in conversation_records:
                        last_timestamp = records['latest_event_time']
                        sender_id = records['sender_id']

                        current_datetime  = datetime.now()
                        last_timestamp = datetime.fromtimestamp(last_timestamp)
                        last_timestamp = last_timestamp + timedelta(minutes = int(bots_record['timeout']))

                        if last_timestamp < current_datetime:
                            enteries += 1
                            await conversations_collections.delete_one({'sender_id': sender_id})

                    if enteries:
                        return await make_response(jsonify(message = f'{enteries} enteries has been deleted'), 200)
                    else:
                        return await make_response(jsonify(message=f'An error occurred: no enteries exist to delete'), 400)
                else:
                    return await make_response(jsonify(message = f'An error occurred: no conversation enteries found'), 400)
            else:    
                return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)

        except Exception as e:
            if 'No connection could be made because the target machine actively refused it' in str(e):
                return await make_response(jsonify(message = f"An error occurred: wait for the bot to start"), 400)
            else:
                return await make_response(jsonify(message = f"An error occurred: {str(e)}"), 500)
