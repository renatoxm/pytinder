# import time
import random
from fastapi import FastAPI
from celery.result import AsyncResult # type: ignore
import os
from dotenv import load_dotenv # type: ignore
import requests
import json
from datetime import datetime
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler # type: ignore
import uvicorn # type: ignore
from tinydb import TinyDB, Query # type: ignore
from celery import Celery # type: ignore
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
matches_table = db.table('matches')
profile_table = db.table('profile')

TINDER_TOKEN = os.getenv('TINDER_TOKEN')
GREETING_MESSAGE = os.getenv("GREETING_MESSAGE")

# Configure Celery
celery = Celery(
    __name__,
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

@celery.task(name='main.send_tinder_opener')
def send_tinder_opener(match_id, from_id, to_id, message):
    with open("logs/openers.txt", "a") as file:
        file.write(f'\n {message}')
    tinder_api = TinderAPI(TINDER_TOKEN)
    message = tinder_api.send_message(match_id, from_id, to_id, message)
    with open("logs/openers.txt", "a") as file:
        file.write("\n" + json.dumps(message))
    if message.get("_id"):  # Check if "_id" exists and is not empty
        return message
    else:
        raise ValueError("Failed to send message to user")
    
@celery.task(name='main.get_tinder_person')
def get_tinder_person(match_id, person_id):
    tinder_api = TinderAPI(TINDER_TOKEN)
    person = tinder_api.get_user_info(person_id)
    if hasattr(person, "id") and person.id:  # Check if "id" exists and is not empty
        birth_date = person.birth_date.strftime('%Y-%m-%d') if isinstance(person.birth_date, datetime) else person.birth_date
        # add only missing fields not present in match
        objPerson = {
            'distance' : person.distance, 
            'birth_date': person.birth_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ') if person.birth_date else None,
            'bio': person.bio
        }
        MatchQuery = Query()
        matches_table.update(objPerson, MatchQuery.match_id == match_id)
        return matches_table.get(MatchQuery.match_id == match_id)
    else:
        raise ValueError("Failed to get profile")
    
@celery.task(name='main.unmatch_tinder_person')
def unmatch_tinder_person(match_id):
    tinder_api = TinderAPI(TINDER_TOKEN)
    response = tinder_api.unmatch(match_id)
    if response.status_code == 200:
        matches_table.remove(match_id == match_id)
        return "ok"
    raise ValueError("Failed to unmatch")

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
        # with open("logs/matches.txt", "a") as file:
            # file.write(f'\n match_id: {match.match_id}, id: {match.person.id}, name: {match.person.name}, message: {message}')
        # save all matches
        MatchQuery = Query()
        # Check if a record with the same match_id exists
        # if matches_table.contains(MatchQuery.match_id == match.match_id):
        #     # Update the existing record
        #     matches_table.update({'match_id': match.match_id, 'person_id' : match.person.id, 'name' : match.person.name})
        # else:
        #     # Insert as a new record
        #     matches_table.insert({'match_id': match.match_id, 'person_id' : match.person.id, 'name' : match.person.name})
        if not matches_table.contains(MatchQuery.match_id == match.match_id):
            # Insert as a new record
            matches_table.insert({'match_id': match.match_id, 'person_id' : match.person.id, 'name' : match.person.name})
                 
        # Save data to a JSON file (TypeError: Object of type Match is not JSON serializable)
        # with open("logs/matches.json", "w") as json_file:
        #     json.dump(matches, json_file, indent=4)
    # Read the JSON-formatted content from the file (TypeError: Object of type Match is not JSON serializable)
    # with open("logs/matches.json", "r") as file:
    #     data = json.load(file)
    return 'ok'

# save all matches in matches_table
@app.get('/all-matches')
def get_all_matches():
    tinder_api = TinderAPI(TINDER_TOKEN)
    message = 1 # 1 for one or more messages, 0 for matches with no messages between them
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
            if not matches_table.contains(MatchQuery.match_id == match.match_id):
                # Insert as a new record
                matches_table.insert({
                    'match_id': match.match_id,
                    'person_id': match.person.id,
                    'name': match.person.name
                })
        
        # add the new batch of matches to the all_matches list
        all_matches.extend(matches)

        # If no page_token is returned, it means there are no more pages
        if not page_token:
            break

    return matches_table.all()

# first run '/all-matches' route to fill your table
# it will only append the task if match does not already have distance att
# make sure celery and flow are running, see: ## Running the app, flower and celery queues in README.md
@app.get('/all-persons')
def get_all_persons():
    cumulative_delay = 0
    task_info = []
    # limit table rows
    # limit = 5
    # matches = matches_table.all()[:limit]
    matches = matches_table.all()
    for row in matches:
        if 'distance' not in row:
            delay = random.randint(5, 10)
            cumulative_delay += delay
            task = get_tinder_person.apply_async((row.get('match_id'),row.get('person_id'),),countdown=cumulative_delay)  # 15-20-second cumulative delay before starting
            task_info.append({"status": "Task started", "task_id": task.id, "delay": delay})
    return task_info

@app.get('/matches/show')
def show_matches():
    return matches_table.all()

@app.get('/matches/totals')
def show_matches_totals():
    MatchQuery = Query()
    total_matches = len(matches_table)
    under_15 = len(matches_table.search(MatchQuery.distance < 15))
    over_15 = len(matches_table.search(MatchQuery.distance >= 15))
    return {
        "total_matches": total_matches,
        "under_15": under_15,
        "over_15": over_15
    }

@app.get('/match/{match_id}')
def get_match(match_id):
    match_query = Query()
    row = matches_table.get(match_query.match_id == match_id)
    if row:
            person_id = row['person_id']
            tinder_api = TinderAPI(TINDER_TOKEN)
            person = tinder_api.get_user_info(person_id)
            obj_person = {
                'distance': person.distance,
                'birth_date': person.birth_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ') if person.birth_date else None,
                'bio': person.bio
            }
            
            # Update existing row
            matches_table.update(obj_person, match_query.match_id == match_id)
            return matches_table.get(match_query.match_id == match_id)

    else:
        return {"error": "Match no found"}

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
    response = tinder_api.unmatch(match_id)
    if response.status_code == 200:
        matches_table.remove(match_id == match_id)
        return "ok"
    raise ValueError("Failed to unmatch")

@app.get('/unmatch-all-persons-distant')
def unmatch_all_distant():
    tinder_api = TinderAPI(TINDER_TOKEN)
    cumulative_delay = 0
    task_info = []
    # limit table rows
    # limit = 5
    # matches = matches_table.all()[:limit]
    matches = matches_table.all()
    for row in matches:
        match_id = row.get("match_id")
        if not match_id:
            continue  # Skip rows with no match_id
        # Skip persons distant more than 15 km
        if row.get("distance") < 15:
            continue
        # Schedule task with a cumulative delay
        delay = random.randint(10, 20)
        cumulative_delay += delay
        # unmatch distant persons
        task = unmatch_tinder_person.apply_async((match_id,), countdown=cumulative_delay)
        task_info.append({"status": "Task started", "task_id": task.id, "delay": delay})
    return task_info

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

@app.get('/send-opener/{match_id}')
async def send_opener(match_id):
    tinder_api = TinderAPI(TINDER_TOKEN)
    profile = tinder_api.profile()

    # Fetch person details from matches_table using match_id
    MatchQuery = Query()
    match = matches_table.get(MatchQuery.match_id == match_id)

    if not match:
        return {"error": "Match not found"}

    # write your opener message below
    # message = f'Hi {to_name}, how are you doing?'
    first_name = match["name"].strip().split()[0] if match["name"].strip() else ''
    message = GREETING_MESSAGE.replace("<match_name>", first_name)
    with open("logs/messages.txt", "a") as file:
        file.write(f'\n {message}')
    tinder_api = TinderAPI(TINDER_TOKEN)
    message = tinder_api.send_message(match_id, profile.id, match["person_id"], message)
    with open("logs/messages.txt", "a") as file:
        file.write("\n" + json.dumps(message))
    return message if message.get("_id") else {"error": "Failed to send message to user"}

    # delay = random.randint(5, 10)
    # task = send_tinder_opener.apply_async((match_id, profile.id, person.id, message),countdown=delay)  # 5-10-second delay before starting
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
        message = GREETING_MESSAGE.replace("<match_name>", first_name)
        with open("logs/openers.txt", "a") as file:
            file.write(f'\n match_id: {match.match_id}, id: {match.person.id}, name: {match.person.name}, first_name: {first_name}, message: {message}')
        delay = random.randint(5, 10)
        cumulative_delay += delay
        task = send_tinder_opener.apply_async((match.match_id, profile.id, match.person.id, message),countdown=cumulative_delay)  # 15-60-second cumulative delay before starting
        task_info.append({"status": "Task started", "task_id": task.id, "delay": delay})
    return task_info

@app.get('/dispatch-openers-from-table')
async def dispatch_openers_from_table():
    tinder_api = TinderAPI(TINDER_TOKEN)
    profile = tinder_api.profile()
    task_info = []
    cumulative_delay = 0
    counter = 0
    matches = matches_table.all()  # Get all matches from the TinyDB table
    for match in matches:
        if match.get("distance", 0) > 15:  # Skip matches with a distance over 15
            continue
        first_name = match["name"].strip().split()[0] if match["name"].strip() else ''
        message = GREETING_MESSAGE.replace("<match_name>", first_name)
        with open("logs/openers.txt", "a") as file:
            file.write(
                f'\n match_id: {match["match_id"]}, id: {match["person_id"]}, name: {match["name"]}, '
                f'first_name: {first_name}, message: {message}'
            )
        delay = random.randint(5, 10)
        cumulative_delay += delay
        counter += 1
        task = send_tinder_opener.apply_async(
            (match["match_id"], profile.id, match["person_id"], message),
            countdown=cumulative_delay
        )
        task_info.append({"status": "Task started", "task_id": task.id, "delay": cumulative_delay})
    
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
    file_path = f'logs/chat_data/{user_id}'
    json_files = [file for file in os.listdir(file_path) if file.endswith('.json')]
    combined_data = []
    for file in json_files:
        with open(f'logs/chat_data/{user_id}/{file}', 'r') as f:
            data = json.load(f)
            combined_data.append(data)
    with open(f'logs/chat_data/{user_id}/combined.jsonl', 'w', encoding="utf-8") as f:
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
