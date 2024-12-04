# Tinder Project

A Tinder automation project (use with caution)

[Python](https://www.python.org/)
[FastApi](https://fastapi.tiangolo.com/)
[Uvicorn](https://www.uvicorn.org/)
[Celery](https://docs.celeryq.dev/)
[Flower](https://flower.readthedocs.io/en/latest/)
[OpenAI](https://pypi.org/project/openai/)
[APScheduler](https://apscheduler.readthedocs.io/)
[TinyDB](https://tinydb.readthedocs.io/)

## python basics if you're new to the language

### Install Python in WSL2

#### Check if Python is installed by running

```bash
python3 --version
```

#### If not installed, update your package list and install Python

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

#### Navigate to Your Project Directory

You can access your Windows file system from WSL by navigating to /mnt/, where each drive is mounted as a folder (/mnt/c for the C drive, for example).
To move to a project directory on your C drive:

```bash
cd /mnt/c/path/to/your/project
```

#### Set Up a Virtual Environment (Recommended)

Create a virtual environment for your project:

```bash
python3 -m venv .venv
```

#### Activate the environment

```bash
source .venv/bin/activate
```

#### Exit the environment

```bash
deactivate
```

#### Install dependencies using pip

```bash
pip install -r requirements.txt
```

#### Run the Python Project

Now, you can run your Python project as you would in a Linux environment:

```bash
python main.py
```

#### Run the FastAPI app with Uvicorn

```bash
uvicorn main:app --reload
```

## Handling requirements.txt

you can auto-generate a requirements.txt file for a Python project, which will include all installed packages along with their versions. Here’s how to do it:

### Using pip freeze

This is a common way to generate requirements.txt based on your currently installed packages in the virtual environment.

```bash
pip freeze > requirements.txt
```

This will create a `requirements.txt` file with all packages and their versions listed.

### Using pipreqs

If you only want to include packages that your project actually imports, you can use a tool called pipreqs, which scans your code and adds only the necessary dependencies.

Install pipreqs:

```bash
pip install pipreqs
```

Run pipreqs in your project directory:

```bash
pipreqs --ignore .venv --force
```

This will create a requirements.txt file based on the packages your code directly depends on.

### Using Poetry or Pipenv (if your project uses them)

If you use Poetry or Pipenv, these tools can also generate a requirements file.

#### Poetry

```bash
poetry export -f requirements.txt --output requirements.txt
```

#### Pipenv

```bash
pipenv lock -r > requirements.txt
```

These methods ensure that you get a `requirements.txt` file tailored to your project's dependencies.

## Celery and Redis

### Installing Redis Server on Windows with WSL2

Open your WSL2 terminal (Ubuntu or another Linux distribution).

Install Redis by running:

```bash
sudo apt update
sudo apt install redis-server
```

Start Redis and configure it to start automatically:

```bash
sudo service redis-server start
```

Verify Redis is running:

```bash
redis-cli ping
```

You should see PONG if Redis is up and running.

### Stopping Redis server

```bash
sudo service redis-server stop
```

## Running the app, flower and celery queues

You will need three separate terminal windows

run one on each (make sure python environment is active `source .venv/bin/activate`):

### start celery

```bash
celery -A main.celery worker --loglevel=info
```

### start flower

```bash
celery -A main.celery flower
```

you can access flower dashboard here: <http://localhost:5555/>

### start the app

```bash
# python app.py
uvicorn main:app --reload
```

## Running the app on docker

Run the following command to start all services:

```bash
docker-compose up --build
```

FastAPI will be available at <http://localhost:8000>.

Flower will be accessible at <http://localhost:5555>.

## How to access your project

you can access your app here: <http://localhost:8000/>

<http://localhost:8000/async-api-data>

<http://localhost:8000/task-status/task-id-from-previous-route>
