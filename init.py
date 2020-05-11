#!/usr/bin/python

import yaml
import os
from src import generate, process, broadcast


def load_from_yaml():
    with open("/opt/streaming/config.yaml") as f:
        data = yaml.safe_load(f)
    return data

if __name__ == "__main__":
    mode = os.environ.get("MODE", None)
    data = load_from_yaml()

    algo_data = data['algorithmia']
    aws_data = data['aws']
    ffmpeg_data = data['ffmpeg']
    threading_data = data['threading']

    api_key = algo_data['api_key']
    api_address = algo_data.get("api_address", None)
    data_collection = algo_data['data_collection']

    credentials = aws_data['credentials']
    kinesis_input = aws_data['kinesis_input_name']
    kinesis_output = aws_data['kinesis_output_name']

    fps = int(ffmpeg_data.get("fps", 10))
    chunk_duration = data.get("chunk_duration", "00:00:10")

    min_pool = int(threading_data['minimum_threadpool'])
    max_pool = int(threading_data['maximum_threadpool'])
    stream_url = threading_data['stream_url']

    if mode == "generate":
        generate(api_key, credentials, data_collection, kinesis_input, stream_url, fps, chunk_duration, algo_address=api_address)
    elif mode == "process":
        process(api_key, credentials, min_pool, max_pool, kinesis_input, kinesis_output, data_collection, fps, algo_address=api_address)
    elif mode == "broadcast":
        broadcast(api_key, credentials, kinesis_output, fps, algo_address=api_address)
    else:
        raise Exception("{} not a valid runtype".format(mode))
