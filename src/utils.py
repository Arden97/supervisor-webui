import argparse
import base64
import json
import os
import ssl
import subprocess
import sys
import time
import traceback
import xmlrpc
from datetime import UTC, datetime
from xmlrpc.client import (
    ServerProxy,
)

import paramiko
import psycopg2
import requests


def read_args() -> dict:
    arg_parser = argparse.ArgumentParser(
        description="HTTP server poskytujici data na WebUI"
    )
    arg_parser.add_argument(
        "host",
        type=str,
        nargs='?',
        help="ip adresa hostu, na kterem pobezi server (default: localhost)",
        default="localhost",
    )
    arg_parser.add_argument(
        "port",
        type=int,
        nargs='?',
        help="systemovy port, na kterem pobezi server (default: 8080 pro HTTP a 8443 pro HTTPS)",
        default=8080,
    )
    arg_parser.add_argument(
        "--debug",
        dest="debug_on",
        action="store_const",
        const=True,
        help="zapnuti debugovaciho rezimu",
        default=False,
    )
    args = arg_parser.parse_args()

    return {
        "host": args.host,
        "port": args.port,
        "debug_on": args.debug_on
    }

def read_json(filepath: str) -> dict | None:
    try:
        with open(filepath) as json_file:
            return json.load(json_file)
    except Exception as err:
        print(f"Error loading {filepath}: {err}")
        return None

class AuthTransport(xmlrpc.client.SafeTransport):
    def __init__(self, username, password, context):
        super().__init__(context=context)
        self.username = username
        self.password = password

    def send_headers(self, connection, headers):
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        connection.putheader("Authorization", f"Basic {encoded}")
        super().send_headers(connection, headers)

