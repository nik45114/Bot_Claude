-- Admin Management Module Database Schema
-- Roles, permissions, invites, requests, and audit logging

-- Create admins table if it doesn't exist (base schema)
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    added_by INTEGER,
    can_teach BOOLEAN DEFAULT 1,
    can_import BOOLEAN DEFAULT 0,
    can_manage_admins BOOLEAN DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Extend admins table with new columns
-- Note: We use a safe approach by checking if columns exist via a try-catch in Python
-- For now, we'll just try to add them and ignore errors if they exist

-- Add role column if it doesn't exist
-- Role: owner, manager, moderator, staff
-- SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we handle this in migration runner
ALTER TABLE admins ADD COLUMN role TEXT DEFAULT 'staff';

-- Add permissions column (JSON string of permission flags)
-- If NULL, permissions are derived from role
ALTER TABLE admins ADD COLUMN permissions TEXT NULL;

-- Add active status (1 = active, 0 = disabled)
ALTER TABLE admins ADD COLUMN active INTEGER DEFAULT 1;

-- Add notes field for admin-specific notes
ALTER TABLE admins ADD COLUMN notes TEXT NULL;

-- Add updated_at timestamp
ALTER TABLE admins ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Admin invites table
CREATE TABLE IF NOT EXISTS admin_invites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT UNIQUE NOT NULL,
    created_by INTEGER NOT NULL,
    target_username TEXT NULL,
    role_default TEXT DEFAULT 'staff',
    expires_at TIMESTAMP NULL,
    status TEXT DEFAULT 'pending', -- pending/accepted/expired/revoked
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES admins(user_id)
);

-- Admin requests table
CREATE TABLE IF NOT EXISTS admin_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT NULL,
    full_name TEXT NULL,
    message TEXT NULL,
    status TEXT DEFAULT 'pending', -- pending/approved/rejected
    reviewed_by INTEGER NULL,
    reviewed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reviewed_by) REFERENCES admins(user_id)
);

-- Admin audit logs table
CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER NOT NULL,
    action TEXT NOT NULL, -- add, remove, set_role, set_permissions, activate, deactivate, invite_create, invite_revoke, request_approve, request_reject
    target_user_id INTEGER NULL,
    details TEXT NULL, -- JSON string with additional details
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (actor_user_id) REFERENCES admins(user_id),
    FOREIGN KEY (target_user_id) REFERENCES admins(user_id)
);

-- Indexes for performance

-- Admin search and filtering
CREATE INDEX IF NOT EXISTS idx_admins_username ON admins(username);
CREATE INDEX IF NOT EXISTS idx_admins_role ON admins(role);
CREATE INDEX IF NOT EXISTS idx_admins_active ON admins(active);
CREATE INDEX IF NOT EXISTS idx_admins_updated_at ON admins(updated_at DESC);

-- Invites
CREATE INDEX IF NOT EXISTS idx_admin_invites_token ON admin_invites(token);
CREATE INDEX IF NOT EXISTS idx_admin_invites_status ON admin_invites(status);
CREATE INDEX IF NOT EXISTS idx_admin_invites_created_at ON admin_invites(created_at DESC);

-- Requests
CREATE INDEX IF NOT EXISTS idx_admin_requests_user_id ON admin_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_requests_status ON admin_requests(status);
CREATE INDEX IF NOT EXISTS idx_admin_requests_created_at ON admin_requests(created_at DESC);

-- Audit logs
CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_actor ON admin_audit_logs(actor_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_target ON admin_audit_logs(target_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_created_at ON admin_audit_logs(created_at DESC);
