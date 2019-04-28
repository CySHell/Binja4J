################################################################################################################
#                                       UUID                                                                   #
################################################################################################################

class UUID:
    """
    UUID object, used to synchronize the UUID of any new object created in the graph.
    Neo4j should take care of the sync locks of multithreading, making this thread-safe.

    # TODO: Store UUID in a more efficient manner, not wasting UUID's on duplicate objects (because of the CSV export)
    """

    def __init__(self, driver, chunk_size=1000):
        """
        :param driver: (Neo4j_Bolt_Driver) connector to the relevant DB
        """

        self._driver = driver
        self._chunk_size = chunk_size  # how many _uuid's to supply to a consumer of this class in a single call
        self.uuid_list = self._get_chunk(chunk_size)

    def _get_chunk(self, size):
        """
        Create a thread safe way to give a chunk of _uuid's to a thread for consumption
        :param size: (INT) how many _uuid's are needed?
        :return: chunk_start: (INT)
        """
        with self._driver.session() as session:
            return session.run("CALL apoc.create.uuids(" + str(size) + "    ) "
                                                                       "YIELD uuid "
                                                                       "RETURN collect(uuid)").single().value()

    def get_uuid(self):
        """
        returns a _uuid for a consumer of the class to use.
        responsible for fetching more chunks from the DB if the current chunk is complete.
        :return: uuid: (string)
        """
        if not self.uuid_list:
            self.uuid_list = self._get_chunk(self._chunk_size)

        return self.uuid_list.pop()
