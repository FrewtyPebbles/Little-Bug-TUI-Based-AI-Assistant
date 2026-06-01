from cassandra import cluster

def create_session():
    cluster = Cluster()
    session = cluster.connect()

    # Create keyspace, if already have keyspace your can skip this
    os.environ['CQLENG_ALLOW_SCHEMA_MANAGEMENT'] = 'true'
    connection.register_connection('cqlengine', session=session, default=True)
    management.create_keyspace_simple('example', replication_factor=1)
    management.sync_table(User, keyspaces=['example'])

    # Wrap cqlengine connection
    aiosession_for_cqlengine(session)
    session.set_keyspace('example')
    connection.set_session(session)
    return session
