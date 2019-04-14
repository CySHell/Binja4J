# Binja4J

This project aims to leverage both the static analysis capabilities of the Binary Ninja platform and the Graph DB capabilities of Neo4j.
The combination of these powerful tools will hopefully allow for sophisticated and efficient program analysis algorithms to be developed.

Please note that only MEDIUM LEVEL IL (MLIL) exporting is supported, not raw assembly.

  REQUIREMENTS:
  - Neo4j database
    * Install Neo4j Desktop: https://neo4j.com/docs/operations-manual/current/installation/neo4j-desktop/index.html
    * Create a local Database:
       1. DB connection details can be edited in the file database.py and ExportNeo4j.py
       2. Default credentials for Binja4J are "neo4j" \ "user", default local port is "bolt://localhost:7687"
       3. install the pypy neo4j module: "pip install neo4j"
       4. Start the DB via the Neo4j Desktop application
       5. Install the APOC plugin for the Neo4j Project (this is done from within the Neo4j Desktop application)
       6. Locate the import directory of the specific Neo4j DB you've started
          * Update the "path" variable in ExportNeo4j.py and database.py 
       
   - xxhash : "pip install xxhash"
   
  USAGE   
  - Place this repository in your BinaryNinja plugins directory
  - Start the Neo4j DB via the Neo4j Desktop application
  - Run the Binja4J plugin on any executable
  - Manually run the ExportNeo4j.py python script
  - Enjoy your brand new graph DB
  
  
  Graph Representation
  
  - The basic graph representation in the graph DB uses the following Ontology:
  
  ![image](https://user-images.githubusercontent.com/34336222/56093078-e5028e00-5ecc-11e9-8e22-c16e0c70a3b8.png)
  
  
  Demo Screenshots
  
  ![image](https://user-images.githubusercontent.com/34336222/56093138-59d5c800-5ecd-11e9-8de4-1d6256406d32.PNG)
