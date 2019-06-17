def get_node_label_map(driver):
    # Return a mapping of all labels in the graph with the literal 'Hash'.
    # This is used in the apoc.search.node function call.
    with driver.session() as session:
        result = session.run("MATCH (n) "
                             "RETURN distinct(labels(n))[0] as labels ")
        node_label_mapping = dict()
        for record in result:
            node_label_mapping.update({record[0]: 'Hash'})

    return node_label_mapping
