import os
from pymongo import MongoClient
from utilities.custom_logger import get_logger

logger = get_logger('db_connection')

# Fetch MongoDB URI from environment or default to local
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
DB_NAME = os.getenv('MONGO_DB_NAME', 'aedip')

try:
    # Initialize PyMongo Client
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]
    
    # Test connection
    client.server_info()
    logger.info(f"Successfully connected to MongoDB database '{DB_NAME}' at {MONGO_URI}")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {str(e)}")
    db = None

def get_db():
    """Return the database instance."""
    return db

def initialize_db_indexes():
    """Initialize necessary indexes for performance and constraints."""
    if db is None:
        logger.warning("Database connection is not initialized. Cannot create indexes.")
        return
        
    try:
        # Organizations & Workspaces
        db.organizations.create_index("name", unique=True)
        db.workspaces.create_index("owner_id")
        db.workspaces.create_index("organization_id")

        # Users indexes
        db.users.create_index("email", unique=True)
        db.users.create_index("role")
        
        # Projects indexes
        db.projects.create_index("owner_id")
        db.projects.create_index("workspace_id")
        
        # Datasets indexes
        db.datasets.create_index("project_id")
        db.datasets.create_index("created_at")

        # Dataset Versions & Data Quality
        db.dataset_versions.create_index("dataset_id")
        db.dataset_versions.create_index([("dataset_id", 1), ("version", 1)], unique=True)
        db.data_quality_reports.create_index("dataset_id")

        # Data Lineage
        db.data_lineage.create_index("project_id")
        db.data_lineage.create_index("dataset_id")
        
        # Models indexes
        db.models.create_index("project_id")
        db.models.create_index("dataset_id")
        
        # Predictions indexes
        db.predictions.create_index("model_id")
        db.predictions.create_index("dataset_id")
        
        # Reports indexes
        db.reports.create_index("project_id")
        
        # Audit Logs & User Activities indexes
        db.audit_logs.create_index("user_id")
        db.audit_logs.create_index("timestamp")
        db.user_activities.create_index("user_id")
        db.user_activities.create_index("timestamp")
        
        # Saved Queries
        db.saved_queries.create_index("project_id")
        
        # Notifications & Alerts indexes
        db.notifications.create_index("user_id")
        db.notifications.create_index([("user_id", 1), ("is_read", 1)])
        db.alerts.create_index("project_id")
        db.alerts.create_index("timestamp")

        # Conversations & Messages
        db.conversations.create_index("project_id")
        db.messages.create_index("conversation_id")

        # Scenarios & Personas
        db.scenarios.create_index("project_id")
        db.scenarios.create_index("model_id")
        db.business_personas.create_index("project_id")
        
        logger.info("Successfully initialized MongoDB database indexes.")
    except Exception as e:
        logger.error(f"Error initializing MongoDB indexes: {str(e)}")

# Initialize indexes on startup
if db is not None:
    initialize_db_indexes()
