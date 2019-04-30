
# PATH to the import directory of the activated Neo4j DB, e.g:
# path = 'C:\\.Neo4jDesktop\\neo4jDatabases\\database-924d535e-f415-4824-8c6d-653b2e50f04d\\installation-3.5.4\\\import\\'

path = 'C:\\Users\\user\\.Neo4jDesktop\\neo4jDatabases\\database-826404ce-4d55-459a-a9ec-5d75a8b1d807\\installation-3.5.4\\\import\\'

# Credentials for the Neo4j DB to store all the information in

uri = "bolt://localhost:7687"
user = "neo4j"
password = "user"

# Amount of threads to employ when committing data to the neo4j DB
THREAD_COUNT = 32

# Amount of relationship dictionaries to send in a single transaction to the neo4j DB
BATCH_SIZE = 30

# Number of retry attempts to make when an error occured in the relationship committing process
RETRIES = 5
