import os
import json
import datetime
import pandas as pd
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_api
from apps.authentication.views import log_user_activity
from apps.nlp_query_engine.interpreter import NLQueryInterpreter
from utilities.custom_logger import get_logger

logger = get_logger('nlp_views')
db = get_db()

@csrf_exempt
@login_required_api
def api_run_nlp_query(request):
    """Process natural language business analytics queries."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)
        
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    try:
        data = json.loads(request.body)
        dataset_id = data.get('dataset_id')
        query_text = data.get('query', '').strip()
        
        if not dataset_id or not query_text:
            return JsonResponse({"error": "dataset_id and query are required."}, status=400)
            
        # Retrieve dataset path
        dataset = db.datasets.find_one({"_id": ObjectId(dataset_id)})
        if not dataset:
            return JsonResponse({"error": "Dataset not found."}, status=404)
            
        file_path = dataset.get('cleaned_file_path') or dataset.get('file_path')
        if not file_path or not os.path.exists(file_path):
            return JsonResponse({"error": "Dataset file not found on server."}, status=400)
            
        # Read dataset
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.csv':
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
            
        if df.empty:
            return JsonResponse({"error": "Dataset is empty."}, status=400)
            
        # Execute Interpreter
        interpreter = NLQueryInterpreter(df)
        result = interpreter.interpret(query_text)
        
        # Save query record to MongoDB & handle Conversation Persistence
        conversation_id = data.get('conversation_id')
        if conversation_id:
            # Save User message
            db.messages.insert_one({
                "conversation_id": ObjectId(conversation_id),
                "sender": "user",
                "text": query_text,
                "timestamp": datetime.datetime.utcnow()
            })
            # Save AI response
            db.messages.insert_one({
                "conversation_id": ObjectId(conversation_id),
                "sender": "ai",
                "text": result.get("text"),
                "chart_data": result.get("chart"),
                "timestamp": datetime.datetime.utcnow()
            })

        query_doc = {
            "project_id": dataset.get("project_id"),
            "user_id": ObjectId(request.user_data['id']),
            "query": query_text,
            "response": result.get("text"),
            "chart_data": result.get("chart"),
            "conversation_id": ObjectId(conversation_id) if conversation_id else None,
            "created_at": datetime.datetime.utcnow()
        }
        db.saved_queries.insert_one(query_doc)
        
        # Log Audit
        log_user_activity(
            request.user_data['id'],
            "NLP_QUERY",
            f"Submitted natural language query: '{query_text}'.",
            request
        )
        
        return JsonResponse({
            "query": query_text,
            "text_response": result.get("text"),
            "chart_response": result.get("chart"),
            "conversation_id": conversation_id
        }, status=200)
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)
    except Exception as e:
        logger.error(f"NLP query execution failed: {str(e)}")
        return JsonResponse({"error": f"Failed to execute query: {str(e)}"}, status=500)

@csrf_exempt
@login_required_api
def api_list_conversations(request, project_id):
    """Retrieve persistent analytical conversations for a project."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
    conversations = list(db.conversations.find({"project_id": ObjectId(project_id)}).sort("created_at", -1))
    for cv in conversations:
        cv['_id'] = str(cv['_id'])
        cv['project_id'] = str(cv['project_id'])
    return JsonResponse({"conversations": conversations}, status=200)

@csrf_exempt
@login_required_api
def api_create_conversation(request):
    """Create a new persistent conversation session."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
    try:
        data = json.loads(request.body)
        project_id = data.get('project_id')
        title = data.get('title', 'New Analytics Session').strip()
        if not project_id:
            return JsonResponse({"error": "project_id is required."}, status=400)
        cv_doc = {
            "project_id": ObjectId(project_id),
            "title": title,
            "created_at": datetime.datetime.utcnow()
        }
        res = db.conversations.insert_one(cv_doc)
        cv_id = str(res.inserted_id)
        
        # Insert initial AI welcome message
        db.messages.insert_one({
            "conversation_id": ObjectId(cv_id),
            "sender": "ai",
            "text": "Hello! Ask me any questions about the dataset, like regional performances, monthly declines, or predictive sales.",
            "timestamp": datetime.datetime.utcnow()
        })
        
        return JsonResponse({"message": "Conversation created.", "conversation_id": cv_id, "title": title}, status=201)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required_api
def api_rename_conversation(request):
    """Rename an existing conversation title."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
    try:
        data = json.loads(request.body)
        cv_id = data.get('conversation_id')
        title = data.get('title', '').strip()
        if not cv_id or not title:
            return JsonResponse({"error": "conversation_id and title are required."}, status=400)
        db.conversations.update_one({"_id": ObjectId(cv_id)}, {"$set": {"title": title}})
        return JsonResponse({"message": "Conversation renamed."}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required_api
def api_delete_conversation(request, conversation_id):
    """Delete a conversation session and all its messages."""
    if request.method != 'DELETE':
        return JsonResponse({"error": "Method not allowed. Use DELETE."}, status=405)
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
    try:
        db.conversations.delete_one({"_id": ObjectId(conversation_id)})
        db.messages.delete_many({"conversation_id": ObjectId(conversation_id)})
        return JsonResponse({"message": "Conversation deleted successfully."}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required_api
def api_get_messages(request, conversation_id):
    """Retrieve message history for a conversation session."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
    messages = list(db.messages.find({"conversation_id": ObjectId(conversation_id)}).sort("timestamp", 1))
    for m in messages:
        m['_id'] = str(m['_id'])
        m['conversation_id'] = str(m['conversation_id'])
    return JsonResponse({"messages": messages}, status=200)
