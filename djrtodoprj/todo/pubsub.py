import json
import redis

redis_client = redis.StrictRedis(host="localhost", port=6379, db=1)


def publish_data_on_redis(json_data, channel):
    redis_client.publish(channel, json.dumps(json_data))
