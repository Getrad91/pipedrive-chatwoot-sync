import os
import json
import time
import requests
from datetime import datetime
from typing import Dict, Any, Optional, Union

class GoogleChatNotifier:
    def __init__(self):
        self.webhook_url = os.getenv('SUPPORT_GOOGLE_CHAT')
        if not self.webhook_url:
            raise ValueError("SUPPORT_GOOGLE_CHAT environment variable not set")
    
    def send_alert(self, 
                   script_name: str,
                   error_type: str, 
                   message: str,
                   details: Dict[str, Any] = None,
                   alert_level: str = "ERROR") -> bool:
        """
        Send structured alert to Google Chat
        
        Args:
            script_name: Name of the script (sync/cleanup/monitor)
            error_type: Type of error (API failure, mismatch, auth issue, etc.)
            message: Main error message
            details: Additional details like affected contacts/labels
            alert_level: ERROR, WARNING, or INFO
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        alert_data = {
            "timestamp": timestamp,
            "script": script_name,
            "level": alert_level,
            "error_type": error_type,
            "message": message
        }
        
        if details:
            alert_data.update(details)
        
        emoji = "🚨" if alert_level == "ERROR" else "⚠️" if alert_level == "WARNING" else "ℹ️"
        
        card_message = {
            "text": f"{emoji} Chatwoot Sync Alert - {error_type}",
            "cards": [{
                "header": {
                    "title": f"Pipedrive-Chatwoot Sync Alert",
                    "subtitle": f"{script_name} - {error_type}",
                    "imageUrl": "https://developers.google.com/chat/images/quickstart-app-avatar.png"
                },
                "sections": [{
                    "widgets": [
                        {
                            "keyValue": {
                                "topLabel": "Timestamp",
                                "content": timestamp
                            }
                        },
                        {
                            "keyValue": {
                                "topLabel": "Script",
                                "content": script_name
                            }
                        },
                        {
                            "keyValue": {
                                "topLabel": "Error Type",
                                "content": error_type
                            }
                        },
                        {
                            "keyValue": {
                                "topLabel": "Alert Level",
                                "content": alert_level
                            }
                        },
                        {
                            "textParagraph": {
                                "text": f"<b>Message:</b><br>{message}"
                            }
                        }
                    ]
                }]
            }]
        }
        
        if details:
            details_widgets = []
            for key, value in details.items():
                details_widgets.append({
                    "keyValue": {
                        "topLabel": key.replace('_', ' ').title(),
                        "content": str(value)
                    }
                })
            
            card_message["cards"][0]["sections"].append({
                "header": "Details",
                "widgets": details_widgets
            })
        
        return self._send_with_retry(card_message)
    
    def _send_with_retry(self, message: Dict[str, Any], max_retries: int = 3) -> bool:
        """Send message with exponential backoff retry logic"""
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.webhook_url,
                    json=message,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )
                
                if response.status_code == 200:
                    return True
                elif response.status_code == 429:
                    wait_time = (2 ** attempt) * 5
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Google Chat notification failed: {response.status_code} - {response.text}")
                    
            except requests.exceptions.RequestException as e:
                print(f"Error sending Google Chat notification (attempt {attempt + 1}): {e}")
                
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 2
                    time.sleep(wait_time)
        
        return False
    
    def test_connection(self) -> bool:
        """Test Google Chat webhook connection"""
        test_message = {
            "text": "🧪 Test notification from Pipedrive-Chatwoot Sync monitoring system",
            "cards": [{
                "header": {
                    "title": "Connection Test",
                    "subtitle": "Monitoring system is working correctly"
                },
                "sections": [{
                    "widgets": [{
                        "textParagraph": {
                            "text": "This is a test message to verify Google Chat integration is working properly."
                        }
                    }]
                }]
            }]
        }
        
        return self._send_with_retry(test_message)

def send_sync_alert(script_name: str, error_type: str, message: str, 
                   details: Optional[Dict[str, Any]] = None, alert_level: str = "ERROR") -> bool:
    """Convenience function to send sync alerts"""
    try:
        notifier = GoogleChatNotifier()
        return notifier.send_alert(script_name, error_type, message, details, alert_level)
    except Exception as e:
        print(f"Failed to send alert: {e}")
        return False

def test_notifications() -> bool:
    """Test notification system"""
    try:
        notifier = GoogleChatNotifier()
        return notifier.test_connection()
    except Exception as e:
        print(f"Failed to test notifications: {e}")
        return False
