# import time
import random
from fastapi import FastAPI # type: ignore
from celery.result import AsyncResult
import os
from dotenv import load_dotenv # type: ignore
import requests
import json
from datetime import datetime
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler # type: ignore
import uvicorn # type: ignore
from tinydb import TinyDB, Query # type: ignore
from celery import Celery
from src.logger import logger
from src.chatgpt import ChatGPT, DALLE
from src.models import OpenAIModel
from src.tinder import TinderAPI
from src.dialog import Dialog

os.environ['TZ'] = 'Brazil/East'

load_dotenv()

models = OpenAIModel(api_key=os.getenv('OPENAI_API'), model_engine=os.getenv('OPENAI_MODEL_ENGINE'))

chatgpt = ChatGPT(models)
dalle = DALLE(models)
dialog = Dialog()

app = FastAPI()
scheduler = AsyncIOScheduler()

db = TinyDB('database/db.json')
maches_table = db.table('matches')
persons_table = db.table('persons')
profile_table = db.table('profile')

TINDER_TOKEN = os.getenv('TINDER_TOKEN')
OPENER_MESSAGE = os.getenv("GREETING_MESSAGE")

# Configure Celery
celery = Celery(
    __name__,
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

@celery.task(name='main.send_tinder_opener')
def send_tinder_opener(match_id, from_id, to_id, to_name):
    message = f'Oi {to_name}, como você é linda! Tudo bem com vc?'
    with open("openers.txt", "a") as file:
        file.write(f'\n {message}')
    tinder_api = TinderAPI(TINDER_TOKEN)
    message = tinder_api.send_message(match_id, from_id, to_id, message)
    with open("openers.txt", "a") as file:
        file.write("\n" + json.dumps(message))
    if message.get("_id"):  # Check if "_id" exists and is not empty
        return message
    else:
        raise ValueError("Failed to send message to user")
    
@celery.task(name='main.get_tinder_person')
def get_tinder_person(id):
    tinder_api = TinderAPI(TINDER_TOKEN)
    person = tinder_api.get_user_info(id)
    if hasattr(person, "id") and person.id:  # Check if "id" exists and is not empty
        birth_date = person.birth_date.strftime('%Y-%m-%d') if isinstance(person.birth_date, datetime) else person.birth_date
        objPerson = {'id': person.id, 'name' : person.name, 'distance' : person.distance, 'birth_date': birth_date, 'bio': person.bio}
        MatchQuery = Query()
        if not persons_table.contains(MatchQuery.id == person.id):
            persons_table.insert(objPerson)
        return objPerson
    else:
        raise ValueError("Failed to get profile")

@app.get('/')
def hello_world():
    # logger.info(f'/ visited!')
    return 'This is a Tinder automation app!'

@app.get('/matches')
def get_matches():
    tinder_api = TinderAPI(TINDER_TOKEN)
    message=0
    matches = tinder_api.matches(count=100, message=message)
    for match in matches:
        # logger.info(f'Name: {match["person"]["name"]}, Id: {match["id"]}')
        # save matches in a txt file
        # with open("matches.txt", "a") as file:
            # file.write(f'\n match_id: {match.match_id}, id: {match.person.id}, name: {match.person.name}, message: {message}')
        # save all matches
        MatchQuery = Query()
        # Check if a record with the same match_id exists
        # if maches_table.contains(MatchQuery.match_id == match.match_id):
        #     # Update the existing record
        #     maches_table.update({'match_id': match.match_id, 'person_id' : match.person.id, 'name' : match.person.name})
        # else:
        #     # Insert as a new record
        #     maches_table.insert({'match_id': match.match_id, 'person_id' : match.person.id, 'name' : match.person.name})
        if not maches_table.contains(MatchQuery.match_id == match.match_id):
            # Insert as a new record
            maches_table.insert({'match_id': match.match_id, 'person_id' : match.person.id, 'name' : match.person.name})
                 
        # Save data to a JSON file (TypeError: Object of type Match is not JSON serializable)
        # with open("matches.json", "w") as json_file:
        #     json.dump(matches, json_file, indent=4)
    # Read the JSON-formatted content from the file (TypeError: Object of type Match is not JSON serializable)
    # with open("matches.json", "r") as file:
    #     data = json.load(file)
    return 'ok'

@app.get('/all-matches')
def get_all_matches():
    tinder_api = TinderAPI(TINDER_TOKEN)
    message = 1
    all_matches = []
    page_token = None

    while True:
        # Fetch matches with pagination
        matches, page_token = tinder_api.matches(count=100, message=message, page_token=page_token)
        if not matches:
            break  # Stop if no more matches

        # Process each match
        for match in matches:
            MatchQuery = Query()
            if not maches_table.contains(MatchQuery.match_id == match.match_id):
                # Insert as a new record
                maches_table.insert({
                    'match_id': match.match_id,
                    'person_id': match.person.id,
                    'name': match.person.name
                })
        
        # add the new batch of matches to the all_matches list
        all_matches.extend(matches)

        # If no page_token is returned, it means there are no more pages
        if not page_token:
            break

    return maches_table.all()

@app.get('/all-persons')
def get_all_persons():
    cumulative_delay = 0
    task_info = []
    # limit table rows
    # limit = 5
    # matches = maches_table.all()[:limit]
    matches = maches_table.all()
    for row in matches:
        delay = random.randint(10, 20)
        cumulative_delay += delay
        task = get_tinder_person.apply_async((row.get('person_id'),),countdown=cumulative_delay)  # 15-20-second cumulative delay before starting
        task_info.append({"status": "Task started", "task_id": task.id, "delay": delay})
    return task_info

@app.get('/matches/show')
def show_matches():
    return maches_table.all()

@app.get('/persons/show')
def show_matches():
    # db.drop_table('persons')
    return persons_table.all()

@app.get('/match/{person_id}')
def get_match(person_id):
    tinder_api = TinderAPI(TINDER_TOKEN)
    person = tinder_api.get_user_info(person_id)
    objPerson = {'id': person.id, 'name' : person.name, 'distance' : person.distance, 'birth_date': person.birth_date, 'bio': person.bio}
    # with open("matches.txt", "a") as file:
    #     file.write(f'\n id: {person.id}, name: {person.name}, distance: {person.distance}')
    MatchQuery = Query()
    # Check if a record with the same match_id exists
    if persons_table.contains(MatchQuery.id == person.id):
        # Update the existing record
        persons_table.update(objPerson)
    else:
        # Insert as a new record
        persons_table.insert(objPerson)
    return objPerson
    # url = f'https://api.gotinder.com/user/{match_id}?locale=pt'

    # api_token = os.getenv('API_TOKEN')

    # # Define your headers here
    # headers = {
    #     'X-Auth-Token': api_token,
    #     'Content-Type': 'application/json'
    # }

    # # Make a GET request with headers
    # response = requests.get(url, headers=headers)

    # # Check if the request was successful
    # if response.status_code == 200:
    #     return response.json()  # Return JSON response
    # else:
    #     return {"error": "Failed to fetch data"}, response.status_code

@app.get('/unmatch/{match_id}')
async def unmatch(match_id):
    tinder_api = TinderAPI(TINDER_TOKEN)
    return tinder_api.unmatch(match_id)

@app.get('/profile')
def get_profile():
    # Check if the profile table is empty
    if len(profile_table.all()) > 0:
        # If the profile table is not empty, fetch and return the first profile entry
        profile_data = profile_table.all()[0]  # there's only one profile entry
        return profile_data
    
    # If the profile table is empty, fetch profile from the Tinder API
    tinder_api = TinderAPI(TINDER_TOKEN)
    profile = tinder_api.profile()

    # Save the profile information to the table
    profile_data = {
        'id': profile.id,
        # '_api': profile._api,
        'bio': profile.bio,
    }
    profile_table.insert(profile_data)

    # Return the profile information as a dictionary (which will be automatically converted to JSON)
    return profile_data

@app.get('/send-opener/{match_id}/{person_id}')
async def send_opener(match_id, person_id):
    tinder_api = TinderAPI(TINDER_TOKEN)
    profile = tinder_api.profile()
    person = tinder_api.get_user_info(person_id)

    # write your opener message below
    # message = f'Oi {person.name}, como você é linda! Tudo bem com vc?'
    message = OPENER_MESSAGE.replace("<match_name>", person.name)
    with open("messages.txt", "a") as file:
        file.write(f'\n {message}')
    tinder_api = TinderAPI(TINDER_TOKEN)
    message = tinder_api.send_message(match_id, profile.id, person.id, message)
    with open("messages.txt", "a") as file:
        file.write("\n" + json.dumps(message))
    return message if message._id != '' else {"error": "Failed to send message to user"}

    # delay = random.randint(5, 10)
    # task = send_tinder_opener.apply_async((match_id, profile.id, person.id, person.name),countdown=delay)  # 5-10-second delay before starting
    # return {"status": "Task started", "task_id": task.id, "delay": delay}

@app.get('/dispatch-openers')
async def dispatch_openers():
    tinder_api = TinderAPI(TINDER_TOKEN)
    profile = tinder_api.profile()
    message=0
    matches = tinder_api.matches(count=30, message=message)
    task_info = []
    cumulative_delay = 0
    for match in matches:
        first_name = match.person.name.strip().split()[0] if match.person.name.strip() else ''
        with open("openers.txt", "a") as file:
            file.write(f'\n match_id: {match.match_id}, id: {match.person.id}, name: {match.person.name}, first_name: {first_name}, message: {message}')
        delay = random.randint(15, 60)
        cumulative_delay += delay
        task = send_tinder_opener.apply_async((match.match_id, profile.id, match.person.id, first_name),countdown=cumulative_delay)  # 15-60-second cumulative delay before starting
        task_info.append({"status": "Task started", "task_id": task.id, "delay": delay})
    return task_info

@app.get('/export-messages')
def export_valuable_messages():
    tinder_api = TinderAPI(TINDER_TOKEN)
    profile = tinder_api.profile()
    user_id = profile.id
    for match in tinder_api.matches(limit=100):
        chatroom = tinder_api.get_messages(match.match_id)
        count = len(chatroom.messages)
        dialog.export_message_json(user_id, chatroom.messages[::-1]) if count > 20 else None
    combine_json_files(user_id)

def combine_json_files(user_id):
    file_path = f'chat_data/{user_id}'
    json_files = [file for file in os.listdir(file_path) if file.endswith('.json')]
    combined_data = []
    for file in json_files:
        with open(f'chat_data/{user_id}/{file}', 'r') as f:
            data = json.load(f)
            combined_data.append(data)
    with open(f'chat_data/{user_id}/combined.jsonl', 'w', encoding="utf-8") as f:
        for item in combined_data:
            json.dump(item, f, ensure_ascii=False)
            f.write('\n')

@scheduler.scheduled_job("cron", minute='*/5', second=0, id='reply_messages')
def reply_messages():
    tinder_api = TinderAPI(TINDER_TOKEN)
    profile = tinder_api.profile()
    interests = ', '.join(profile.user_interests)
    user_id = profile.id

    for match in tinder_api.matches(limit=50):
        chatroom = tinder_api.get_messages(match.match_id)
        lastest_message = chatroom.get_lastest_message()
        if lastest_message:
            if lastest_message.from_id == user_id:
                from_user_id = lastest_message.from_id
                to_user_id = lastest_message.to_id
                last_message = 'me'
            else:
                from_user_id = lastest_message.to_id
                to_user_id = lastest_message.from_id
                last_message = 'other'
            sent_date = lastest_message.sent_date
            if last_message == 'other' or (sent_date + datetime.timedelta(days=5)) < datetime.datetime.now():
                content = dialog.generate_input(from_user_id, to_user_id, chatroom.messages[::-1])
                response = chatgpt.get_response(profile.bio, interests, content)
                if response:
                    if response.startswith('[Sender]'):
                        chatroom.send(response[8:], from_user_id, to_user_id)
                    else:
                        chatroom.send(response, from_user_id, to_user_id)
                logger.info(f'Content: {content}, Reply: {response}')

@app.get('/task-status/{task_id}')
async def get_task_status(task_id):
    task = AsyncResult(task_id)
    # if task.state == 'PENDING':
    #     response = {"status": "Pending..."}
    # elif task.state == 'SUCCESS':
    #     response = {"status": "Completed", "data": task.result}
    # else:
    #     response = {"status": task.state}
    # return response
    if task.ready():
            return {"task_id": task_id, "result": task.result}
    return {"task_id": task_id, "status": "Processing"}

@app.get("/monitor")
async def monitor():
    return {"flower_url": "http://localhost:5555"}

# @app.on_event("startup")
# async def startup():
#     scheduler.start()


# @app.on_event("shutdown")
# async def shutdown():
#     scheduler.remove_job('reply_messages')

if __name__ == "__main__":
    uvicorn.run('main:app', host='0.0.0.0', port=8080, reload=True)
