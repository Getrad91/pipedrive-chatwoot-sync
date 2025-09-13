#!/usr/bin/env python3
"""
Test script for monitoring and notification system
"""

import os
import sys

def test_notifications():
    """Test Google Chat notifications"""
    print("🧪 Testing Google Chat notifications...")
    
    try:
        from app.notifications import test_notifications
        result = test_notifications()
        if result:
            print("✅ Google Chat test successful!")
            return True
        else:
            print("❌ Google Chat test failed!")
            return False
    except Exception as e:
        print(f"❌ Notification test error: {e}")
        return False

def test_monitor_validation():
    """Test monitor validation with invalid credentials"""
    print("🧪 Testing monitor validation...")
    
    os.environ['PIPEDRIVE_API_KEY'] = 'invalid_test_key'
    os.environ['CHATWOOT_API_KEY'] = 'invalid_test_key'
    os.environ['MYSQL_PASSWORD'] = 'test_password'
    
    try:
        from app.monitor import SyncMonitor
        monitor = SyncMonitor()
        
        pipedrive_healthy, pipedrive_data = monitor.check_pipedrive_api()
        print(f"Pipedrive API test (should fail): healthy={pipedrive_healthy}")
        print(f"  Error data: {pipedrive_data}")
        
        chatwoot_healthy, chatwoot_data = monitor.check_chatwoot_api()
        print(f"Chatwoot API test (should fail): healthy={chatwoot_healthy}")
        print(f"  Error data: {chatwoot_data}")
        
        if not pipedrive_healthy and not chatwoot_healthy:
            print("✅ Monitor validation tests completed successfully!")
            return True
        else:
            print("❌ Monitor validation failed - should have detected invalid credentials")
            return False
            
    except Exception as e:
        print(f"❌ Monitor test error: {e}")
        return False

def test_module_imports():
    """Test that all modules can be imported"""
    print("🧪 Testing module imports...")
    
    modules = [
        'app.notifications',
        'app.logging_config', 
        'app.monitor'
    ]
    
    success = True
    for module in modules:
        try:
            __import__(module)
            print(f"✅ {module} imported successfully")
        except Exception as e:
            print(f"❌ Failed to import {module}: {e}")
            success = False
    
    return success

def main():
    """Run all tests"""
    print("🚀 Starting monitoring system tests...")
    print("=" * 50)
    
    if not test_module_imports():
        print("❌ Module import tests failed!")
        return False
    
    if not test_monitor_validation():
        print("❌ Monitor validation tests failed!")
        return False
    
    if os.getenv('SUPPORT_GOOGLE_CHAT'):
        if not test_notifications():
            print("❌ Notification tests failed!")
            return False
    else:
        print("⚠️ Skipping notification test - SUPPORT_GOOGLE_CHAT not set")
    
    print("=" * 50)
    print("🎉 All monitoring system tests passed!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
