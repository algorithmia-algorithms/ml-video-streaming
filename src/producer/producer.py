import streamlink
import ffmpeg
import os
import time
import shutil
from subprocess import Popen, PIPE
from src.utils import create_producer, credential_auth
import Algorithmia
from uuid import uuid4
import json

LOCAL_SYSTEM_DUMP_PATH = "/tmp/streaming_data"
STREAM_QUALITY = "480p"


def get_stream(url, quality=STREAM_QUALITY):
    streams = streamlink.streams(url)
    if streams:
        return streams[quality].to_url()
    else:
        raise ValueError("No steams were available")



def create_video_blocks(stream, path_naming, fps, segment_time='00:00:10'):
    path = path_naming.replace('{}', '%d')
    (ffmpeg
     .input(stream)
     .output(path, segment_time=segment_time, f="segment", r=fps, reset_timestamps='1')
     .global_args('-loglevel', 'warning')
     .run_async()
     )

def file_ready(file_path):
    if os.path.exists(file_path):
        file_check_process = Popen("lsof -f -- {}".format(file_path).split(' '), stdout=PIPE)
        file_chcker = file_check_process.wait()
        return file_chcker
    else:
        return 0


def restream_file(client, producer, itr, local_file_path, remote_file_path):
    local_file_path = local_file_path.format(str(itr))
    remote_file_path = remote_file_path.format(str(itr))
    print(local_file_path)
    print(remote_file_path)
    while True:
        if file_ready(local_file_path):
            print("uploading file...")
            client.file(remote_file_path).putFile(local_file_path)
            output = json.dumps({'url': remote_file_path, 'itr': itr})
            print("pushing to kinesis...")
            producer.put(output)
            break
        else:
            time.sleep(1)

def stream_data(client, producer, local_file_path, remote_file_path):
    itr = 1
    while True:
        restream_file(client, producer, itr, local_file_path, remote_file_path)
        itr += 1

def prepare_scratch_space():
    shutil.rmtree("/tmp/streaming_data", ignore_errors=True)
    os.makedirs("/tmp/streaming_data")


def generate(algorithmia_api_key, aws_creds, data_collection, kinesis_input_name, stream_url, fps, chunk_size="00:00:10", algo_address=None):
    if algo_address:
        client = Algorithmia.client(algorithmia_api_key, api_address=algo_address)
    else:
        client = Algorithmia.client(algorithmia_api_key)
    prepare_scratch_space()
    session = credential_auth(aws_creds)
    producer = create_producer(kinesis_input_name, session)
    local_file_format = "{}/stream_input_{}.mp4".format(LOCAL_SYSTEM_DUMP_PATH, "{}")
    remote_file_format = "{}/{}-{}.mp4".format(data_collection, str(uuid4()), "{}")
    input_stream = get_stream(stream_url)

    create_video_blocks(input_stream, local_file_format, fps)
    stream_data(client, producer, local_file_format, remote_file_format)
