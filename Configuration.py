# PATH to the import directory of the activated Neo4j DB, e.g:

analysis_database_path = 'C:\\Users\\user\\.Neo4jDesktop\\neo4jDatabases\\database-fcc352f4-1ce6-469c-8081-39ae41e637e5\\installation-3.5.7\\import\\'


# Credentials for the Neo4j DB to store all the information in

analysis_database_uri = "bolt://localhost:7687"
analysis_database_user = "neo4j"
analysis_database_password = "user"

# Minimum amount of mlil basic blocks required in each analyzed function
MIN_MLIL_BASIC_BLOCKS = 1

# Amount of threads to employ when committing data to the neo4j DB
THREAD_COUNT = 25

# Amount of relationship dictionaries to send in a single transaction to the neo4j DB
BATCH_SIZE = 150

# Number of retry attempts to make when an error occured in the relationship committing process
RETRIES = 5
