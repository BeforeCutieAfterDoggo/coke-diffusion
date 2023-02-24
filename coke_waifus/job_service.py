import time

from coke_waifus.common import (
    db,
    poll_eden_jobs,
    construct_result_url,
    configure_logging,
)
from coke_waifus import messages

logger = configure_logging(__file__)

jobs_collection_ref = db.collection("jobs")


def handle_job_error(prediction_id, error):
    logger.error(f"Job {prediction_id} failed: {error}")
    job_ref = jobs_collection_ref.document(prediction_id)
    job_ref.update({"status": "failed", "error": error})
    doc_data = {
        "tweet_id": job_ref.get().get("tweet_id"),
        "error": messages.JOB_ERROR,
        "result_url": None,
        "acknowledged": False,
    }
    db.collection("results").add(doc_data)


def handle_job_result(prediction_id, result_url):
    logger.info(f"Job {prediction_id} complete: {result_url}")
    job_ref = jobs_collection_ref.document(prediction_id)
    job_ref.update({"status": "complete", "result_url": result_url})
    doc_data = {
        "tweet_id": job_ref.get().get("tweet_id"),
        "error": None,
        "result_url": result_url,
        "acknowledged": False,
    }
    db.collection("results").add(doc_data)


def main():
    while True:
        # Get all jobs with pending status
        try:
            jobs = list(jobs_collection_ref.where("status", "==", "pending").stream())
            logger.info(f"Found {len(jobs)} pending jobs")
            prediction_ids = [job.get("prediction_id") for job in jobs]
            job_results = poll_eden_jobs(prediction_ids)
            for result in job_results["tasks"]:
                prediction_id = result["taskId"]
                if result["status"] == "failed":
                    handle_job_error(prediction_id, result["error"])
                elif result["status"] == "completed":
                    if not result["output"]:
                        handle_job_error(prediction_id, "Output not found")
                    else:
                        result_url = result["output"]["file"]
                        handle_job_result(prediction_id, result_url)
        except Exception as e:
            logger.error(f"Error while polling jobs: {e}")
        time.sleep(20)


if __name__ == "__main__":
    main()
