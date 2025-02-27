from celery import group, chord
from flask_socketio import emit, join_room
from flask import request, current_app
import re
from pathlib import Path
from typing import Optional

from app import socketio
# from services.tasks import retrieve_conversation_from_cache, retrieve_passages_task, process_and_emit, delete_conversation_from_cache

from autogpt.app.main import run_auto_gpt

conversations = {}
default_messages = [
    {"role": "system", "content": "You're 'Romeo,' the IT Consortium chatbot, here to answer "+
                               " questions about our services. You'll get more info denoted by 'Context:' for "+
                                "better replies. Use a friendly tone. For greetings like 'Hi/What's up/Yo'"+
                                "respond as if starting fresh: Without Context. "+
                                "Ignore 'Context:' for greetings."},
]

def authenticate_user(request):
    # TODO: implement authentication
    pass

def get_user_from_session():
    return request.sid

def validate_chat_data(json):
    required_fields = ['message']
    errors = []
    for field in required_fields:
        if field not in json or json.get(field) == None or json.get(field) == "":
            errors.append(f"{field} is required")
        else:
            if field in ['index'] and not isinstance(json[field], str):
                errors.append(f"{field} must be a string")
            if field in ['size'] and not isinstance(json[field], int):
                errors.append(f"{field} must be an integer")
    return errors

# def update_conversation_history(conversation_id, message, default_messages=default_messages, summary=False):
#     if conversation_id not in conversations:
#         conversations[conversation_id] = default_messages.copy()

#     if summary:
#         new_conversation = default_messages.copy() + [message]
#         conversations[conversation_id] = new_conversation
#     else:
#         conversations[conversation_id].append(message)

# def summary(conversation_id):
#          summarized_text = summarize_conversation_t5(conversations.get(conversation_id, []))
#          if summarized_text:
#             new_default_messages = [
#                         {"role": "system", "content": "You're 'Romeo,' the IT Consortium chatbot, here to answer "+
#                                                     " questions about our services. You'll get more info denoted by 'Context:' for "+
#                                                         "better replies. Use a friendly tone. For greetings like 'Hi/What's up/Yo'"+
#                                                         "respond as if starting fresh: Without Context. "+
#                                                         "Ignore 'Context:' for greetings. If unsure about names, ask for clarity."},
#                         ]
#             update_conversation_history(conversation_id, summarized_text, new_default_messages, True)





@socketio.on('connect')
def handle_connect():
    current_app.logger.info("Connected")
    user = authenticate_user(request)
    conversation_id = user.conversation_id if user else get_user_from_session()
    join_room(conversation_id)

    # Extract messages from the request
    settings = {
        'continuous': request.args.get('continuous', type=bool),
        'continuous_limit': request.args.get('continuous_limit', type=int),
        'ai_settings': request.args.get('ai_settings', type=str),
        'prompt_settings': request.args.get('prompt_settings', type=str),
        'skip_reprompt': request.args.get('skip_reprompt', type=bool),
        'speak': request.args.get('speak', type=bool),
        'debug': request.args.get('debug', type=bool),
        'gpt3only': request.args.get('gpt3only', type=bool),
        'gpt4only': request.args.get('gpt4only', type=bool),
        'memory_type': request.args.get('memory_type', type=str),
        'browser_name': request.args.get('browser_name', type=str),
        'allow_downloads': request.args.get('allow_downloads', type=bool),
        'skip_news': request.args.get('skip_news', type=bool),
        # 'working_directory': Path(request.args.get('working_directory', type=str)),
        'workspace_directory': request.args.get('workspace_directory', type=lambda x: Path(x) if x else x),
        'install_plugin_deps': request.args.get('install_plugin_deps', type=bool),
        'ai_name': request.args.get('ai_name', default=None, type=str),
        'ai_role': request.args.get('ai_role', default=None, type=str),
        'ai_goals': tuple(request.args.getlist('ai_goals', type=str)),
    }
    run_auto_gpt(**settings)



# @socketio.on('chat')
# def handle_client_message(json):
#     errors = validate_chat_data(json)
#     if errors:
#         emit('error', {'error': "Validation errors: " + ", ".join(errors)}, room=json.get('connection_id', ''))
#         return
#     current_app.logger.info(f"Got chat: {json}")
#     conversation_id = json.get('connection_id', "")
#     user_message = json['message']

    # # Retrieve and prepare the message
    # index = json.get('index', 'search-chatbot-final')
    # size = json.get('size', 2)
    # chunks, retrieved_passage = retrievePassages(index, size, [user_message])
    # emit('chunks_retrieved', {'chunks': chunks}, room=conversation_id)
    # message = {"role": "user", "content": user_message + ". Context: " + retrieved_passage}

    # update_conversation_history(conversation_id, message)
    # emit('typing_indicator', {'status': True}, room=conversation_id)

#     @copy_current_request_context
#     def process_message():
#         try:
#             response = ask_gpt4(conversations.get(conversation_id, default_messages))
#             update_conversation_history(conversation_id, response)
#             emit('typing_indicator', {'status': False}, room=conversation_id)
#             emit('message_from_llm', {'message': response["content"]}, room=conversation_id)
#             summary(conversation_id)
#         except Exception as e:
#             current_app.logger.error(f"Error processing message: {e}")
#             emit('error', {'error': "An error occurred while processing message"}, room=conversation_id)

#     threading.Thread(target=process_message).start()

# In your Flask-SocketIO event handling file


from celery import group, chord

def initiate_retrieval_and_processing(conversation_id, index, size, user_message, models):
    tasks = [retrieve_conversation_from_cache.s(conversation_id)]

    if index:
        tasks.append(retrieve_passages_task.s(conversation_id, index, size, user_message))

    header = group(*tasks)

    callback = process_and_emit.s(conversation_id=conversation_id, user_message=user_message, models=models)

    chord(header)(callback)



@socketio.on('chat')
def handle_client_message(json):
    errors = validate_chat_data(json)
    if errors:
        emit('error', {'error': "Validation errors: " + ", ".join(errors)}, room=json.get('connection_id', ''))
        return
    current_app.logger.info(f"Got chat: {json}")
    conversation_id = get_user_from_session()
    user_message = json['message']
    models = json.get('models', ['gpt4'])
    index = json.get('index', '')
    if index:
        index =  'search-'+re.sub(r'[\s/]+', '-', index).strip().lower()
    size = json.get('size', 2)
    

    initiate_retrieval_and_processing(conversation_id, index, size, user_message, models)


@socketio.on('disconnect')
def handle_disconnect():
    user = get_user_from_session()
    if user:
        delete_conversation_from_cache.delay(user)
        current_app.logger.info(f"Deleted conversation for {user}")
