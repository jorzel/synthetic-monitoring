import os
import time
import threading

import prometheus_client
from flask import Flask

import structlog
import requests
from prometheus_client import Histogram, make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

logger = structlog.get_logger()

app = Flask(__name__)

# Add endpoint that will expose the metrics
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {"/metrics": make_wsgi_app()})

prometheus_client.REGISTRY.unregister(prometheus_client.GC_COLLECTOR)
prometheus_client.REGISTRY.unregister(prometheus_client.PLATFORM_COLLECTOR)
prometheus_client.REGISTRY.unregister(prometheus_client.PROCESS_COLLECTOR)

INTERVAL_SEC = int(os.getenv("INTERVAL_SEC", 5))
RESERVATIONS_SERVICE_URL = os.getenv("RESERVATIONS_SERVICE_URL")
if not RESERVATIONS_SERVICE_URL:
    raise ValueError("RESERVATIONS_SERVICE_URL is not set")

HTTP_REQUEST_DURATION = Histogram(
    "synthetic_request_duration",
    "Synthetic requests durations",
    ["method", "url", "result"],
    buckets=[0.01, 0.1, 0.5, 2, float("inf")],
)

logger.info("Monitor")

def start_monitor():
    logger.info("Starting monitor")
    while True:
        _make_request()     
        time.sleep(INTERVAL_SEC)

    logger.info("Monitor terminated")


def _make_request():
    logger.info("Sending request to reservations service")
    endpoint = f"{RESERVATIONS_SERVICE_URL}/reservations"
    result = 'success'
    start = time.time()
    try:
        response = requests.post(endpoint, data='{"username": "synthetic"}')
        if response.status_code != 200:
            result = 'failure'
    except Exception as e:
        logger.warn(f"Error: {e}")
        result = 'failure'
    finally:
        end = time.time()
        HTTP_REQUEST_DURATION.labels(
            method='POST',
            url=endpoint,
            result=result
        ).observe(end - start)


@app.route("/")
@app.route("/up")
def up():
    return "I am running"


# Start the monitor in a separate thread in the background
t = threading.Thread(target=start_monitor)
t.start()
