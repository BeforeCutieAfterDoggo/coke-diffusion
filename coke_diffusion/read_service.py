import re
import time

from coke_diffusion.common import (
    api,
    db,
    client,
    send_real2real_request,
    configure_logging,
)
from coke_diffusion import messages

logger = configure_logging(__file__)

THREAD_ID = 1629173900197371904
AUTHOR_ID = 1623020917965348865
MAX_USER_CREATIONS = 50


def update_user_creation_total(user_id):
    user_ref = db.collection("users").document(str(user_id))
    user = user_ref.get()
    if user.exists:
        user_ref.update({"creation_total": user.get("creation_total") + 1})
    else:
        user_ref.set({"creation_total": 1})


def get_image_urls(tweet):
    old_tweet = api.get_status(id=tweet.id)
    image_urls = [e["media_url_https"] for e in old_tweet.extended_entities["media"]]
    return image_urls


def is_follower_check(replies):
    author_ids = [reply.author_id for reply in replies]
    friendships = api.lookup_friendships(user_id=author_ids)
    follower_ids = [
        friendship.id for friendship in friendships if friendship.is_followed_by
    ]
    follower_replies = [reply for reply in replies if reply.author_id in follower_ids]
    nonfollower_replies = [
        reply for reply in replies if reply.author_id not in follower_ids
    ]
    return follower_replies, nonfollower_replies


def is_top_level_reply(tweet):
    is_top_level_reply = False
    for ref in tweet.referenced_tweets:
        if ref.type == "replied_to" and ref.id == THREAD_ID:
            is_top_level_reply = True
    return is_top_level_reply


def entity_is_image(entity):
    if entity.get("expanded_url"):
        if "photo" in entity["expanded_url"]:
            return True


def check_reply_has_two_images(reply):
    entities = reply.entities
    if entities and entities.get("urls"):
        if len(entities["urls"]) == 2:
            for entity in entities["urls"]:
                if not entity_is_image(entity):
                    return False
            return True
    return False


def get_user_creation_count(user_id):
    user_ref = db.collection("users").document(str(user_id))
    user = user_ref.get()
    if user.exists:
        return user.get("creation_total")
    else:
        return 0


def handle_reached_max_user_creation_limit(reply):
    user_id = reply.author_id
    logger.info(f"User {user_id} has reached the max user creation limit")
    doc_data = {
        "author_id": user_id,
        "tweet_id": None,
        "error": messages.MAX_USER_CREATIONS_ERROR,
    }
    db.collection("requests").document(str(reply.id)).set(doc_data)
    doc_data = {
        "tweet_id": reply.id,
        "error": messages.MAX_USER_CREATIONS_ERROR,
        "result_url": None,
        "acknowledged": False,
    }
    db.collection("results").document(str(reply.id)).set(doc_data)


def handle_nonfollower_reply(reply):
    logger.info(f"Found non-follower reply: {reply.id}")
    doc_data = {
        "author_id": reply.author_id,
        "tweet_id": reply.id,
        "error": messages.NOT_FOLLOWING_ERROR,
    }
    db.collection("requests").document(str(reply.id)).set(doc_data)
    doc_data = {
        "tweet_id": reply.id,
        "error": messages.NOT_FOLLOWING_ERROR,
        "result_url": None,
        "acknowledged": False,
    }
    db.collection("results").document(str(reply.id)).set(doc_data)


def handle_valid_reply(reply):
    logger.info(f"Found valid reply: {reply.id}")
    prompt = re.sub(r"@\w+", "", reply.text)
    doc_data = {
        "author_id": reply.author_id,
        "tweet_id": reply.id,
        "prompt": prompt,
        "error": None,
    }
    db.collection("requests").document(str(reply.id)).set(doc_data)
    logger.info("Sending job to eden...")
    prediction_id = send_real2real_request(prompt)
    doc_data = {
        "status": "pending",
        "prediction_id": prediction_id,
        "tweet_id": reply.id,
    }
    db.collection("jobs").document(prediction_id).set(doc_data)
    update_user_creation_total(reply.author_id)


def get_latest_reply_id():
    collection_ref = db.collection("requests")
    docs = collection_ref.order_by("tweet_id", direction="DESCENDING").limit(1).stream()
    for doc in docs:
        return doc.to_dict()["tweet_id"]


def main():
    newest_id = get_latest_reply_id()
    query = f"conversation_id:{THREAD_ID} is:reply"
    logger.info(f"Starting read service from tweet id: {newest_id}")
    while True:
        try:
            logger.info("Polling for new responses...")
            response = client.search_recent_tweets(
                query=query,
                since_id=newest_id,
                tweet_fields="author_id,entities,referenced_tweets",
                media_fields="url",
            )
            if response and response.data:
                replies = [tw for tw in response.data if is_top_level_reply(tw)]
                logger.info(f"Found {len(replies)} new top-level replies.")
                if replies:
                    for reply in replies:
                        creation_count = get_user_creation_count(reply.author_id)
                        if creation_count >= MAX_USER_CREATIONS:
                            handle_reached_max_user_creation_limit(reply)
                        else:
                            handle_valid_reply(reply)

                    newest_id = response.meta["newest_id"]
        except Exception as e:
            logger.error(e)
        time.sleep(10)


if __name__ == "__main__":
    main()
