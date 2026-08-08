# EduMi2 — Remote Windows PC Database (E: Drive) Setup Guide

This guide explains how to host your **PostgreSQL Database on your Windows PC (E: Drive)** while running the **EduMi2 Application Server on your Ubuntu Server**.

---

## 🏗 System Architecture Diagram

```
+------------------------------------+           +-------------------------------------+
|        UBUNTU WEB SERVER           |           |         YOUR WINDOWS PC             |
|                                    |           |                                     |
|  - Daphne ASGI Web App (8002-8007) |  network  |  - PostgreSQL 15 Database           |
|  - Camera Service (8008)           | --------> |  - Data Storage Path: E:\edumi_data |
|  - LiveKit SFU (7880)              |           |  - Windows Firewall: Open 5432      |
|  - Nginx Reverse Proxy (80/443)    |           |  - IP Address: [e.g. 192.168.1.100] |
+------------------------------------+           +-------------------------------------+
```

---

## 🚀 Step 1: Configure Windows PC PostgreSQL (E: Drive)

On your **Windows PC**:

1. Open PowerShell **as Administrator**.
2. Run the automated setup script:
   ```powershell
   Set-ExecutionPolicy Unrestricted -Scope Process -Force
   .\setup_windows_postgres_e_drive.ps1
   ```

### What this script does automatically:
- Creates the database data directory on **E:\edumi_postgres_data**.
- Updates `postgresql.conf` to set `listen_addresses = '*'`.
- Updates `pg_hba.conf` to allow remote host connections (`0.0.0.0/0`).
- Adds an **Inbound Firewall Rule** allowing port **5432**.
- Restarts PostgreSQL service.
- Displays your **Windows PC LAN IP Address** (e.g. `192.168.1.100`).

---

## 🌐 Step 2: Deploy Application on Ubuntu Server

On your **Ubuntu Server**:

1. Run the deployment script, passing your **Windows PC LAN IP Address** via `--db-host`:

```bash
chmod +x deploy_ubuntu_native.sh
sudo bash deploy_ubuntu_native.sh --db-host 192.168.1.100
```
*(Replace `192.168.1.100` with the actual LAN IP of your Windows PC shown by the PowerShell script)*

---

## 🔧 Step 3: Verify Remote Database Connection

From your **Ubuntu Server** terminal, you can test connectivity to your Windows PC database:

```bash
# Test PostgreSQL Port Connection
nc -zv 192.168.1.100 5432

# Test PostgreSQL Database Login
psql -h 192.168.1.100 -U edumi_user -d edumi_db
```

---

## ❓ Troubleshooting Connection Issues

1. **Firewall Blocking**: Ensure Windows Firewall port 5432 rule is active. In PowerShell as Admin run:
   ```powershell
   Get-NetFirewallRule -DisplayName "Edumi-PostgreSQL-5432"
   ```
2. **Ping Test**: Ensure Ubuntu server can ping Windows PC IP (`ping 192.168.1.100`).
3. **pg_hba.conf**: Ensure `E:\edumi_postgres_data\pg_hba.conf` contains:
   ```
   host    all             all             0.0.0.0/0               scram-sha-256
   ```
