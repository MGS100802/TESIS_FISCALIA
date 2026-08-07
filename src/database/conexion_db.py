import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

# Cambiamos 'localhost' por '127.0.0.1' para evitar el conflicto con IPv6
URI = "bolt://127.0.0.1:7687"
USER = "neo4j"
PASSWORD = "Mgs21085$$"  # Asegúrate de que coincida con tu clave de Neo4j

def probar_conexion():
    try:
        driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
        driver.verify_connectivity()
        print("¡Conexión exitosa con Neo4j! La base de datos de grafos está lista.")
        driver.close()
    except Exception as e:
        print(f"Error al conectar con Neo4j: {e}")

if __name__ == "__main__":
    probar_conexion()