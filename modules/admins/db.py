#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Admin Management Database Operations
Handles all database operations for admin management: roles, permissions, invites, requests, audit logs
"""

import sqlite3
import json
import secrets
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple


# Permission flags for granular control
PERMISSIONS = [
    'cash_view', 'cash_edit',
    'products_view', 'products_edit',
    'issues_view', 'issues_edit',
    'v2ray_view', 'v2ray_manage',
    'content_generate',
    'can_manage_admins',
    'can_work_shifts'  # Can work shifts and appear in shift replacement lists
]

# Default permissions for each role
ROLE_PERMISSIONS = {
    'owner': {perm: True for perm in PERMISSIONS},
    'manager': {
        'cash_view': True, 'cash_edit': True,
        'products_view': True, 'products_edit': True,
        'issues_view': True, 'issues_edit': True,
        'v2ray_view': True, 'v2ray_manage': False,
        'content_generate': True,
        'can_manage_admins': True,
        'can_work_shifts': True
    },
    'moderator': {
        'cash_view': True, 'cash_edit': False,
        'products_view': True, 'products_edit': True,
        'issues_view': True, 'issues_edit': True,
        'v2ray_view': False, 'v2ray_manage': False,
        'content_generate': True,
        'can_manage_admins': False,
        'can_work_shifts': True
    },
    'staff': {
        'cash_view': False, 'cash_edit': False,
        'products_view': True, 'products_edit': False,
        'issues_view': True, 'issues_edit': False,
        'v2ray_view': False, 'v2ray_manage': False,
        'content_generate': False,
        'can_manage_admins': False,
        'can_work_shifts': False  # Staff can work shifts only if they have full_name
    }
}


class AdminDB:
    """Database operations for admin management"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    # ===== Admin CRUD Operations =====
    
    def add_admin(self, user_id: int, username: str = None, full_name: str = None, 
                  role: str = 'staff', added_by: int = 0, active: int = 1) -> bool:
        """Add or update admin"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # Check if admin exists
            cursor.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
            exists = cursor.fetchone() is not None
            
            if exists:
                # Update existing admin
                cursor.execute('''
                    UPDATE admins 
                    SET username = ?, full_name = ?, role = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                ''', (username, full_name, role, active, user_id))
            else:
                # Insert new admin
                cursor.execute('''
                    INSERT INTO admins 
                    (user_id, username, full_name, role, added_by, is_active, 
                     can_teach, can_import, can_manage_admins, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 1, 1, 0, CURRENT_TIMESTAMP)
                ''', (user_id, username, full_name, role, added_by, active))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error adding admin: {e}")
            return False
    
    def get_admin(self, user_id: int) -> Optional[Dict]:
        """Get admin by user_id"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, username, full_name, role, permissions, is_active as active, notes, 
                       added_by, created_at, updated_at
                FROM admins 
                WHERE user_id = ?
            ''', (user_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'user_id': row[0],
                    'username': row[1],
                    'full_name': row[2],
                    'role': row[3],
                    'permissions': json.loads(row[4]) if row[4] else None,
                    'active': row[5],
                    'notes': row[6],
                    'added_by': row[7],
                    'created_at': row[8],
                    'updated_at': row[9]
                }
            return None
        except Exception as e:
            print(f"Error getting admin: {e}")
            return None
    
    def get_admin_by_username(self, username: str) -> Optional[Dict]:
        """Get admin by username (without @)"""
        try:
            # Remove @ if present
            username = username.lstrip('@')
            
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, username, full_name, role, permissions, is_active as active, notes, 
                       added_by, created_at, updated_at
                FROM admins 
                WHERE username = ?
            ''', (username,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'user_id': row[0],
                    'username': row[1],
                    'full_name': row[2],
                    'role': row[3],
                    'permissions': json.loads(row[4]) if row[4] else None,
                    'active': row[5],
                    'notes': row[6],
                    'added_by': row[7],
                    'created_at': row[8],
                    'updated_at': row[9]
                }
            return None
        except Exception as e:
            print(f"Error getting admin by username: {e}")
            return None
    
    def list_admins(self, role: str = None, active: int = None, 
                    page: int = 1, per_page: int = 20) -> Tuple[List[Dict], int]:
        """List admins with filters and pagination"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # Build query
            where_clauses = []
            params = []
            
            if role:
                where_clauses.append('role = ?')
                params.append(role)
            
            if active is not None:
                where_clauses.append('is_active = ?')
                params.append(active)
            
            where_sql = ' AND '.join(where_clauses) if where_clauses else '1=1'
            
            # Get total count
            cursor.execute(f'SELECT COUNT(*) FROM admins WHERE {where_sql}', params)
            total = cursor.fetchone()[0]
            
            # Get paginated results
            offset = (page - 1) * per_page
            cursor.execute(f'''
                SELECT user_id, username, full_name, role, permissions, is_active as active, notes, 
                       added_by, created_at, updated_at
                FROM admins 
                WHERE {where_sql}
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            ''', params + [per_page, offset])
            
            rows = cursor.fetchall()
            conn.close()
            
            admins = []
            for row in rows:
                admins.append({
                    'user_id': row[0],
                    'username': row[1],
                    'full_name': row[2],
                    'role': row[3],
                    'permissions': json.loads(row[4]) if row[4] else None,
                    'active': row[5],
                    'notes': row[6],
                    'added_by': row[7],
                    'created_at': row[8],
                    'updated_at': row[9]
                })
            
            return admins, total
        except Exception as e:
            print(f"Error listing admins: {e}")
            return [], 0
    
    def get_all_admins(self, active_only: bool = True) -> List[Dict]:
        """Get all admins (convenience method)"""
        admins, _ = self.list_admins(active=1 if active_only else None, page=1, per_page=1000)
        return admins
    
    def search_admins(self, query: str, page: int = 1, per_page: int = 20) -> Tuple[List[Dict], int]:
        """Search admins by username, full_name, or user_id"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # Try to parse as user_id
            try:
                user_id_query = int(query)
                user_id_condition = 'OR user_id = ?'
                params_search = [f'%{query}%', f'%{query}%', user_id_query]
            except ValueError:
                user_id_condition = ''
                params_search = [f'%{query}%', f'%{query}%']
            
            # Get total count
            cursor.execute(f'''
                SELECT COUNT(*) FROM admins 
                WHERE username LIKE ? OR full_name LIKE ? {user_id_condition}
            ''', params_search)
            total = cursor.fetchone()[0]
            
            # Get paginated results
            offset = (page - 1) * per_page
            cursor.execute(f'''
                SELECT user_id, username, full_name, role, permissions, is_active as active, notes, 
                       added_by, created_at, updated_at
                FROM admins 
                WHERE username LIKE ? OR full_name LIKE ? {user_id_condition}
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            ''', params_search + [per_page, offset])
            
            rows = cursor.fetchall()
            conn.close()
            
            admins = []
            for row in rows:
                admins.append({
                    'user_id': row[0],
                    'username': row[1],
                    'full_name': row[2],
                    'role': row[3],
                    'permissions': json.loads(row[4]) if row[4] else None,
                    'active': row[5],
                    'notes': row[6],
                    'added_by': row[7],
                    'created_at': row[8],
                    'updated_at': row[9]
                })
            
            return admins, total
        except Exception as e:
            print(f"Error searching admins: {e}")
            return [], 0
    
    def update_admin_cache(self, user_id: int, username: str = None, full_name: str = None) -> bool:
        """Update cached username and full_name for an admin"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            updates = []
            params = []
            
            if username is not None:
                updates.append('username = ?')
                params.append(username.lstrip('@') if username else None)
            
            if full_name is not None:
                updates.append('full_name = ?')
                params.append(full_name)
            
            if updates:
                updates.append('updated_at = CURRENT_TIMESTAMP')
                params.append(user_id)
                
                cursor.execute(f'''
                    UPDATE admins 
                    SET {', '.join(updates)}
                    WHERE user_id = ?
                ''', params)
                
                conn.commit()
            
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating admin cache: {e}")
            return False
    
    def set_role(self, user_id: int, role: str) -> bool:
        """Set admin role"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE admins 
                SET role = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (role, user_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error setting role: {e}")
            return False
    
    def set_permissions(self, user_id: int, permissions: Dict[str, bool]) -> bool:
        """Set custom permissions (overrides role defaults)"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE admins 
                SET permissions = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (json.dumps(permissions), user_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error setting permissions: {e}")
            return False
    
    def reset_permissions(self, user_id: int) -> bool:
        """Reset permissions to role defaults (set to NULL)"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE admins 
                SET permissions = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error resetting permissions: {e}")
            return False
    
    def set_active(self, user_id: int, active: int) -> bool:
        """Activate or deactivate admin"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE admins 
                SET is_active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (active, user_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error setting active status: {e}")
            return False
    
    def set_notes(self, user_id: int, notes: str) -> bool:
        """Set admin notes"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE admins 
                SET notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (notes, user_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error setting notes: {e}")
            return False
    
    def remove_admin(self, user_id: int) -> bool:
        """Remove admin from database"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error removing admin: {e}")
            return False
    
    def get_permissions(self, user_id: int) -> Dict[str, bool]:
        """Get effective permissions for admin (custom or role-based)"""
        admin = self.get_admin(user_id)
        if not admin:
            return {}
        
        # If custom permissions are set, use them
        if admin['permissions']:
            return admin['permissions']
        
        # Otherwise, use role defaults
        role = admin.get('role', 'staff')
        return ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS['staff'])
    
    def has_permission(self, user_id: int, permission: str) -> bool:
        """Check if admin has a specific permission"""
        permissions = self.get_permissions(user_id)
        return permissions.get(permission, False)
    
    def is_active(self, user_id: int) -> bool:
        """Check if admin is active"""
        admin = self.get_admin(user_id)
        return admin and admin['active'] == 1
    
    # ===== Invite Operations =====
    
    def create_invite(self, created_by: int, target_username: str = None, 
                      role_default: str = 'staff', expires_hours: int = 24) -> Optional[str]:
        """Create an invite link token"""
        try:
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(hours=expires_hours) if expires_hours else None
            
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO admin_invites 
                (token, created_by, target_username, role_default, expires_at, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
            ''', (token, created_by, target_username, role_default, expires_at))
            conn.commit()
            conn.close()
            
            return token
        except Exception as e:
            print(f"Error creating invite: {e}")
            return None
    
    def get_invite(self, token: str) -> Optional[Dict]:
        """Get invite by token"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, token, created_by, target_username, role_default, 
                       expires_at, status, created_at
                FROM admin_invites 
                WHERE token = ?
            ''', (token,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'id': row[0],
                    'token': row[1],
                    'created_by': row[2],
                    'target_username': row[3],
                    'role_default': row[4],
                    'expires_at': row[5],
                    'status': row[6],
                    'created_at': row[7]
                }
            return None
        except Exception as e:
            print(f"Error getting invite: {e}")
            return None
    
    def list_invites(self, status: str = None, page: int = 1, per_page: int = 20) -> Tuple[List[Dict], int]:
        """List invites with optional status filter"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            where_sql = 'WHERE status = ?' if status else 'WHERE 1=1'
            params = [status] if status else []
            
            # Get total count
            cursor.execute(f'SELECT COUNT(*) FROM admin_invites {where_sql}', params)
            total = cursor.fetchone()[0]
            
            # Get paginated results
            offset = (page - 1) * per_page
            cursor.execute(f'''
                SELECT id, token, created_by, target_username, role_default, 
                       expires_at, status, created_at
                FROM admin_invites 
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', params + [per_page, offset])
            
            rows = cursor.fetchall()
            conn.close()
            
            invites = []
            for row in rows:
                invites.append({
                    'id': row[0],
                    'token': row[1],
                    'created_by': row[2],
                    'target_username': row[3],
                    'role_default': row[4],
                    'expires_at': row[5],
                    'status': row[6],
                    'created_at': row[7]
                })
            
            return invites, total
        except Exception as e:
            print(f"Error listing invites: {e}")
            return [], 0
    
    def update_invite_status(self, token: str, status: str) -> bool:
        """Update invite status"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE admin_invites 
                SET status = ?
                WHERE token = ?
            ''', (status, token))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating invite status: {e}")
            return False
    
    def revoke_invite(self, invite_id: int) -> bool:
        """Revoke an invite"""
        return self.update_invite_status_by_id(invite_id, 'revoked')
    
    def update_invite_status_by_id(self, invite_id: int, status: str) -> bool:
        """Update invite status by ID"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE admin_invites 
                SET status = ?
                WHERE id = ?
            ''', (status, invite_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating invite status: {e}")
            return False
    
    # ===== Request Operations =====
    
    def create_request(self, user_id: int, username: str = None, 
                       full_name: str = None, message: str = None) -> bool:
        """Create an admin request"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # Check if request already exists
            cursor.execute('''
                SELECT id FROM admin_requests 
                WHERE user_id = ? AND status = 'pending'
            ''', (user_id,))
            
            if cursor.fetchone():
                conn.close()
                return False  # Request already exists
            
            cursor.execute('''
                INSERT INTO admin_requests 
                (user_id, username, full_name, message, status)
                VALUES (?, ?, ?, ?, 'pending')
            ''', (user_id, username, full_name, message))
            conn.commit()
            conn.close()
            
            return True
        except Exception as e:
            print(f"Error creating request: {e}")
            return False
    
    def list_requests(self, status: str = 'pending', page: int = 1, per_page: int = 20) -> Tuple[List[Dict], int]:
        """List admin requests"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            where_sql = 'WHERE status = ?' if status else 'WHERE 1=1'
            params = [status] if status else []
            
            # Get total count
            cursor.execute(f'SELECT COUNT(*) FROM admin_requests {where_sql}', params)
            total = cursor.fetchone()[0]
            
            # Get paginated results
            offset = (page - 1) * per_page
            cursor.execute(f'''
                SELECT id, user_id, username, full_name, message, status, 
                       reviewed_by, reviewed_at, created_at
                FROM admin_requests 
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', params + [per_page, offset])
            
            rows = cursor.fetchall()
            conn.close()
            
            requests = []
            for row in rows:
                requests.append({
                    'id': row[0],
                    'user_id': row[1],
                    'username': row[2],
                    'full_name': row[3],
                    'message': row[4],
                    'status': row[5],
                    'reviewed_by': row[6],
                    'reviewed_at': row[7],
                    'created_at': row[8]
                })
            
            return requests, total
        except Exception as e:
            print(f"Error listing requests: {e}")
            return [], 0
    
    def approve_request(self, request_id: int, reviewed_by: int, role: str = 'staff') -> Optional[int]:
        """Approve a request and return user_id"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # Get request details
            cursor.execute('''
                SELECT user_id, username, full_name FROM admin_requests 
                WHERE id = ? AND status = 'pending'
            ''', (request_id,))
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return None
            
            user_id, username, full_name = row
            
            # Update request status
            cursor.execute('''
                UPDATE admin_requests 
                SET status = 'approved', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (reviewed_by, request_id))
            
            conn.commit()
            conn.close()
            
            # Add admin
            self.add_admin(user_id, username, full_name, role, reviewed_by, active=1)
            
            return user_id
        except Exception as e:
            print(f"Error approving request: {e}")
            return None
    
    def reject_request(self, request_id: int, reviewed_by: int) -> bool:
        """Reject a request"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE admin_requests 
                SET status = 'rejected', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (reviewed_by, request_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error rejecting request: {e}")
            return False
    
    # ===== Audit Log Operations =====
    
    def log_action(self, actor_user_id: int, action: str, target_user_id: int = None, 
                   details: Dict = None) -> bool:
        """Log an admin action"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO admin_audit_logs 
                (actor_user_id, action, target_user_id, details)
                VALUES (?, ?, ?, ?)
            ''', (actor_user_id, action, target_user_id, json.dumps(details) if details else None))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error logging action: {e}")
            return False
    
    def get_audit_logs(self, user_id: int = None, action: str = None, 
                       page: int = 1, per_page: int = 50) -> Tuple[List[Dict], int]:
        """Get audit logs with filters"""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            where_clauses = []
            params = []
            
            if user_id:
                where_clauses.append('(actor_user_id = ? OR target_user_id = ?)')
                params.extend([user_id, user_id])
            
            if action:
                where_clauses.append('action = ?')
                params.append(action)
            
            where_sql = ' AND '.join(where_clauses) if where_clauses else '1=1'
            
            # Get total count
            cursor.execute(f'SELECT COUNT(*) FROM admin_audit_logs WHERE {where_sql}', params)
            total = cursor.fetchone()[0]
            
            # Get paginated results
            offset = (page - 1) * per_page
            cursor.execute(f'''
                SELECT id, actor_user_id, action, target_user_id, details, created_at
                FROM admin_audit_logs 
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', params + [per_page, offset])
            
            rows = cursor.fetchall()
            conn.close()
            
            logs = []
            for row in rows:
                logs.append({
                    'id': row[0],
                    'actor_user_id': row[1],
                    'action': row[2],
                    'target_user_id': row[3],
                    'details': json.loads(row[4]) if row[4] else None,
                    'created_at': row[5]
                })
            
            return logs, total
        except Exception as e:
            print(f"Error getting audit logs: {e}")
            return [], 0
    
    # ===== Salary Management Methods =====
    
    def set_employment_type(self, user_id: int, employment_type: str) -> bool:
        """
        Set employment type: 'self_employed', 'staff', 'gpc'
        
        Args:
            user_id: Admin user ID
            employment_type: Employment type
        
        Returns:
            True if successful, False otherwise
        """
        if employment_type not in ['self_employed', 'staff', 'gpc']:
            print(f"Invalid employment type: {employment_type}")
            return False
        
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE admins 
                SET employment_type = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (employment_type, user_id))
            
            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()
            
            if rows_affected > 0:
                print(f"✅ Set employment type to {employment_type} for admin {user_id}")
                return True
            else:
                print(f"❌ Admin {user_id} not found")
                return False
                
        except Exception as e:
            print(f"Error setting employment type: {e}")
            return False
    
    def set_salary_per_shift(self, user_id: int, amount: float) -> bool:
        """
        Set fixed salary per shift
        
        Args:
            user_id: Admin user ID
            amount: Salary amount per shift
        
        Returns:
            True if successful, False otherwise
        """
        if amount < 0:
            print(f"Salary amount cannot be negative: {amount}")
            return False
        
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE admins 
                SET salary_per_shift = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (amount, user_id))
            
            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()
            
            if rows_affected > 0:
                print(f"✅ Set salary per shift to {amount} for admin {user_id}")
                return True
            else:
                print(f"❌ Admin {user_id} not found")
                return False
                
        except Exception as e:
            print(f"Error setting salary per shift: {e}")
            return False
    
    def set_custom_tax_rate(self, user_id: int, rate: float) -> bool:
        """
        Set custom tax rate (overrides default)
        
        Args:
            user_id: Admin user ID
            rate: Tax rate percentage (0 = use default)
        
        Returns:
            True if successful, False otherwise
        """
        if rate < 0 or rate > 100:
            print(f"Tax rate must be between 0 and 100: {rate}")
            return False
        
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE admins 
                SET tax_rate = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (rate, user_id))
            
            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()
            
            if rows_affected > 0:
                print(f"✅ Set custom tax rate to {rate}% for admin {user_id}")
                return True
            else:
                print(f"❌ Admin {user_id} not found")
                return False
                
        except Exception as e:
            print(f"Error setting custom tax rate: {e}")
            return False
    
    def get_salary_settings(self, user_id: int) -> Dict:
        """
        Get employment_type, salary_per_shift, tax_rate
        
        Args:
            user_id: Admin user ID
        
        Returns:
            Dictionary with salary settings
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT employment_type, salary_per_shift, tax_rate
                FROM admins 
                WHERE user_id = ?
            ''', (user_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'employment_type': row[0] or 'self_employed',
                    'salary_per_shift': row[1] or 0.0,
                    'tax_rate': row[2] or 0.0
                }
            else:
                print(f"Admin {user_id} not found")
                return {
                    'employment_type': 'self_employed',
                    'salary_per_shift': 0.0,
                    'tax_rate': 0.0
                }
                
        except Exception as e:
            print(f"Error getting salary settings: {e}")
            return {
                'employment_type': 'self_employed',
                'salary_per_shift': 0.0,
                'tax_rate': 0.0
            }
