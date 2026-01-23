from celery import Celery

# 配置 RabbitMQ 连接地址
BROKER_URL = 'amqp://jay:comp0235@10.134.12.72:5672//'

app = Celery('protein_pipeline', broker=BROKER_URL)

app.conf.update(
    result_backend='rpc://',
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='Europe/London',
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue='celery'
)

if __name__ == "__main__":
    app.start()
