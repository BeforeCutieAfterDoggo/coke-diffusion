import random
import time
import tempfile

import requests

from coke_waifus.common import db, client, api, configure_logging
from coke_waifus.messages import COMPLETE_RESPONSES

logger = configure_logging(__file__)


def upload_media(result_url):
    logger.info(f"Uploading media from {result_url}")
    r = requests.get(result_url)
    with tempfile.NamedTemporaryFile(suffix=".mp4") as f:
        f.write(r.content)
        f.flush()
        media = api.media_upload(f.name)
    return media.media_id


def main():
    # Create a callback on_snapshot function to capture changes
    logger.info("Starting up...")

    def on_result_snapshot(col_snapshot, changes, read_time):
        for change in changes:
            if change.type.name == "ADDED":
                try:
                    logger.info(f"New result: {change.document.id}")
                    tweet_id = change.document.get("tweet_id")
                    result_url = change.document.get("result_url")
                    error = change.document.get("error")
                    acknowledged = change.document.get("acknowledged")
                    if acknowledged:
                        continue

                    logger.info(f"Replying to {tweet_id}")
                    if error or result_url is None:
                        logger.info(f"New eden error. Replying to {tweet_id}")
                        client.create_tweet(
                            text=error,
                            in_reply_to_tweet_id=tweet_id,
                        )
                        change.document.reference.update({"acknowledged": True})
                    else:
                        media_id = upload_media(result_url)
                        client.create_tweet(
                            text=random.choice(COMPLETE_RESPONSES),
                            in_reply_to_tweet_id=tweet_id,
                            media_ids=[media_id],
                        )
                        change.document.reference.update({"acknowledged": True})
                except Exception as e:
                    logger.error(e)

    results_collection_ref = db.collection("results")

    # Watch the document
    results_collection_ref.on_snapshot(on_result_snapshot)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
