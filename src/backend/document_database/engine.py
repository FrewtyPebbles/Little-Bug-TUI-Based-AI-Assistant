from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from backend.config import ENVIRONMENT

def __create_cassandra_connection(host:str = ENVIRONMENT.CASSANDRA_HOST):
    auth_provider = PlainTextAuthProvider(
        username=ENVIRONMENT.CASSANDRA_USER,
        password=ENVIRONMENT.CASSANDRA_PASSWORD
    )
    CASSANDRA_CLUSTER = Cluster(
        [host],
        auth_provider=auth_provider
    )
    CASSANDRA_SESSION = CASSANDRA_CLUSTER.connect()

    return CASSANDRA_CLUSTER, CASSANDRA_SESSION

CASSANDRA_CLUSTER, CASSANDRA_SESSION = __create_cassandra_connection()