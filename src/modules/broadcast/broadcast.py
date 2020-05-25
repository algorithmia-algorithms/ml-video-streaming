import Algorithmia
import ffmpeg
import os
from src.utils import create_consumer, credential_auth
from subprocess import Popen
import json
import time


def push_to_stream(local_path, svg_path, type, input_fps):
    input = ffmpeg.input(local_path)
    if type == "transform":
        probe = ffmpeg.probe(local_path)
        video_info = next(stream for stream in probe['streams'] if stream['codec_type'] == 'video')
        width = int(video_info['width'])
        input = ffmpeg.input(local_path)
        overlay_dim = int(width / 10)
        overlay = ffmpeg.input(svg_path).filter_('scale', "{}x{}".format(str(overlay_dim), str(overlay_dim)))
        v0 = input['v'].overlay(overlay, x=10, y=10)
        a0 = input['a']
        output = ffmpeg.output(v0, a0, "rtmp://localhost/hls/streaming", vcodec="h264", acodec="copy", r=input_fps,
                               max_muxing_queue_size=1024, f="flv", loglevel="error")
    else:
        output = ffmpeg.output(input, "rtmp://localhost/hls/streaming", vcodec="h264", acodec="copy", r=input_fps,
                               max_muxing_queue_size=1024, f="flv", loglevel="error")

    output.run()
    print(" streamer - pushed stream", flush=True)


def start_nginx():
    os.makedirs("/tmp/streaming", exist_ok=True)
    p = Popen("/usr/local/nginx/sbin/nginx")
    p.wait()
    print("started nginx", flush=True)


def download_and_stream(client, url, svg_path, type, input_fps):
    if url:
        local_path = client.file(url).getFile().name
        renamed_path = local_path + '.mp4'
        os.rename(local_path, renamed_path)
        push_to_stream(renamed_path, svg_path, type, input_fps)
    else:
        print("no URL provided, skipping..".format(url), flush=True)


def main_loop(client, consumer, input_fps):
    iterator = consumer.__iter__()
    svg_path = "/opt/streaming/src/btree.svg"
    while True:
        message = iterator.__next__()
        if message:
            print("got a message", flush=True)
            data = json.loads(message['Data'])
            url = data['url']
            type = data['type']
            download_and_stream(client, url, svg_path, type, input_fps)
        else:
            print("no message found", flush=True)
            time.sleep(1)


def broadcast(algorithmia_api_key, aws_creds, kinesis_stream_name, stream_fps, dynamo_table_name=None,
              algo_address=None):
    if algo_address:
        client = Algorithmia.client(algorithmia_api_key, api_address=algo_address)
    else:
        client = Algorithmia.client(algorithmia_api_key)
    print("starting broadcast", flush=True)
    session = credential_auth(aws_creds)
    consumer = create_consumer(kinesis_stream_name, session, dynamo_table_name)
    start_nginx()
    main_loop(client, consumer, stream_fps)
