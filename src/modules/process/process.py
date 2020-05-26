from random import uniform
import time
from threading import Thread, Lock
from queue import Queue
import Algorithmia
from src.utils import create_producer, create_consumer, credential_auth
from uuid import uuid4
import json

MAX_SECONDS = 120


class CheckableVariable(object):
    def __init__(self, default_value):
        self.queue = Queue(1)
        self.queue.put(default_value)
        self.lock = Lock()

    def get(self):
        with self.lock:
            result = self.queue.get()
            self.queue.put(result)
            return result

    def increment(self, value):
        with self.lock:
            result = self.queue.get()
            self.queue.put(result + value)

    def decrement(self, value):
        with self.lock:
            result = self.queue.get()
            self.queue.put(result - value)


class PoolManger(object):
    def __init__(self, min_pool, max_pool, increment_size):
        self._current_count = CheckableVariable(min_pool)
        self._max_count = CheckableVariable(max_pool)
        self._unlock = Lock()
        self._incr_size = increment_size

    def max(self):
        return self._max_count.get()

    def current(self):
        return self._current_count.get()

    def acquire(self):
        while True:
            if not self._unlock.locked() and self.current() < self.max():
                break
            else:
                time.sleep(uniform(0.1, 0.5))
        self._unlock.acquire()
        self._current_count.increment(1)

    def release(self):
        try:
            self._unlock.release()
        except RuntimeError:
            pass

    def update_max(self):
        self._max_count.increment(self._incr_size)

    def __enter__(self):
        self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def wait_to_transform(client, logger, itr, next_input, next_output, fps, time_wait=5):
    dataFile = client.file(next_input)
    while True:
        logger.info("process - {} - woke thread".format(itr))
        if dataFile.exists():
            break
        else:
            time.sleep(time_wait)
    logger.info("process - {}- processing".format(itr))
    result = transform(client, logger, next_input, next_output, fps)
    logger.info("process - {} - processed".format(itr))
    return result


def transform(client, logger, input_file, output_file, fps):
    algo = "deeplearning/ObjectDetectionCOCO/0.3.x"
    advanced_input = {
        "images": "$BATCH_INPUT",
        "outputs": "$BATCH_OUTPUT",
        "model": "ssd_mobilenet_v1",
        "minscore": "0.7"
    }
    input = {
        "input_file": input_file,
        "output_file": output_file,
        "algorithm": algo,
        "advanced_input": advanced_input,
        "fps": fps,
    }
    try:
        result = client.algo('media/videotransform?timeout=3000').pipe(input).result
        return result['output_file']
    except Exception as e:
        logger.info(e)
        return None


def process(logger, client, feeder_q, processed_q, thread_locker, remote_format, fps):
    with thread_locker:
        logger.info("process - {}/{} threads unlocked".format(str(thread_locker.current()), str(thread_locker.max())))
        while True:
            while feeder_q.empty():
                time.sleep(0.25)
            data = feeder_q.get()
            itr = data['itr']
            input_url = data['url']
            remote_path = "{}/{}.mp4".format(remote_format, str(uuid4()))
            algorithm_response = wait_to_transform(client, logger, itr, input_url, remote_path, fps, time_wait=1)
            if algorithm_response:
                data = {itr: algorithm_response}
                logger.info("process - pushing {} to publishing queue..".format(itr))
                processed_q.put(data)
                thread_locker.release()
            else:
                logger.info("process - skipping {} due to exception...".format(itr))


def consume(logger, aws_creds, work1_q, work2_q, input_stream):
    session = credential_auth(aws_creds)
    consumer = create_consumer(input_stream, session)
    logger.info("input - starting to consume...")
    for message in consumer:
        work1_q.put(json.loads(message['Data']))
        work2_q.put(json.loads(message['Data']))
        logger.info("input - got message and queued")


