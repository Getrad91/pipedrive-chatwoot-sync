-- Pipedrive to Chatwoot Sync Database Schema
-- This creates the middleware database for syncing data

CREATE DATABASE IF NOT EXISTS pipedrive_chatwoot_sync;
USE pipedrive_chatwoot_sync;

-- Organizations table (matching existing schema)
CREATE TABLE IF NOT EXISTS organizations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pipedrive_org_id INT UNIQUE NOT NULL,
    name VARCHAR(255),
    phone VARCHAR(50),
    support_link VARCHAR(255),
    city VARCHAR(100),
    country VARCHAR(100),
    email VARCHAR(255),
    status VARCHAR(50),
    data JSON,
    notes TEXT,
    deal_title VARCHAR(255),
    owner_name VARCHAR(255),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    synced_to_chatwoot TINYINT(1) DEFAULT 0,
    chatwoot_contact_id INT NULL,
    INDEX idx_pipedrive_org_id (pipedrive_org_id),
    INDEX idx_synced_status (synced_to_chatwoot),
    INDEX idx_chatwoot_id (chatwoot_contact_id)
);

-- Persons table (matching existing schema)
CREATE TABLE IF NOT EXISTS persons (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pipedrive_person_id INT UNIQUE NOT NULL,
    name VARCHAR(255),
    phone VARCHAR(100),
    email VARCHAR(255),
    org_id INT,
    status VARCHAR(50),
    data JSON,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    synced_to_chatwoot TINYINT(1) DEFAULT 0,
    chatwoot_contact_id INT NULL,
    INDEX idx_pipedrive_person_id (pipedrive_person_id),
    INDEX idx_org_id (org_id),
    INDEX idx_synced_status (synced_to_chatwoot),
    INDEX idx_chatwoot_id (chatwoot_contact_id)
);

-- Contacts table (matching existing schema)
CREATE TABLE IF NOT EXISTS contacts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pipedrive_person_id INT UNIQUE NOT NULL,
    org_id INT,
    name VARCHAR(255),
    phone VARCHAR(50),
    email VARCHAR(255),
    role VARCHAR(100),
    status VARCHAR(50),
    data JSON,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    synced_to_chatwoot TINYINT(1) DEFAULT 0,
    chatwoot_contact_id INT NULL,
    INDEX idx_pipedrive_person_id (pipedrive_person_id),
    INDEX idx_org_id (org_id),
    INDEX idx_synced_status (synced_to_chatwoot),
    INDEX idx_chatwoot_id (chatwoot_contact_id)
);

-- Sync log table for tracking operations
CREATE TABLE IF NOT EXISTS sync_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sync_type ENUM('organizations', 'persons', 'contacts', 'full_sync') NOT NULL,
    status ENUM('success', 'error', 'partial') NOT NULL,
    records_processed INT DEFAULT 0,
    records_synced INT DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    INDEX idx_sync_type (sync_type),
    INDEX idx_status (status),
    INDEX idx_started_at (started_at)
);

CREATE TABLE IF NOT EXISTS sync_metadata (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sync_type VARCHAR(50) NOT NULL UNIQUE,
    last_sync_timestamp TIMESTAMP NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Create dedicated user for the sync application
CREATE USER IF NOT EXISTS 'sync_user'@'%' IDENTIFIED BY 'sync_password_2024';
GRANT SELECT, INSERT, UPDATE, DELETE ON pipedrive_chatwoot_sync.* TO 'sync_user'@'%';
FLUSH PRIVILEGES;

-- Insert initial sync log entry
INSERT INTO sync_log (sync_type, status, records_processed, records_synced, completed_at) 
VALUES ('full_sync', 'success', 0, 0, NOW());
