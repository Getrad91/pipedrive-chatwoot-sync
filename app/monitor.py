import os
import sys
import time
import json
import requests
import pymysql
import pymysql.cursors
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from .logging_config import get_monitor_logger, log_with_extra
from .notifications import send_sync_alert

class SyncMonitor:
    def __init__(self):
        self.logger = get_monitor_logger()
        self.pipedrive_api_key = os.getenv('PIPEDRIVE_API_KEY')
        self.chatwoot_api_key = os.getenv('CHATWOOT_API_KEY')
        self.pipedrive_base_url = os.getenv('PIPEDRIVE_BASE_URL', 'https://api.pipedrive.com/v1')
        self.chatwoot_base_url = os.getenv('CHATWOOT_BASE_URL', 'https://support.liveport.com.au/api/v1/accounts/2')
        
        self.error_threshold = int(os.getenv('ALERT_ERROR_THRESHOLD', '10'))
        self.max_sync_age_hours = int(os.getenv('MAX_SYNC_AGE_HOURS', '2'))
        
        # Database configuration
        self.db_config = {
            'host': os.getenv('MYSQL_HOST', 'mysql'),
            'port': int(os.getenv('MYSQL_PORT', '3306')),
            'user': os.getenv('MYSQL_USER', 'sync_user'),
            'password': os.getenv('MYSQL_PASSWORD'),
            'database': os.getenv('MYSQL_DATABASE', 'pipedrive_chatwoot_sync'),
            'charset': 'utf8mb4'
        }
        
        if not all([self.pipedrive_api_key, self.chatwoot_api_key, self.db_config['password']]):
            raise ValueError("Missing required environment variables")
    
    def get_db_connection(self):
        """Get database connection"""
        return pymysql.connect(**self.db_config)
    
    def check_pipedrive_api(self) -> Tuple[bool, Dict[str, Any]]:
        """Check Pipedrive API connectivity and get Customer organizations count"""
        try:
            url = f"{self.pipedrive_base_url}/organizations"
            params = {
                'api_token': self.pipedrive_api_key,
                'limit': 1,
                'filter_id': 5  # Customer organizations
            }
            
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 401:
                return False, {'error': 'API authentication failed', 'status_code': 401}
            elif response.status_code != 200:
                return False, {'error': f'API request failed', 'status_code': response.status_code}
            
            data = response.json()
            if not data.get('success'):
                return False, {'error': 'API returned unsuccessful response', 'data': data}
            
            pagination = data.get('additional_data', {}).get('pagination', {})
            total_count = pagination.get('total_count', 0)
            
            return True, {
                'total_customer_orgs': total_count,
                'api_status': 'healthy'
            }
            
        except requests.exceptions.RequestException as e:
            return False, {'error': f'Network error: {str(e)}'}
        except Exception as e:
            return False, {'error': f'Unexpected error: {str(e)}'}
    
    def check_chatwoot_api(self) -> Tuple[bool, Dict[str, Any]]:
        """Check Chatwoot API connectivity and get contact count"""
        try:
            url = f"{self.chatwoot_base_url}/contacts"
            headers = {'Api-Access-Token': self.chatwoot_api_key}
            params = {'page': 1, 'per_page': 1}
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 401:
                return False, {'error': 'API authentication failed', 'status_code': 401}
            elif response.status_code != 200:
                return False, {'error': f'API request failed', 'status_code': response.status_code}
            
            data = response.json()
            
            meta = data.get('meta', {})
            total_count = meta.get('count', 0)
            
            return True, {
                'total_contacts': total_count,
                'api_status': 'healthy'
            }
            
        except requests.exceptions.RequestException as e:
            return False, {'error': f'Network error: {str(e)}'}
        except Exception as e:
            return False, {'error': f'Unexpected error: {str(e)}'}
    
    def check_database_sync_status(self) -> Tuple[bool, Dict[str, Any]]:
        """Check database for sync status and potential issues"""
        try:
            conn = self.get_db_connection()
            
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("SELECT COUNT(*) as unsynced_count FROM organizations WHERE synced_to_chatwoot = 0")
                unsynced_result = cursor.fetchone()
                unsynced_count = unsynced_result['unsynced_count'] if unsynced_result else 0
                
                cutoff_time = datetime.now() - timedelta(hours=self.max_sync_age_hours)
                cursor.execute(
                    "SELECT COUNT(*) as stale_count FROM organizations WHERE synced_to_chatwoot = 0 AND updated_at < %s",
                    (cutoff_time,)
                )
                stale_result = cursor.fetchone()
                stale_count = stale_result['stale_count'] if stale_result else 0
                
                cursor.execute(
                    "SELECT * FROM sync_log WHERE started_at >= %s ORDER BY started_at DESC LIMIT 10",
                    (datetime.now() - timedelta(hours=24),)
                )
                recent_syncs = cursor.fetchall()
                
                if recent_syncs:
                    error_syncs = [s for s in recent_syncs if s['status'] == 'error']
                    error_rate = (len(error_syncs) / len(recent_syncs)) * 100
                else:
                    error_rate = 0
                
                cursor.execute(
                    "SELECT COUNT(*) as consecutive_errors FROM sync_log WHERE started_at >= %s AND status = 'error'",
                    (datetime.now() - timedelta(hours=6),)
                )
                consecutive_errors_result = cursor.fetchone()
                consecutive_errors = consecutive_errors_result['consecutive_errors'] if consecutive_errors_result else 0
                
                conn.close()
                
                issues = []
                if stale_count > 0:
                    issues.append(f"{stale_count} organizations unsynced for over {self.max_sync_age_hours} hours")
                
                if error_rate > self.error_threshold:
                    issues.append(f"High error rate: {error_rate:.1f}% in last 24 hours")
                
                if consecutive_errors >= 3:
                    issues.append(f"{consecutive_errors} consecutive sync errors in last 6 hours")
                
                return len(issues) == 0, {
                    'unsynced_count': unsynced_count,
                    'stale_count': stale_count,
                    'error_rate': error_rate,
                    'consecutive_errors': consecutive_errors,
                    'recent_syncs_count': len(recent_syncs),
                    'issues': issues
                }
                
        except Exception as e:
            return False, {'error': f'Database check failed: {str(e)}'}
    
    def check_data_consistency(self) -> Tuple[bool, Dict[str, Any]]:
        """Check for data mismatches between Pipedrive and local database"""
        try:
            pipedrive_healthy, pipedrive_data = self.check_pipedrive_api()
            if not pipedrive_healthy:
                return False, {'error': 'Cannot check consistency - Pipedrive API unavailable'}
            
            conn = self.get_db_connection()
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("SELECT COUNT(*) as db_count FROM organizations")
                db_result = cursor.fetchone()
                db_count = db_result['db_count']
                
                cursor.execute("SELECT COUNT(*) as synced_count FROM organizations WHERE synced_to_chatwoot = 1")
                synced_result = cursor.fetchone()
                synced_count = synced_result['synced_count']
            
            conn.close()
            
            pipedrive_count = pipedrive_data.get('total_customer_orgs', 0)
            
            issues = []
            if abs(pipedrive_count - db_count) > max(10, pipedrive_count * 0.1):
                issues.append(f"Large discrepancy: Pipedrive has {pipedrive_count} Customer orgs, database has {db_count}")
            
            sync_rate = (synced_count / db_count * 100) if db_count > 0 else 0
            if sync_rate < 90 and db_count > 0:
                issues.append(f"Low sync rate: Only {sync_rate:.1f}% of database records synced to Chatwoot")
            
            return len(issues) == 0, {
                'pipedrive_count': pipedrive_count,
                'database_count': db_count,
                'synced_count': synced_count,
                'sync_rate': sync_rate,
                'issues': issues
            }
            
        except Exception as e:
            return False, {'error': f'Consistency check failed: {str(e)}'}
    
    def run_health_check(self) -> Dict[str, Any]:
        """Run comprehensive health check"""
        self.logger.info("Starting comprehensive health check")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy',
            'checks': {}
        }
        
        self.logger.info("Checking Pipedrive API connectivity")
        pipedrive_healthy, pipedrive_data = self.check_pipedrive_api()
        results['checks']['pipedrive_api'] = {
            'status': 'healthy' if pipedrive_healthy else 'unhealthy',
            'data': pipedrive_data
        }
        
        if not pipedrive_healthy:
            self.logger.error("Pipedrive API check failed", extra={'extra_data': pipedrive_data})
            send_sync_alert(
                'monitor',
                'API failure',
                f"Pipedrive API connectivity failed: {pipedrive_data.get('error', 'Unknown error')}",
                pipedrive_data,
                'ERROR'
            )
            results['overall_status'] = 'unhealthy'
        
        self.logger.info("Checking Chatwoot API connectivity")
        chatwoot_healthy, chatwoot_data = self.check_chatwoot_api()
        results['checks']['chatwoot_api'] = {
            'status': 'healthy' if chatwoot_healthy else 'unhealthy',
            'data': chatwoot_data
        }
        
        if not chatwoot_healthy:
            self.logger.error("Chatwoot API check failed", extra={'extra_data': chatwoot_data})
            send_sync_alert(
                'monitor',
                'API failure',
                f"Chatwoot API connectivity failed: {chatwoot_data.get('error', 'Unknown error')}",
                chatwoot_data,
                'ERROR'
            )
            results['overall_status'] = 'unhealthy'
        
        self.logger.info("Checking database sync status")
        db_healthy, db_data = self.check_database_sync_status()
        results['checks']['database_sync'] = {
            'status': 'healthy' if db_healthy else 'unhealthy',
            'data': db_data
        }
        
        if not db_healthy:
            self.logger.warning("Database sync issues detected", extra={'extra_data': db_data})
            if db_data.get('issues'):
                send_sync_alert(
                    'monitor',
                    'sync issues',
                    f"Database sync problems detected: {'; '.join(db_data['issues'])}",
                    db_data,
                    'WARNING'
                )
            results['overall_status'] = 'unhealthy'
        
        self.logger.info("Checking data consistency")
        consistency_healthy, consistency_data = self.check_data_consistency()
        results['checks']['data_consistency'] = {
            'status': 'healthy' if consistency_healthy else 'unhealthy',
            'data': consistency_data
        }
        
        if not consistency_healthy:
            self.logger.warning("Data consistency issues detected", extra={'extra_data': consistency_data})
            if consistency_data.get('issues'):
                send_sync_alert(
                    'monitor',
                    'data mismatch',
                    f"Data consistency problems detected: {'; '.join(consistency_data['issues'])}",
                    consistency_data,
                    'WARNING'
                )
            results['overall_status'] = 'unhealthy'
        
        self.logger.info(f"Health check completed - Overall status: {results['overall_status']}")
        log_with_extra(self.logger, 20, "Health check results", results)
        
        return results

def main():
    """Main monitoring function"""
    try:
        monitor = SyncMonitor()
        results = monitor.run_health_check()
        
        print(f"Health Check Results - {results['timestamp']}")
        print(f"Overall Status: {results['overall_status'].upper()}")
        print("\nCheck Details:")
        
        for check_name, check_data in results['checks'].items():
            status_emoji = "✅" if check_data['status'] == 'healthy' else "❌"
            print(f"  {status_emoji} {check_name.replace('_', ' ').title()}: {check_data['status']}")
            
            if check_data['status'] == 'unhealthy' and 'issues' in check_data['data']:
                for issue in check_data['data']['issues']:
                    print(f"    - {issue}")
        
        sys.exit(0 if results['overall_status'] == 'healthy' else 1)
        
    except Exception as e:
        print(f"Monitor failed with error: {e}")
        send_sync_alert(
            'monitor',
            'system error',
            f"Monitoring system failed: {str(e)}",
            {'error': str(e)},
            'ERROR'
        )
        sys.exit(1)

if __name__ == "__main__":
    main()
