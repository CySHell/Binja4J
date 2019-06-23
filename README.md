# Binja4J

This project aims to leverage both the static analysis capabilities of the Binary Ninja platform and the Graph DB capabilities of Neo4j.
The combination of these powerful tools will hopefully allow for sophisticated and efficient program analysis algorithms to be developed.

Before the graph is populated, It is possible to utilize a tool that parses any c header file and stores the definition within the graph, and then defines all recognized functions within the BinaryView. 
Following is a demo of this capability after parsing all windows headers (windows.h): 
![image](https://user-images.githubusercontent.com/34336222/59976825-63b52f00-95d2-11e9-9573-ecda09866dca.gif)


Please note that only MEDIUM LEVEL IL (MLIL) exporting is supported, not raw assembly. 

  REQUIREMENTS:
  - Neo4j database
    * Install Neo4j Desktop: https://neo4j.com/docs/operations-manual/current/installation/neo4j-desktop/index.html
    * Create a local Database:
       1. DB connection details can be edited in Configuration.py
       2. Default credentials for Bin4J are "neo4j" \ "user", default local port is "bolt://localhost:7687"
       3. install the pypy neo4j module: "pip install neo4j"
       4. Create a new DB and install the APOC plugin:
       ![image](https://user-images.githubusercontent.com/34336222/56972290-687dd980-6b73-11e9-9690-277af1cb64a4.PNG)
       
       5. Start the DB via the Neo4j Desktop application
       6. Locate the import directory of the specific Neo4j DB you've started
          * Update the "path" variable in Configuration.py 
       
   - xxhash : "pip install xxhash"
   
  USAGE   
  - Place this repository in your BinaryNinja plugins directory
  - Start the Neo4j DB via the Neo4j Desktop application
  ![image](https://user-images.githubusercontent.com/34336222/56973099-dbd41b00-6b74-11e9-8e02-5ef5470416aa.PNG)
  
  - Run the Binja4J plugin on any executable
  - Manually run the ExportNeo4j.py python script
  - Enjoy your brand new graph DB
  
  Enriching the Graph
  - Each node and relationship in the graph has a corresponding class in the /extraction_helpers folder
  - Each of the classes has a dictionary composed inside the self.serialize() function
  - Simply add any information you want to enrich the graph with into the "node_attributes" and "relationship_attributes" 
    sub-dictionaries
  - This information will automatically be propegated into the graph
  
  Graph Representation
  
  - The basic graph representation in the graph DB uses the following Ontology:
![image](https://user-images.githubusercontent.com/34336222/58807914-aa41ea00-8621-11e9-877f-d92310b0296d.png)
  
  
  Demo Screenshots
  
  ![image](https://user-images.githubusercontent.com/34336222/56093138-59d5c800-5ecd-11e9-8de4-1d6256406d32.PNG)
