# This module contain helper functions for propagating sub-graphs with the correct context information.
# This situation is caused when the binary view contains 2 identical objects (for example 2 identical basic blocks)
# and the cache mechanism prevents us from creating nodes and relationships under the second basic block encountered
# in order to save time.
# The duplicated object is added to the uuid_propagation map and this module creates all neccesarry relationships
# in the corresponding csv file.


class UUIDPropagator:
    def __init__(self, uuid_propagation_map, object_map):
        self.uuid_propagation_map = uuid_propagation_map
        self.object_map = object_map

    def dispatch_uuid_propagation(self):
        """
        Read a row from the uuid_propagation  and dispatch the correct
        param: uuid_propagation_map: a mapping where the key is the existing uuid and the value is a list of relationship
                                     contexts to insert. See BuildCSV.uuid_propagation_map for info
        """

    def propagate_function(self):
        for program_entity in self.object_map:
            for object in self.object_map[program_entity]:
                # We are only interested in duplicating relationships, not nodes
                if object['Object']['UUID'] in self.uuid_propagation_map:
                    for context in self.uuid_propagation_map[object['Object']['UUID']]:
                        original_row = object
                        original_row.update(context)
                        original_row['WriteNode'] = False
                        self.uuid_propagation_map.append(original_row)
