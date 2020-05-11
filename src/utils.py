from kinesis.consumer import KinesisConsumer
from kinesis.state import DynamoDB
from kinesis.producer import KinesisProducer
import boto3

def create_consumer(stream_name, session, db_name=None):
    if db_name:
        consumer = KinesisConsumer(stream_name=stream_name, boto3_session=session, state=DynamoDB(db_name, session))
    else:
        consumer = KinesisConsumer(stream_name=stream_name, boto3_session=session)
    return consumer


def create_producer(stream_name, session):
    producer = KinesisProducer(stream_name=stream_name, boto3_session=session)
    return producer


def credential_auth(aws_creds):
    if 'access_keys' in aws_creds:
        access_keys = aws_creds['access_keys']
        session = boto3.Session(access_keys['access_key'], access_keys['secret'], region_name=aws_creds['region_name'])
    elif 'IAM' in aws_creds:
        iam = aws_creds['IAM']
        if iam and 'local_iam' in iam:
            session = boto3.Session(profile_name=iam['local_iam']['profile_name'], region_name=aws_creds['region_name'])
        else:
            session = boto3.Session(region_name=aws_creds['region_name'])
    else:
        raise Exception("aws credentials pulled from yaml file must either define 'access_keys' or 'IAM' as authentication paths")
    return session