class SupervisorWebuiUtils:
    def __init__(self, debug: bool) -> None:
        self.debug = debug
        self.portainer_api_token = os.getenv('PORTAINER_API_TOKEN')
        self.portainer_url = f"https://{os.getenv('PORTAINER_HOST')}:{os.getenv('PORTAINER_PORT')}/api"
        self.data_db = psycopg2.connect(
            dbname=os.getenv("WEBUI_DATA_DB_NAME"),
            user=os.getenv("WEBUI_DATA_DB_USERNAME"),
            password=os.getenv("WEBUI_DATA_DB_PASSWORD"),
            host=os.getenv("WEBUI_DATA_DB_HOST"),
            port=os.getenv("WEBUI_DATA_DB_PORT")
        )
        self.supervisors_apis= self.set_supervisors()
        self.host_dir = os.getenv("SUPERVISOR_HOST_DIR")

    def set_supervisors(self) -> list:
        return_list = []
        supervisor_username = os.getenv("SUPERVISOR_USER")
        supervisor_password = os.getenv("SUPERVISOR_PASSWORD")
        with self.data_db.cursor() as cursor:
            cursor.execute("""SELECT * FROM platforms;""")
            platforms = cursor.fetchall()
            for platform in platforms:
                endpoint_id = platform[0]
                cursor.execute(f"""SELECT * FROM supervisors
                               WHERE platform_id = '{endpoint_id}';""")
                supervisors = cursor.fetchall()
                for supervisor in supervisors:
                    context = ssl._create_unverified_context()
                    return_list.append({
                        "platform_endpoint_id": endpoint_id,
                        "supervisor_id": supervisor[0],
                        "name": supervisor[1],
                        "api": ServerProxy(
                            f"https://{supervisor[2]}:{supervisor[3]}/supervisor/RPC2",
                            transport=AuthTransport(supervisor_username,
                                                    supervisor_password,context),
                            allow_none=True
                        ).supervisor
                    })

        return return_list

    def debug_print(self, msg: str, prettyprint=False) -> None:
        if self.debug:
            if prettyprint:
                print(json.dumps(msg, indent=4), file=sys.stderr)
            else:
                print(f"[DEBUG]: {msg}", file=sys.stderr)

    def run_system_command(self, command: str, debug=True) -> str | None:
        # Provedeni prikazu
        response = subprocess.run(command,
                                  check=False,
                                  capture_output=True,
                                  text=True,
                                  shell=True).stdout
        if len(response) != 0:
            response = response.strip()
        if not response:
            response = None
        if debug:
            self.debug_print(f"Command = '{command}' returned '{response}'")

        return response

    def get_uptime(self) -> dict:
        device_uptime = self.run_system_command("cat /proc/uptime")
        uptime = float(device_uptime.split(' ')[0])

        uptime_days, remainder = divmod(int(uptime), 24 * 3600)
        uptime_hours, remainder = divmod(remainder, 3600)
        uptime_minutes, uptime_seconds = divmod(remainder, 60)

        return {
            "days": uptime_days,
            "hours": uptime_hours,
            "minutes": uptime_minutes,
            "seconds": uptime_seconds
        }

    def parse_uptime(self, uptime_str: str) -> tuple | None:
        if not uptime_str:
            return None

        len_uptime_str_few_minutes = 2
        len_uptime_str_few_hours = 3

        if "-" in uptime_str: # format 1-01:01:01
            splited = uptime_str.split("-")
            days = int(splited[0])
            tmp = splited[1].split(":")
            hours = int(tmp[0])
            minutes = int(tmp[1])
            seconds = int(tmp[2])
        else:
            splited = uptime_str.split(":") # format 01:01
            if len(splited) == len_uptime_str_few_minutes:
                days = None
                hours = None
                minutes = int(splited[0])
                seconds = int(splited[1])
            elif len(splited) == len_uptime_str_few_hours: # format 01:01:01
                days = None
                hours = int(splited[0])
                minutes = int(splited[1])
                seconds = int(splited[2])

        return (days, hours, minutes, seconds)

    def check_uptime(self, seconds: int) -> dict:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60

        return {
            "days": days,
            "hours": hours,
            "minutes": minutes,
            "seconds": seconds
        }

    def get_container_from_config(self, platform: dict, container_name: str) -> dict:
        return next((
                c
                for c in platform.get("containers")
                if c.get("name") == container_name
            ),
            None
        )

    def get_supervisor_by_name(self, endpoint_id: int, supervisor_name: str) -> ServerProxy:
        return next((
                s
                for s in self.supervisors_apis
                if s.get("name") == supervisor_name
                and s.get("platform_endpoint_id") == endpoint_id
            ),
            None
        )

    def get_supervisor_from_config(self, platform: dict, supervisor_name: str) -> dict:
        return next((
                s
                for s in platform.get("supervisors")
                if s.get("name") == supervisor_name
            ),
            None
        )

    def get_process_from_config(self, supervisor: dict, process_name: str) -> dict:
        return next((
                proc
                for proc in supervisor.get("processes")
                if proc.get("process_name") ==  process_name
            ),
            None
        )

    def get_container_name_by_id(self, endpoint_id: int, container_id: str) -> str:
        request = (
            f"{self.portainer_url}/endpoints/{endpoint_id}/docker/"
            f"containers/{container_id}/json"
        )
        headers = {
            "X-API-Key": self.portainer_api_token,
        }
        response = requests.get(request, headers=headers, verify=False)
        if response.ok:
            return response.json().get("Name").split("/")[1]
        return ""

    def get_platforms_info(self) -> list:
        return_list = []
        with self.data_db.cursor() as cursor:
            cursor.execute("""SELECT * FROM platforms;""")
            platforms = cursor.fetchall()
            for platform in platforms:
                endpoint_id = platform[0]
                platform_name = platform[1]

                cursor.execute(f"""SELECT * FROM supervisors
                                WHERE platform_id = '{endpoint_id}'""")
                supervisors_data = cursor.fetchall()
                supervisors = []
                for supervisor in supervisors_data:
                    try:
                        name = supervisor[1]
                        supervisor_with_api = self.get_supervisor_by_name(endpoint_id, name)
                        supervisors.append({
                            "name": name,
                            "processes": self.get_processes_info(supervisor_with_api)
                        })
                    except Exception:
                        self.debug_print("ERROR pri ziskavani informaci o supervisoru")
                        self.debug_print(f"Platform ID: {endpoint_id}")
                        self.debug_print(f"Supervisor host: {supervisor[2]}")
                        self.debug_print(f"Supervisor port: {supervisor[3]}")
                        self.debug_print(traceback.format_exc())


                return_list.append({
                    "name": platform_name,
                    "platform_endpoint_id": endpoint_id,
                    "supervisors": supervisors,
                    "portainer": {
                        "name": "Kontejnery",
                        "containers": self.get_containers_info(platform[0])
                    }
                })

            return return_list

    def parse_portainer_status_to_uptime(self, start_str: str) -> dict:
        start_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        uptime = datetime.now(UTC) - start_time

        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        return {
            "days": days,
            "hours": hours,
            "minutes": minutes,
            "seconds": seconds
        }

    def get_containers_info(self, platform_id: int) -> list:
        return_list = []
        endpoint_url = f"{self.portainer_url}/endpoints/{platform_id}"
        headers = {
            "X-API-Key": self.portainer_api_token,
        }
        platform = requests.get(endpoint_url, headers=headers, verify=False).json()
        containers = platform.get("Snapshots")[0].get("DockerSnapshotRaw").get("Containers")
        for container in containers:
            container_id = container.get("Id")
            name = container.get("Names")[0].split("/")[1]
            container_data = self.get_container_data(platform_id, name)
            if not container_data:
                continue
            description = container_data[2]

            endpoint_url_to_verify = (
                f"{self.portainer_url}/endpoints/{platform_id}/docker/containers/{container_id}/json"
            )
            container_state = requests.get(endpoint_url_to_verify,
                                           headers=headers,
                                           verify=False).json().get("State")
            state = container_state.get("Status").capitalize()
            if state == "Running":
                uptime = self.parse_portainer_status_to_uptime(container_state.get("StartedAt"))
            else:
                uptime = {
                    "days": 0,
                    "hours": 0,
                    "minutes": 0,
                    "seconds": 0
                }

            return_list.append({
                "container_id": container_id,
                "state": state,
                "uptime": uptime,
                "container_name": name,
                "description": description
            })

        return return_list

    def refresh_processes_table(self, endpoint_id: int, supervisor_name: str) -> dict:
        data = self.get_platforms_info()
        try:
            platform = next((
                    p
                    for p in data
                    if p.get("platform_endpoint_id") == endpoint_id
                ),
                None
            )
            supervisor = next((
                    s
                    for s in platform.get("supervisors")
                    if s.get("name") == supervisor_name
                ),
                None
            )
            processes = supervisor.get("processes")
            return {
                "result": "success",
                "notification": "Tabulka procesů byla úspešně aktualizováná",
                "uptime": self.get_uptime(),
                "last_update": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                "processes": processes
            }
        except Exception:
            self.debug_print(traceback.format_exc())
            return {
                "result": "error",
                "notification": "Chyba při načtení dat z platformy",
                "uptime": self.get_uptime(),
                "last_update": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                "processes": []
            }

    def refresh_containers_table(self, endpoint_id: int) -> dict:
        data = self.get_platforms_info()
        try:
            platform = next((
                    p
                    for p in data
                    if p.get("platform_endpoint_id") == endpoint_id
                ),
                None
            )
            containers = platform.get("portainer").get("containers")
            return {
                "result": "success",
                "notification": "Tabulka kontejnerů byla úspešně aktualizováná",
                "uptime": self.get_uptime(),
                "last_update": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                "containers": containers
            }
        except Exception:
            self.debug_print(traceback.format_exc())
            return {
                "result": "error",
                "notification": "Chyba při načtení dat z platformy",
                "uptime": self.get_uptime(),
                "last_update": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                "containers": []
            }

    def get_processes_info(self, supervisor_with_api: dict) -> list:
        return_list = []
        supervisor_api = supervisor_with_api.get("api")
        all_processes = supervisor_api.getAllProcessInfo()
        for process in all_processes:
            try:
                name = process.get("name")
                pid = process.get("pid")
                state = process.get("statename").lower().capitalize()
                process_data = self.get_process_data(supervisor_with_api.get("supervisor_id"), name)
                if state != "Running":
                    uptime_seconds = 0
                else:
                    uptime_seconds = process.get('now') - process.get('start')
                process_to_return = {
                    "description": process_data[2],
                    "process_name": name,
                    "uptime": self.check_uptime(uptime_seconds),
                    "state": state,
                    "pid": pid,
                }
                self.debug_print(name.upper())
                self.debug_print(process_to_return, prettyprint=True)
                return_list.append(process_to_return)
            except StopIteration:
                continue

        return return_list

    def restart_process(self, supervisor_api: ServerProxy, name: str) -> tuple[str, str]:
        process = supervisor_api.getProcessInfo(name)
        if process.get("pid"):
            self.debug_print(f"Zastavení procesu {name}")
            supervisor_api.stopProcess(name)
            time.sleep(1)
        if supervisor_api.startProcess(name):
            self.debug_print(f"Nastartování procesu {name}")
            return ("success", f"Restart procesu {name} proběhl úspešně")

        return ("error", f"Při restartu procesu {name} nastala chyba")

    def stop_process(self, supervisor_api: ServerProxy, name: str) -> tuple[str, str]:
        process = supervisor_api.getProcessInfo(name)
        if process.get("pid"):
            try:
                self.debug_print(f"Zastavení procesu {name}")
                supervisor_api.stopProcess(name)
                return ("success", f"Zastavení procesu {name} proběhlo úspešně")
            except Exception:
                return ("error", f"Při zastavení procesu {name} nastala chyba")
        else:
            return ("info", f"Proces {name} nebeží")

    def handle_process_command(self, supervisor_api: ServerProxy, proc_name: str, cmd: str) -> dict:
        commands = {
            "stop": self.stop_process,
            "restart": self.restart_process
        }
        operation = commands.get(cmd)
        result, notification = operation(supervisor_api, proc_name)

        return_dict = {
            "process_name": proc_name,
            "command": cmd,
            "result": result,
            "notification": notification
        }

        process = supervisor_api.getProcessInfo(proc_name)
        return_dict.update({
            "pid": process.get("pid"),
            "state": process.get("statename").lower().capitalize()
        })

        return return_dict

    def handle_container_command(self, endpoint_id: int, container_id: str, cmd: str) -> dict:
        commands = {
            "stop": self.stop_container,
            "restart": self.restart_container
        }
        operation = commands.get(cmd)
        result, notification = operation(endpoint_id, container_id)

        containers = self.get_containers_info(endpoint_id)
        container_name = self.get_container_name_by_id(endpoint_id, container_id)
        container = next((c for c in containers if c.get("container_name") == container_name), None)

        return {
            "container_id": container_id,
            "command": cmd,
            "state": container.get("state"),
            "result": result,
            "notification": notification
        }

    def stop_container(self, endpoint_id: int, container_id: str) -> tuple[str, str]:
        request = (
            f"{self.portainer_url}/endpoints/{endpoint_id}/docker/"
            f"containers/{container_id}/stop"
        )
        headers = {
            "X-API-Key": self.portainer_api_token,
        }
        response = requests.post(request, headers=headers, verify=False)

        if response.ok:
            return ("success",  "Container was stopped")
        else:
            return ("error",  "Container was not stopped or it is stopped already")

    def restart_container(self, endpoint_id: int, container_id: str) -> tuple[str, str]:
        request = (
            f"{self.portainer_url}/endpoints/{endpoint_id}/docker/"
            f"containers/{container_id}/restart"
        )
        headers = {
            "X-API-Key": self.portainer_api_token,
        }
        response = requests.post(request, headers=headers, verify=False)

        if response.ok:
            return ("success", "Container was restarted")
        else:
            return ("error",  "Container was not restarted")

    def show_process_logs(self, platform_id: int, supervisor_name: str, process_name: str) -> dict:
        supervisor_id = self.get_supervisor_data(platform_id, supervisor_name)[0]
        process_id = self.get_process_data(supervisor_id, process_name)[0]
        with self.data_db.cursor() as cursor:
            cursor.execute(f"""SELECT * FROM process_logs WHERE process_id = '{process_id}';""")
            logs = cursor.fetchall()
        
        log_names = []
        for log in logs:
            log_names.append(log[1])

        return {
            "platform_id": platform_id,
            "supervisor_name": supervisor_name,
            "result": "success",
            "process_name": process_name,
            "logs": log_names
        }

    def show_container_logs(self, platform_id: int, container_name: str) -> dict:
        container_id = self.get_container_data(platform_id, container_name)[0]
        with self.data_db.cursor() as cursor:
            cursor.execute(f"""SELECT * FROM container_logs
                           WHERE container_id = '{container_id}';""")
            logs = cursor.fetchall()

        log_names = []
        for log in logs:
            log_names.append(log[1])

        return {
            "platform_id": platform_id,
            "result": "success",
            "container_name": container_name,
            "logs": log_names
        }

    def download_file(self, hostname: str, port: int, username: str, logpath: str) -> str:
        os.makedirs(f"{self.host_dir}logs/", exist_ok=True)
        filename = f"{self.host_dir}logs/{logpath.split('/')[-1]}"
        if os.path.exists(filename):
            return filename

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname, port=port, username=username)
        sftp = ssh.open_sftp()
        try:
            self.run_system_command(f"touch {filename}")
            sftp.get(logpath, filename)
        except FileNotFoundError:
            self.debug_print(traceback.format_exc())
            self.debug_print(f"[ERROR] soubor {logpath} neexistuje na {hostname}")
            return None

        return filename

    def get_platform_data(self, endpoint_id: int) -> list:
        with self.data_db.cursor() as cursor:
            cursor.execute(f"""SELECT * FROM platforms WHERE id = '{endpoint_id}';""")

            return cursor.fetchone()
        
    def get_supervisor_data(self, endpoint_id: int, supervisor_name: str) -> list:
        with self.data_db.cursor() as cursor:
            cursor.execute(f"""SELECT * FROM supervisors 
                            WHERE platform_id = '{endpoint_id}'
                            AND supervisor_name = '{supervisor_name}';""")
            
            return cursor.fetchone()
        
    def get_process_data(self, supervisor_id: int, process_name: str) -> list:
        with self.data_db.cursor() as cursor:
            cursor.execute(f"""SELECT * FROM processes WHERE supervisor_id = '{supervisor_id}'
                        AND process_name = '{process_name}';""")
            
            return cursor.fetchone()
        
    def get_process_log_data(self, process_id: int, log_name: str) -> list:
        with self.data_db.cursor() as cursor:
            cursor.execute(f"""SELECT * FROM process_logs WHERE process_id = '{process_id}'
                        AND log_name = '{log_name}';""")
            
            return cursor.fetchone()
        
    def get_container_data(self, endpoint_id: int, container_name: str) -> list:
        with self.data_db.cursor() as cursor:
            cursor.execute(f"""SELECT * FROM containers WHERE platform_id = '{endpoint_id}'
                        AND container_name = '{container_name}';""")
            
            return cursor.fetchone()
        
    def get_container_log_data(self, container_id: str, log_name: str) -> list:
        with self.data_db.cursor() as cursor:
            cursor.execute(f"""SELECT * FROM container_logs WHERE container_id = '{container_id}'
                        AND log_name = '{log_name}';""")
            
            return cursor.fetchone()

    def get_process_log_download_data(
            self,
            endpoint_id: int,
            supervisor_name: str,
            process_name: str,
            log_name: str
    ) -> tuple[str, str, str]:
        
        platform = self.get_platform_data(endpoint_id)
        platform_host = platform[2]
        platform_user = platform[3]
        supervisor_id = self.get_supervisor_data(endpoint_id,supervisor_name)[0]
        process_id = self.get_process_data(supervisor_id, process_name)[0]
        log_path = self.get_process_log_data(process_id, log_name)[2]

        return platform_host, platform_user, log_path+log_name

    def get_container_log_download_data(
            self,
            endpoint_id: int,
            container_name: str,
            log_name: str
        ) -> tuple[str, str, str]:
        
        platform = self.get_platform_data(endpoint_id)
        platform_host = platform[2]
        platform_user = platform[3]
        container_id = self.get_container_data(endpoint_id, container_name)[0]
        log_path = self.get_container_log_data(container_id, log_name)[2]

        return platform_host, platform_user, log_path+log_name
        






