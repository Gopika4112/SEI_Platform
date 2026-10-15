from neo4j import GraphDatabase
from typing import List, Dict, Any, Tuple

class GraphStoreManager:
    """
    Manages connections, schema indexes, and batch transactions to Neo4j
    graph database using Cypher.
    """
    def __init__(self, uri: str = "bolt://127.0.0.1:7687", user: str = "neo4j", password: str = "password123"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._setup_schema()

    def close(self):
        """Closes the active database driver connection."""
        self.driver.close()

    def _setup_schema(self):
        """
        Creates schema constraints and indexes on startup to optimize 
        node lookups during ingestion and query execution.
        """
        queries = [
            # Ensure unique File paths
            "CREATE CONSTRAINT FOR (f:File) REQUIRE f.file_path IS UNIQUE",
            # Create fast lookup indexes on name properties
            "CREATE INDEX FOR (c:Class) ON (c.name)",
            "CREATE INDEX FOR (fn:Function) ON (fn.name)",
            "CREATE INDEX FOR (m:Method) ON (m.name)",
            "CREATE INDEX FOR (mod:Module) ON (mod.name)"
        ]
        with self.driver.session() as session:
            for q in queries:
                try:
                    session.run(q)
                except Exception:
                    # Ignore if constraint/index already exists
                    pass

    def create_nodes_and_edges(self, nodes: List[Dict[str, Any]], relationships: List[Tuple[Dict[str, Any], str, Dict[str, Any]]]):
        """
        Saves a batch of nodes and relationships to Neo4j using efficient Cypher MERGE statements.
        
        Args:
            nodes: List of node dictionaries containing 'name', 'label', and 'metadata'.
            relationships: List of tuples representing (source_node, type, target_node).
        """
        if not nodes and not relationships:
            return
            
        with self.driver.session() as session:
            # 1. Insert Nodes in batches grouped by label
            # Separate nodes by label to use optimized Cypher templates
            nodes_by_label = {}
            for node in nodes:
                label = node["label"]
                nodes_by_label.setdefault(label, []).append(node)
                
            for label, label_nodes in nodes_by_label.items():
                if label == "Module":
                    # Global Modules (like os, sys) are merged globally on name only
                    cypher = """
                    UNWIND $props AS row
                    MERGE (n:Module {name: row.name})
                    SET n += row.metadata
                    """
                elif label == "File":
                    # Files are merged on absolute path (stored as file_path)
                    cypher = """
                    UNWIND $props AS row
                    MERGE (n:File {file_path: row.metadata.absolute_path})
                    SET n.name = row.name, n += row.metadata
                    """
                else:
                    # Classes, Methods, Functions are scoped uniquely to their containing file
                    cypher = f"""
                    UNWIND $props AS row
                    MERGE (n:{label} {{file_path: row.metadata.file_path, name: row.name}})
                    SET n += row.metadata
                    """
                
                session.run(cypher, props=label_nodes)

            # 2. Insert Relationships in batches grouped by relation type
            rels_by_type = {}
            for src, rel_type, dst in relationships:
                rels_by_type.setdefault(rel_type, []).append({
                    "src_name": src["name"],
                    "src_label": src["label"],
                    "src_file_path": src["metadata"].get("file_path") or src["metadata"].get("absolute_path"),
                    "dst_name": dst["name"],
                    "dst_label": dst["label"],
                    "dst_file_path": dst["metadata"].get("file_path") or dst["metadata"].get("absolute_path")
                })

            for rel_type, r_list in rels_by_type.items():
                # Neo4j query matches nodes based on unique keys and merges the specific edge
                if rel_type == "IMPORTS":
                    # IMPORTS links File (matched by file_path) to Module (matched globally by name)
                    cypher = """
                    UNWIND $rels AS r
                    MATCH (src:File {file_path: r.src_file_path})
                    MATCH (dst:Module {name: r.dst_name})
                    MERGE (src)-[:IMPORTS]->(dst)
                    """
                else:
                    # Local relationships (CALLS, INHERITS, DEFINED_IN, HAS_METHOD) match on file_path + name
                    cypher = f"""
                    UNWIND $rels AS r
                    MATCH (src:{rel_type}_placeholder {{file_path: r.src_file_path, name: r.src_name}})
                    MATCH (dst:{rel_type}_placeholder2 {{file_path: r.dst_file_path, name: r.dst_name}})
                    MERGE (src)-[:{rel_type}]->(dst)
                    """
                    # Replace label placeholders dynamically with exact labels
                    # Cypher doesn't support parameterized node labels, so we format them safely
                    # Since these labels come directly from our system models (Class, Function, Method, File),
                    # this dynamic replacement is safe and avoids sql-injection type vulnerabilities.
                    
                for r in r_list:
                    # Execute each relationship link
                    # Determine search parameters based on label
                    src_label = r["src_label"]
                    dst_label = r["dst_label"]
                    
                    if rel_type == "IMPORTS":
                        # IMPORTS is handled in batch by the UNWIND query above
                        continue
                    elif rel_type == "DEFINED_IN" and dst_label == "File":
                        # Links Class/Method/Function to File node
                        cypher_single = f"""
                        MATCH (src:{src_label} {{file_path: $r.src_file_path, name: $r.src_name}})
                        MATCH (dst:File {{file_path: $r.dst_file_path}})
                        MERGE (src)-[:DEFINED_IN]->(dst)
                        """
                    else:
                        cypher_single = f"""
                        MATCH (src:{src_label} {{file_path: $r.src_file_path, name: $r.src_name}})
                        MATCH (dst:{dst_label} {{file_path: $r.dst_file_path, name: $r.dst_name}})
                        MERGE (src)-[:{rel_type}]->(dst)
                        """
                    session.run(cypher_single, r=r)
                    
                if rel_type == "IMPORTS":
                    session.run(cypher, rels=r_list)

    def run_query(self, cypher_query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Runs an arbitrary Cypher query and returns the list of matched results.
        
        Args:
            cypher_query: The Cypher query string.
            parameters: Optional query parameters.
            
        Returns:
            A list of dictionary records representing matching graphs.
        """
        with self.driver.session() as session:
            result = session.run(cypher_query, parameters or {})
            return [dict(record) for record in result]
