# PATH to the import directory of the activated Neo4j DB, e.g:

analysis_database_path = 'C:\\Users\\user\\.Neo4jDesktop\\neo4jDatabases\\database-a5cab528-5b2d-4309-8160-2d79d0799193\\installation-3.5.6\\import\\'

# Credentials for the Neo4j DB to store all the information in

analysis_database_uri = "bolt://localhost:7687"
analysis_database_user = "neo4j"
analysis_database_password = "user"

# Amount of threads to employ when committing data to the neo4j DB
THREAD_COUNT = 70

# Amount of relationship dictionaries to send in a single transaction to the neo4j DB
BATCH_SIZE = 150

# Number of retry attempts to make when an error occured in the relationship committing process
RETRIES = 5
