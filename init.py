import docker
from docker.models.images import Image
from docker.models.containers import _create_container_args
import yaml
import shutil
from multiprocessing import Process, Queue
from distutils.dir_util import copy_tree
import sys, os, time
from pathlib import Path
from jinja2 import Template

def build_image(docker_client, host_url, index_jinja_path, dockerfile_path, image_tag):
    with open(index_jinja_path) as f:
        raw_template = f.read()
    index_template = Template(raw_template)
    output_path = index_jinja_path.split('.j2')[0]
    index_string = index_template.render(host=host_url)
    with open(output_path, 'w') as f:
        f.write(index_string)
    try:
        image, _ = docker_client.images.build(path=".", dockerfile=dockerfile_path, tag=image_tag, rm=True)
        return image
    except docker.errors.BuildError as e:
        for line in e.build_log:
            if 'stream' in line:
                print(line)
        raise e


def run_container(client, image, algorithmia_api_key, algorithmia_api_address, mode, local_aws=False, networking=False):
    raw_args = {}

    if isinstance(image, Image):
        image = image.id
    raw_args['image'] = image
    raw_args['version'] = client.containers.client.api._version
    home_dir = str(Path.home())
    aws_dir = os.path.join(home_dir, ".aws")
    if networking and local_aws:
        raw_args['ports'] = {80: 80}
        container_args = _create_container_args(raw_args)
        container_args['host_config'] = client.api.create_host_config(port_bindings={80: ("127.0.0.1", 80)},
                                                                      binds={aws_dir: {'bind': "/root/.aws", "mode": "ro"}})
        container_args['volumes'] = ["/root/.aws"]
    elif networking:
        raw_args['ports'] = {80: 80}
        container_args = _create_container_args(raw_args)
        container_args['host_config'] = client.api.create_host_config(port_bindings={80: ("127.0.0.1", 80)})
    elif local_aws:
        container_args = _create_container_args(raw_args)
        container_args['host_config'] = client.api.create_host_config(binds={aws_dir: {'bind': "/root/.aws", "mode": "ro"}})
        container_args['volumes'] = ["/root/.aws"]

    else:
        container_args = _create_container_args(raw_args)
    container_args['detach'] = True
    container_args['environment'] = {}
    container_args['environment']['ALGORITHMIA_API_KEY'] = algorithmia_api_key
    container_args['environment']['ALGORITHMIA_API_ADDRESS'] = algorithmia_api_address
    container_args['environment']['MODE'] = mode

    resp = client.api.create_container(**container_args)
    client.api.start(resp['Id'])
    return resp['Id']


def stop_and_kill_containers(docker_client, all=False):
    """
    Kills all docker containers, if all is =true, it kills all containers whether running or not
    :param docker_client: The docker python client
    :param all: Boolean variable defining whether we destroy 'all' docker containers, or just running ones
    :return: None
    """
    containers = docker_client.containers.list(all=all, ignore_removed=True)
    for container in containers:
        try:
            container.remove(force=True)
        except docker.errors.APIError:
            pass


def kill_dangling_images(docker_client):
    """
    Kills all dangling images, to free up disk space
    :param docker_client: The docker python client
    :return: None
    """
    images = docker_client.images.list()
    for image in images:
        if len(image.tags) == 0:
            docker_client.images.remove(image.id, force=True)


def copy_aws_dir():
    print("copying creds")
    home_path = os.getenv("HOME", None)
    aws_cred_path = os.path.join(home_path, ".aws")
    copy_tree(aws_cred_path, ".aws")


def get_log_and_push(logger, queue, name):
    for message in logger:
        message = str(message, 'utf-8')
        messages_split = message.split('\n')[0:-1]
        for message in messages_split:
            queue.put("{} - {}".format(name, message))


client = docker.from_env()

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            mode = str(sys.argv[1])
        else:
            mode = None
        with open('config.yaml') as f:
            data = yaml.safe_load(f)
        if 'aws' in data and 'credentials' in data['aws']:
            creds = data['aws']['credentials']
            if 'IAM' in creds and isinstance(creds['IAM'], dict) and 'local_iam' in creds['IAM']:
                copy_aws_dir()
                local_credentials = True
            else:
                local_credentials = False
        else:
            raise Exception("your 'config.yaml' file is misconfigured around 'aws'")
        if 'algorithmia' in data and ('api_key' in data['algorithmia'] and 'api_address' in data['algorithmia']):
            api_key = data['algorithmia']['api_key']
            api_address = data['algorithmia']['api_address']
        else:
            raise Exception("your 'config.yaml' file is misconfigured around 'algorithmia'")
        if 'video' in data and isinstance(data['video'], dict):
            host = data['video']['host']
        else:
            raise Exception("your 'config.yaml' file is misconfigured around 'video'")
        image = build_image(client, host, "src/www/index.html.j2", "Dockerfile", "streaming")
        if mode:
            if mode == "generate":
                container = run_container(client, image, api_key, api_address, "generate", local_aws=local_credentials)
            elif mode == "process":
                container = run_container(client, image, api_key, api_address, "process", local_aws=local_credentials)
            elif mode == "broadcast":
                container = run_container(client, image, api_key, api_address, "broadcast", local_aws=local_credentials,
                                          networking=True)
            else:
                raise Exception(
                    "variable passed to init.py was {}, must be 'generate', 'process', or 'broadcast'".format(mode))
            logger = client.api.attach(container, stream=True, logs=True, stdout=True, stderr=True)
            for msg in logger:
                print(str(msg, 'utf-8'))
        else:
            logging_queue = Queue()
            generator = run_container(client, image, api_key, api_address, "generate", local_aws=local_credentials)
            processor = run_container(client, image, api_key, api_address, "process", local_aws=local_credentials)
            broadcaster = run_container(client, image, api_key, api_address, "broadcast", local_aws=local_credentials, networking=True)
            streams = [(container_name, client.api.attach(container, stdout=True, logs=True, stderr=True, stream=True))
                       for
                       container_name, container in
                       [("generate", generator), ("process", processor), ("broadcast", broadcaster)]]
            threads = [Process(target=get_log_and_push, args=(stream, logging_queue, name)) for name, stream in streams]
            [thread.start() for thread in threads]
            print("streaming started, connecting to containers")
            while True:
                if logging_queue.empty():
                    time.sleep(0.25)
                else:
                    msg = logging_queue.get()
                    print(msg)

    except KeyboardInterrupt as e:
        print("killing")
        stop_and_kill_containers(client, True)
        path = os.path.join(os.getcwd(), '.aws')
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
    except Exception as e:
        print("killing")
        stop_and_kill_containers(client, True)
        path = os.path.join(os.getcwd(), '.aws')
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
        raise e
