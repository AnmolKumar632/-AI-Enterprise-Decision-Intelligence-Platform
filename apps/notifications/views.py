import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from bson import ObjectId
from utilities.db_connection import get_db
from utilities.decorators import login_required_api
from utilities.custom_logger import get_logger

logger = get_logger('notifications_views')
db = get_db()

@csrf_exempt
@login_required_api
def api_list_notifications(request):
    """Retrieve in-app notifications for the logged-in user."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    user_id = request.user_data['id']
    
    # Retrieve latest 20 notifications
    notifications = list(db.notifications.find({"user_id": ObjectId(user_id)}).sort("created_at", -1).limit(20))
    for n in notifications:
        n['_id'] = str(n['_id'])
        n['user_id'] = str(n['user_id'])
        
    return JsonResponse({"notifications": notifications}, status=200)

@csrf_exempt
@login_required_api
def api_mark_as_read(request, notification_id):
    """Mark a specific notification as read."""
    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)
        
    try:
        db.notifications.update_one(
            {"_id": ObjectId(notification_id)},
            {"$set": {"is_read": True}}
        )
        return JsonResponse({"message": "Notification marked as read."}, status=200)
    except Exception as e:
        logger.error(f"Failed to update notification {notification_id}: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@login_required_api
def api_delete_notification(request, notification_id):
    """Delete a notification for the logged-in user."""
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed. Use POST."}, status=405)

    if db is None:
        return JsonResponse({"error": "Database offline."}, status=500)

    result = db.notifications.delete_one({
        "_id": ObjectId(notification_id),
        "user_id": ObjectId(request.user_data['id'])
    })
    if result.deleted_count == 0:
        return JsonResponse({"error": "Notification not found."}, status=404)

    return JsonResponse({"message": "Notification deleted successfully."}, status=200)
