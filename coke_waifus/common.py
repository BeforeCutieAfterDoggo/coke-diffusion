import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import firebase_admin
import requests
import tweepy
from dotenv import load_dotenv
from firebase_admin import credentials
from firebase_admin import firestore

load_dotenv()

logfile_path = Path(__file__).parent.parent / "coke_waifus.log"
cred_path = Path(__file__).parent.parent / "credential.json"
cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

client = tweepy.Client(
    bearer_token=os.getenv("TWITTER_BEARER_TOKEN"),
    consumer_key=os.getenv("TWITTER_CONSUMER_KEY"),
    consumer_secret=os.getenv("TWITTER_CONSUMER_SECRET"),
    access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
    access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
)
auth = tweepy.OAuthHandler(
    os.getenv("TWITTER_CONSUMER_KEY"),
    os.getenv("TWITTER_CONSUMER_SECRET"),
)
auth.set_access_token(
    os.getenv("TWITTER_ACCESS_TOKEN"),
    os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
)
api = tweepy.API(auth)

EDEN_GATEWAY_URL = os.getenv("EDEN_GATEWAY_URL")
EDEN_MINIO_URL = os.getenv("EDEN_MINIO_URL")
EDEN_MINIO_BUCKET = os.getenv("EDEN_MINIO_BUCKET")

EDEN_API_KEY = os.getenv("EDEN_API_KEY")
EDEN_API_SECRET = os.getenv("EDEN_API_SECRET")

EDEN_AUTH_DATA = {"x-api-key": EDEN_API_KEY, "x-api-secret": EDEN_API_SECRET}


def start_prediction(data):
    response = requests.post(
        EDEN_GATEWAY_URL + "/user/create", json=data, headers=EDEN_AUTH_DATA
    )
    return response


def prompt_formatter(prompt):
    return prompt + ", subtle Coca-Cola branding and logos in background"


def send_real2real_request(prompt):
    request = {
        "config": {"text_input": prompt_formatter(prompt)},
        "generatorName": "create",
    }
    response = start_prediction(request)
    prediction_id = response.json()["taskId"]
    return prediction_id


def poll_eden_jobs(prediction_ids):
    response = requests.post(
        EDEN_GATEWAY_URL + "/user/tasks",
        json={"taskIds": prediction_ids},
        headers=EDEN_AUTH_DATA,
    )
    result = response.json()
    return result


def construct_result_url(sha):
    return f"{EDEN_MINIO_URL}/{EDEN_MINIO_BUCKET}/{sha}"


def configure_logging(filename):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename=logfile_path,
        filemode="a",
    )
    logger = logging.getLogger(filename)
    handler = RotatingFileHandler(logfile_path, maxBytes=1000000, backupCount=5)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
