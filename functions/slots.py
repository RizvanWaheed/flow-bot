import pymongo
from datetime import datetime, timedelta
from quart import Blueprint, request, jsonify, make_response, g
from functions.utilities import connect, process_name
from decorators.teams import x_super_team
from decorators.key import x_app_key
from decorators.jwt import jwt_token

slots_bp = Blueprint('slots', __name__)

@slots_bp.route('/get', methods=['GET'])
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
        slots_collections = db['slots']

        bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

        if bots_record:
            slots_record = await slots_collections.find_one({"company_id": company_id,"bot_id": bot_id, "is_active": 1})
        
            if slots_record:
                if slots_record['data']['slots'] == 'null' or slots_record['data']['slots']:
                    slots_record.pop('_id')
                    return await make_response(jsonify(slots_record['data']), 200)
                else:
                    return await make_response(jsonify(message = f'An error occurred: no slots exist for this bot'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
        else:
            return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)  
            
    except Exception as e:
        return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)

@slots_bp.route('/create', methods=['POST'])
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
            if not data.get('type'):
                return await make_response(jsonify(message = "An error occurred: missing 'type' parameter"), 400)
            if not data.get('mapping_type'):
                return await make_response(jsonify(message = "An error occurred: missing 'mapping_type' parameter"), 400)        
            
            # if not data.get('influence'):
            #     influence = False
            # else:
            #     influence = data.get('influence')

            # if influence != 'True' and influence != 'False':
            #     return await make_response(jsonify(message = "An error occurred: invalid 'influence' parameter"), 400)
            # elif influence == 'True':
            #     influence = True
            # elif influence == 'False':
            #     influence = False
            
            if not data.get('initial'):
                initial = None
            else:
                initial = data.get('initial')

            bot_id, name, type, entity, mapping_type = data.get('bot_id'), data.get('name'), data.get('type'), data.get('entity'), data.get('mapping_type')

            company_id = request.headers.get('x-super-team')
            user = g.current_user

            name = process_name(name, 1)
                
            db = await connect()

            bots_collections = db['bots']
            slots_collections = db['slots']
            entities_collections = db['entities']
            process_collections = db['process']
            domain_collections = db['domain']

            bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

            if bots_record:
                latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
                
                if latest_process['is_process'] == 0:
                    slots_record = await slots_collections.find_one({"bot_id": bot_id, "is_active": 1})
                    domain_record = await domain_collections.find_one({"bot_id": bot_id, "is_active": 1})
                    entity_record = await entities_collections.find_one({"bot_id": bot_id, "is_active": 1})
                        
                    if slots_record:
                        slot = slots_record['data']
                        domain = domain_record['data']
                        entities = entity_record['data']

                        if slot['slots']:
                            for temp in slot['slots']:
                                if temp == name:
                                    return await make_response(jsonify(message = f'An error occurred: duplicate slot name found'), 200)
                                
                        if type == 'categorical':
                            if not data.get('categorical'):
                                return await make_response(jsonify(message = "An error occurred: missing 'categorical' parameter"), 400)
                            else:
                                categories = data.getlist('categorical')

                            if slot['slots']:
                                slot['slots'].update({name: {'type': type, 'initial_value': initial, 'values': categories}})
                            else:
                                slot['slots'] = {name: {'type': type, 'initial_value': initial, 'values': categories}}
                        
                        elif type.lower() == 'float':
                            if not data.get('float_min'):
                                return await make_response(jsonify(message = "An error occurred: missing 'float_min' parameter"), 400)
                            else:
                                float_min = data.get('float_min')

                            if not data.get('float_max'):
                                return await make_response(jsonify(message = "An error occurred: missing 'float_max' parameter"), 400)
                            else:
                                float_max = data.get('float_max')
                                
                            if slot['slots']:
                                slot['slots'].update({name: {'type': type, 'initial_value': initial, 'min_value': float_min, 'max_value': float_max}})  
                            else:
                                slot['slots'] = {name: {'type': type, 'initial_value': initial, 'min_value': float_min, 'max_value': float_max}}  

                        elif type == 'text' or type == 'bool':
                            if slot['slots']:
                                slot['slots'].update({name: {'type': type, 'initial_value': initial}})
                            else:
                                slot['slots'] = {name: {'type': type, 'initial_value': initial}}   

                        else:     
                            return await make_response(jsonify(message = "An error occurred: invalid 'type' parameter"), 400)
                        
                        if mapping_type == 'from_entity': 

                            if not data.get('entity'):
                                return await make_response(jsonify(message = "An error occurred: missing 'entity' parameter"), 400)    

                            found = 0    
                            if entities['entities']:
                                for temp in entities['entities']:
                                    if temp == entity:
                                        found = 1
                                
                            if not found:
                                return await make_response(jsonify(message = f'An error occurred: entity doesn\'t exist'), 200)
                            
                            slot['slots'][name].update({'mappings': [{'type': 'from_entity', 'entity': entity}]})

                        elif mapping_type == 'custom':
                            slot['slots'][name].update({'mappings': [{'type': 'custom'}]})

                        domain['slots'] = slot['slots']
                        
                        now = datetime.now()
                        date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                        await slots_collections.update_one({"_id": slots_record["_id"]}, {"$set": {"is_active": 0}})
                        await slots_collections.update_one({"_id": slots_record["_id"]}, {"$set": {"modified_date": date_time}})
                        await slots_collections.update_one({"_id": slots_record["_id"]}, {"$set": {"modified_by": user}})

                        await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"is_active": 0}})
                        await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_date": date_time}})
                        await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_by": user}})

                        await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                        await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                        document = {'company_id': company_id, 'bot_id': bot_id, 'data': slot, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                        await slots_collections.insert_one(document)

                        document = {"company_id": company_id, 'bot_id': bot_id, 'data': domain, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                        await domain_collections.insert_one(document)

                        return await make_response(jsonify(message = f'Slot has been created for the bot'), 200)
                    else:
                        return await make_response(jsonify(message = f'An error occurred: an unexpected error occured'), 400)
                else:
                    return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)   
                
        except Exception as e:
            return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)
                                     
