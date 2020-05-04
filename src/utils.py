from kinesis.consumer import KinesisConsumer
from kinesis.state import DynamoDB
from kinesis.producer import KinesisProducer

def create_consumer(stream_name, session, db_name=None):
    if db_name:
        consumer = KinesisConsumer(stream_name=stream_name, boto3_session=session, state=DynamoDB(db_name, session))
    else:
        consumer = KinesisConsumer(stream_name=stream_name, boto3_session=session)
    return consumer


def create_producer(stream_name, session):
    producer = KinesisProducer(stream_name=stream_name, boto3_session=session)
    return producer
