from celery import Celery

# 配置 RabbitMQ 连接地址
BROKER_URL = 'amqp://jay:comp0235@10.134.12.72:5672//'

app = Celery('protein_pipeline', broker=BROKER_URL)

app.conf.update(
    result_backend='rpc://',
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    task_acks_late=True,
    task_default_queue='celery'
)
