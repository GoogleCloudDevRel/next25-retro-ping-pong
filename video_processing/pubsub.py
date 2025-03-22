from google.cloud import pubsub_v1
import json
import time


def publish_event(project_id, topic_id, event_type):
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_id)
    timestamp = time.time()

    message = {
        "event_type": event_type,
        "timestamp": timestamp,
    }

    data = json.dumps(message).encode("utf-8")
    future = publisher.publish(topic_path, data)

    try:
        message_id = future.result()
        print(f"Published message: {message_id} to topic: {topic_path}")
    except Exception as e:
        print(f"Error publishing message: {e}")


if __name__ == "__main__":
    project_id = "data-connect-interactive-demo"
    topic_id = "game_events"
    # publish_event(project_id, topic_id, "RECORDING_START")
    publish_event(project_id, topic_id, "RECORDING_STOP")
