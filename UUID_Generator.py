"""
Define data structures to hold information regarding the following components of the binary view:
    - binary view itself
    - MLIL function
    - MLIL basic block
    - MLIL instruction

All structures defined here will be serve as a schema for the neo4j graph
"""

import threading


################################################################################################################
#                                       UUID                                                                   #
################################################################################################################

class UUID:
    """
    UUID object, used to synchronize the UUID of any new object created in the graph.
    Neo4j should take care of the sync locks of multithreading, making this thread-safe.

    # TODO: Store UUID in a more efficient manner, not wasting UUID's on duplicate objects (because of the CSV export)
    """

    _singleton_exists = False
    _lock = threading.Lock()
    _modulu_helper = 0

    def __init__(self, driver, chunk_size=600):
        """
        :param driver: (Neo4j_Bolt_Driver) connector to the relevant DB
        """

        if not self._singleton_exists:
            self._singleton_exists = True
        else:
            print("ERROR, cant create more then one UUID object")
            return

        self._driver = driver
        self._chunk_size = chunk_size  # how many _uuid's to supply to a consumer of this class in a single call
        self._modulu_helper = chunk_size

        with driver.session() as session:
            uuid = session.run("MATCH (n:UUID)"
                               "return n.uuid")
            if not uuid.peek():
                session.run("CREATE (:UUID {uuid: 1})")
                self._uuid = 1
            else:
                self._uuid = self._get_current_uuid()

    def _get_current_uuid(self):
        """
        internal function - receives the current _uuid pointed by the _uuid node
        :return: _uuid: (INT) the current _uuid
        """
        with self._driver.session() as session:
            uuid = session.run("MATCH (n:UUID)"
                               "RETURN n.uuid")

            return int(uuid.peek()['n.uuid'])

    def _set_current_uuid(self, new_uuid):
        """
        internal function - sets the current _uuid pointed by the _uuid node
        :return: _uuid: (INT) the current _uuid
        """
        with self._driver.session() as session:
            uuid = session.run("MATCH (n:UUID)"
                               "SET n.uuid = {new_uuid}"
                               "RETURN n.uuid",
                               new_uuid=new_uuid)

            return int(uuid.peek()['n.uuid'])

    def _get_chunk(self, size):
        """
        Create a thread safe way to give a chunk of _uuid's to a thread for consumption
        :param size: (INT) how many _uuid's are needed?
        :return: chunk_start: (INT)
        """
        chunk_start = self._get_current_uuid()
        self._set_current_uuid(chunk_start + size)
        return chunk_start

    def get_uuid(self):
        """
        returns a _uuid for a consumer of the class to use.
        responsible for fetching more chunks from the DB if the current chunk is complete.
        :return: _uuid: (INT)
        """
        if self._modulu_helper == self._chunk_size:
            # consumed the current chunk, get another one from DB
            self._modulu_helper = 0
            self._uuid = self._get_chunk(self._chunk_size)
            return self._uuid
        else:
            self._modulu_helper += 1
            self._uuid += 1
            return self._uuid