def publish(logger, aws_creds, output_stream, work_completed_queue, input_secondary_queue, thread_locker, fps):
    session = credential_auth(aws_creds)
    producer = create_producer(output_stream, session)
    cutoff = None
    videos_per_publish = int(MAX_SECONDS / fps)
    buffer = {}
    originals_buffer = {}
    t = time.time()
    logger.info("output - waiting {}s before starting publishing".format(str(MAX_SECONDS)))
    while time.time() - t < MAX_SECONDS:
        time.sleep(0.25)
    t = time.time()
    logger.info("output - starting publishing system...")
    while True:
        while work_completed_queue.empty() and input_secondary_queue.empty() and time.time() - t < MAX_SECONDS:
            time.sleep(0.25)

        transformed_indicies = list(buffer.keys())

        if not input_secondary_queue.empty():
            data = input_secondary_queue.get()
            itr = data['itr']
            if not cutoff:
                cutoff = int(itr)
            original_url = data['url']
            originals_buffer[itr] = original_url
        if not work_completed_queue.empty():
            data = work_completed_queue.get()
            key = list(data.keys())[0]
            if int(key) >= cutoff:
                buffer[key] = data[key]
                logger.info("output - transformed -  {} - {}".format(transformed_indicies, cutoff))
            else:
                logger.info("output - {} is not greater than current cursor, ignoring...".format(key))
        if time.time() - t > MAX_SECONDS and len(buffer.keys()) >= videos_per_publish:
            logger.info("output - {} - {}".format(transformed_indicies, videos_per_publish))
            transformed_indicies.sort()
            shippable_buffer = []
            increase_threads_signal = False
            logger.info("output - pushing {}s of content to publishing buffer...".format(str(MAX_SECONDS)))
            for i in range(cutoff, cutoff + videos_per_publish):
                if i in transformed_indicies:
                    packaged = {"itr": i, "url": buffer[i], "type": "transform"}
                    del buffer[i]
                elif i in originals_buffer:
                    packaged = {"itr": i, "url": originals_buffer[i], "type": "original"}
                    del originals_buffer[i]
                else:
                    packaged = {'itr': i, "url": None, "type": None}
                logger.info("output - packaging -{}".format(packaged))
                shippable_buffer.append(packaged)
            shippable_buffer = sorted(shippable_buffer, key=lambda k: k['itr'])
            for next_item in shippable_buffer:
                if next_item['type'] == "original":
                    increase_threads_signal = True
                logger.info("output - shipping {}".format(next_item))
                producer.put(json.dumps(next_item))
            logger.info("output - finished publishing")
            if increase_threads_signal:
                thread_locker.update_max()
            cutoff = cutoff + videos_per_publish
            t = time.time()


class Logger:
    def __init__(self):
        self.q = Queue()

    def info(self, message):
        self.q.put(message)

    def read_next(self):
        next_message = self.q.get()
        print(next_message, flush=True)


def processor(algorithmia_api_key, aws_creds, initial_pool, input_stream_name, output_stream_name,
              data_collection, fps, algo_address=None):
    logger = Logger()
    if algo_address:
        client = Algorithmia.client(algorithmia_api_key, api_address=algo_address)
    else:
        client = Algorithmia.client(algorithmia_api_key)
    print("starting process", flush=True)
    input1_q = Queue(500)
    input2_q = Queue(500)
    processed_q = Queue(500)
    thread_locker = PoolManger(0, initial_pool, 2)
    consume_t = [Thread(target=consume, args=(logger, aws_creds, input1_q, input2_q, input_stream_name))]
    publish_t = [
        Thread(target=publish, args=(logger, aws_creds, output_stream_name, processed_q, input2_q, thread_locker, fps))]
    threads = [Thread(target=process, args=(logger, client, input1_q, processed_q, thread_locker, data_collection, fps)) for
               _ in range(100)]
    threads += consume_t + publish_t
    [thread.start() for thread in threads]
    while True:
        logger.read_next()
