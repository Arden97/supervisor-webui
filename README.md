# SupervisorAPI

**Supervisor Webui** is a FastAPI-based web API that allows you to monitor and control remote processes (via `supervisord` XML-RPC APIs) and containers (via the Portainer API). It provides a unified overview and control surface for managing an infrastructure composed of various platforms.

---

## 🚀 Features

- 📊 **Infrastructure Overview**: Get a centralized view of all monitored platforms, processes, and containers.
- 🔁 **Control**: Start, stop, or restart any supervised process or container.
- 📥 **Log Access**: Download logs for troubleshooting or monitoring.

---

## 🛠 Installation

### Requirements

- An **SQL database** for storing static data:
  - Platforms, supervisors, processes, containers, log paths, etc.
  - See `initial_setup.sql` for schema setup.
- **Supervisors**, **processes**, and **containers** must already be configured on the target (remote) platforms.
- **nginx** is used as a secure entrypoint and reverse proxy:
  - Make sure you generate necessary ssl certificates.
  - Ensure all listed ports in nginx config are allowed by your system firewall.
- **Portainer** should also be set up and preferably run on the **same host** as Supervisor Webui.

### Setup Instructions

1. Clone the repository.
2. Gather all of the nessecary information about processes and containers on different platforms and modify `initial_setup.sql` to your needs.
3. Configure all enviromental variables in `supervisor-webui.env` according to your setup
4. Change access port in nginx configuration files and generate ssl certificates.
5. Specify all of your remote platforms in `inventory.ini` inside of `[servers]` section
6. Change mounting point for a `/log` directory in `playbook.yml`
7. Run `playbook.yml` using:
   ```bash
   ansible-playbook ./deploy/ansible/playbook.yml -i ./deploy/ansible/inventory.ini
   ```

## 🧰 Technologies Used

- **FastAPI** – Web framework for building the HTTP API
- **Portainer** – API and UI for Docker container management
- **XML-RPC** – Interface for communicating with `supervisord` on remote systems
- **nginx** – Acts as a reverse proxy with SSL support and access control
- **Ansible** – Manages automated deployment and remote setup

## 📡 Supported Requests

Check out `webserver.py` for more details about request arguments and expected responses.

### 🔐 Authentication
```bash
POST http://127.0.0.1:8080/login
  -H "Content-Type: application/x-www-form-urlencoded"
  -d "username=admin&password=password"
```

# 🔄 Data Refresh

- `GET https://supervisor-webui:8443/refresh-processes`  
  Refresh process data from all supervisors.

- `GET https://supervisor-webui:8443/refresh-containers`  
  Refresh container data from Portainer.

---

# 📊 Data Overview

- `GET https://supervisor-webui:8443/get-data`  
  Retrieve a full infrastructure overview (platforms, supervisors, containers, and processes).

---

# 🛠️ Control: Restart / Stop

- `GET https://supervisor-webui:8443/restart-process`  
  Restart a specified process.

- `GET https://supervisor-webui:8443/restart-container`  
  Restart a specified container.

- `GET https://supervisor-webui:8443/stop-process`  
  Stop a specified process.

- `GET https://supervisor-webui:8443/stop-container`  
  Stop a specified container.


# 📄 Logs

- `GET https://supervisor-webui:8443/show-process-logs`  
  List available logs for a specified process.

- `GET https://supervisor-webui:8443/show-container-logs`  
  List available logs for a specified container.

- `GET https://supervisor-webui:8443/download-process-log`  
  Download a specific log file for a process.

- `GET https://supervisor-webui:8443/download-container-log`  
  Download a specific log file for a container.