@slots_bp.route('/delete', methods=['POST'])
@x_super_team
@x_app_key
@jwt_token
async def delete():
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
                
            db = await connect()

            bots_collections = db['bots']
            slots_collections = db['slots']
            process_collections = db['process']
            domain_collections = db['domain']

            bots_record = await bots_collections.find_one({"company_id": company_id, "bot_id": bot_id, "is_active": 1})

            if bots_record:
                latest_process = await process_collections.find_one({"company_id": company_id, "bot_id": bot_id}, sort=[("_id", pymongo.DESCENDING)])
                
                if latest_process['is_process'] == 0:
                    slots_record = await slots_collections.find_one({"bot_id": bot_id, "is_active": 1})
                    domain_record = await domain_collections.find_one({"bot_id": bot_id, "is_active": 1})
                        
                    if slots_record:
                        slot = slots_record['data']
                        domain = domain_record['data']
                        
                        remove = 0
                        for ent in slot['slots']:
                            if ent == name:
                                remove = 1

                        if not remove:
                            return await make_response(jsonify(message=f'An error occurred: slot doesn\'t exist.'), 400)    
                        else:
                            del slot['slots'][ent]
                    else:
                        return await make_response(jsonify(message='An error occurred: no slots exists for this bot'), 400)    
                    
                    domain['slots'] = slot['slots']

                    now = datetime.now()
                    date_time = now.strftime("%d/%m/%Y %H:%M:%S")

                    await slots_collections.update_one({"_id": slots_record["_id"]}, {"$set": {"is_active": 0}})
                    await slots_collections.update_one({"_id": slots_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await slots_collections.update_one({"_id": slots_record["_id"]}, {"$set": {"modified_by": user}})

                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"is_active": 0}})
                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await domain_collections.update_one({"_id": domain_record["_id"]}, {"$set": {"modified_by": user}})

                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_date": date_time}})
                    await bots_collections.update_one({"_id": bots_record["_id"]}, {"$set": {"modified_by": user}})

                    document = {'company_id': company_id, 'bot_id': bot_id, 'data': slot, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await slots_collections.insert_one(document)

                    document = {"company_id": company_id, 'bot_id': bot_id, 'data': domain, 'is_active': 1, 'created_date': date_time, 'modified_date': date_time, 'created_by': user, 'modified_by': user}
                    await domain_collections.insert_one(document)

                    return await make_response(jsonify(message=f'Slot has been deleted for the bot!'), 200)       
                else:
                    return await make_response(jsonify(message = f'An error occurred: bot is {latest_process["type"]} at the moment'), 400)
            else:
                return await make_response(jsonify(message = f'An error occurred: bot doesn\'t exist'), 400)   

        except Exception as e:
            return await make_response(jsonify(message=f"An error occurred: {str(e)}"), 500)