import duckdb

# 1. Connect to a persistent file (this creates kg_index.db)
con = duckdb.connect('knowledge_graph/data/kg_index.db')

# 2. Import the parquet data into a real table
print("🚀 Indexing Knowledge Graph...")
con.execute("CREATE TABLE primekg AS SELECT * FROM read_parquet('trialcpg/knowledge_graph/data/kg.parquet')")

# 3. Create an INDEX on the drug name column (CRITICAL FOR SPEED)
con.execute("CREATE INDEX idx_drug_name ON primekg (x_name)")

con.close()
print("✅ Index created! Queries will now be instant.")