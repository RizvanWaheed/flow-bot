import pymongo
from datetime import datetime
from quart import Blueprint, request, jsonify, make_response, g
from functions.utilities import connect, process_name
from decorators.teams import x_super_team
from decorators.key import x_app_key
from decorators.jwt import jwt_token

entities_bp = Blueprint('entities', __name__)

@entities_bp.route('/get', methods=['GET'])
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
        entities_collections = db['entities']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            entity_record = await entities_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
        
            if entity_record:
                if entity_record['data']['entities'] == 'null' or entity_record['data']['entities']:
                    entity_record.pop('_id')
                    return await make_response(jsonify(entity_record['data']), 200)
                else:
                    return await make_response(jsonify(message = f'An error occurred: no entities exist for this bot'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)  
            
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)

@entities_bp.route('/create', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def create():
    if request.method == 'POST':
        try:
            data = await request.form

            if not data.get('bot_id'):
                return await make_response(jsonify(message = "An error occurred: missing 'bot_id' parameter"), 400)
            if not data.get('name'):
                return await make_response(jsonify(message = "An error occurred: missing 'name' parameter"), 400)
            
            bot_id, name = data.get('bot_id'), data.get('name')

            company_id = request.headers.get('x-super-team')
            user = g.current_user

            name = process_name(name, 1)
                
            db = await connect()

            bots_collections = db['bots']
            entities_collections = db['entities']
            process_collections = db['process']
            domain_collections = db['domain']

            bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

            if bots_record:
                latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
                
                if latest_process['is_process'] == 0:
                    entity_record = await entities_collections.find_one({"bot_id": bot_id, "is_active": 1})
                    domain_record = await domain_collections.find_one({"bot_id": bot_id, "is_active": 1})
                        
                    if entity_record:
                        entity = entity_record['data']
                        domain = domain_record['data']

                        if entity['entities']:
                            found = 0
                            for ent in entity['entities']:
                                if ent == name:
                                    found = 1

                            if found:
                                return await make_response(jsonify(message = f'An error occurred: duplicate entity name found'), 200)
                            
                            entity['entities'].append(name)
                        else:
                            entity['entities'] = [name]

                        domain['entities'] = entity['entities']

                        now = datetime.now()
                        date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                        await entities_collections.update_one({"_id": entity_record["_id"]}, {"$set": {"is_active": 0}})
                        await entities_collections.update_one({"_id": entity_record["_id"]}, {"$set": {"modified_date": date_time}})
                        await entities_collections.update_one({"_id": entity_record["_id"]}, {"$set": {"modified_by": user}})

                        await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"is_active": 0}})
                        await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_date": date_time}})
                        await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_by": user}})

                        await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                        await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                        document = {'company_id': company_id, 'bot_id': bot_id, 'data': entity, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                        entities_collections.insert_one(document)

                        document = {"company_id": company_id, 'bot_id': bot_id, 'data': domain, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                        await domain_collections.insert_one(document)

                        return await make_response(jsonify(message = f'Entity has been created for the bot'), 200)
                    else:
                        return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
                else:
                    return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)   
            
        except Exception as e:
            return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
     
@entities_bp.route('/delete', methods=['POST'])
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
        entities_collections = db['entities']
        process_collections = db['process']
        domain_collections = db['domain']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
            
            if latest_process['is_process'] == 0:
                entity_record = await entities_collections.find_one({"bot_id": bot_id, "is_active": 1})
                domain_record = await domain_collections.find_one({"bot_id": bot_id, "is_active": 1})
                    
                if entity_record:
                    entity = entity_record['data']
                    domain = domain_record['data']

                    if entity['entities']:
                        remove = 0
                        for ent in entity['entities']:
                            if ent == name:
                                entity['entities'].remove(ent)
                                domain['entities'].remove(ent)
                                remove = 1

                        if not remove:
                            return await make_response(jsonify(message=f'An error occurred: entity doesn\'t exist.'), 400)    
                    else:
                        return await make_response(jsonify(message='An error occurred: no entities exists for this bot'), 400) 

                    domain['entities'] = entity['entities']

                    now = datetime.now()
                    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                    await entities_collections.update_one({"_id": entity_record["_id"]}, {"$set": {"is_active": 0}})
                    await entities_collections.update_one({"_id": entity_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await entities_collections.update_one({"_id": entity_record["_id"]}, {"$set": {"modified_by": user}})

                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"is_active": 0}})
                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_by": user}})

                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                    document = {'company_id': company_id, 'bot_id': bot_id, 'data': entity, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    entities_collections.insert_one(document)

                    document = {"company_id": company_id, 'bot_id': bot_id, 'data': domain, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await domain_collections.insert_one(document)

                    return await make_response(jsonify(message=f'Entity has been deleted for the bot!'), 200)       
                else:
                    return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)   

    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
