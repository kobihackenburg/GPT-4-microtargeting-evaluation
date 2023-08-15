import os
from redis import Redis
from rq import Worker, Queue, Connection

listen = ['high', 'default', 'low']

# replace with redis url from heroku (test)
redis_url = os.getenv('REDISTOGO_URL', 'rediss://:pc27cbd8577149057fd408f22e0e0ad85efae39203fb9e67ec321ec0d7f6aec6d@ec2-52-30-102-197.eu-west-1.compute.amazonaws.com:17539')

conn2 = Redis.from_url(redis_url, ssl_cert_reqs=None)

if __name__ == '__main__':
    with Connection(conn2):
        worker = Worker(map(Queue, listen))
        worker.work()