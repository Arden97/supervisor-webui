import hashlib
import os
import random
import string
from datetime import datetime

import psycopg2
from fastapi import Depends, FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from utils import SupervisorWebuiUtils, read_args

args = read_args()
supervisor_api = FastAPI()
supervisor_api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
server_utils = SupervisorWebuiUtils(args.get("debug_on", False))

SESSIONS = {}
class Session:
    def __init__(self, username, token, membership):
        self.username = username
        self.token = token
        self.membership = membership

class LoginResponse(BaseModel):
    access_token: str
    username: str
    result: str
    notification: str

def check_credentials(username, password):
    try:
        db_conn = psycopg2.connect(
            dbname=os.getenv("WEBUI_LOGIN_DB_NAME"),
            user=os.getenv("WEBUI_LOGIN_DB_USERNAME"),
            password=os.getenv("WEBUI_LOGIN_DB_PASSWORD"),
            host=os.getenv("WEBUI_LOGIN_DB_HOST"),
            port=os.getenv("WEBUI_LOGIN_DB_PORT")
        )
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        with db_conn.cursor() as cursor:
            cursor.execute(f"""SELECT * FROM {os.getenv("WEBUI_LOGIN_DB_TABLE")}
                           WHERE username = %s AND password = %s""",
                           (username, hashed_password))
            profile = cursor.fetchone()
            if profile and profile[1] and profile[3]:
                return profile[1], profile[3]
    except Exception as e:
        server_utils.debug_print(f"DB connection error: {e}")
        return None, None
    return False, False

def authorize(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    token = credentials.credentials
    session = SESSIONS.get(token)
    if not session:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return session

@supervisor_api.post("/login", response_model=LoginResponse)
async def login(username: str = Form(...), password: str = Form(...)):
    username_valid, membership = check_credentials(username, password)

    if username_valid and membership:
        token = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        session = Session(username, token, membership)
        SESSIONS[token] = session
        return LoginResponse(
            access_token=token,
            username=username_valid,
            result="success",
            notification=f"Welcome, {username}!"
        )
    elif username_valid is False:
        raise HTTPException(status_code=401, detail="Specified profile was not found")
    else:
        raise HTTPException(status_code=500, detail="Error, while trying to connect to DB")

@supervisor_api.get("/get-data")
async def get_data(session: Session = Depends(authorize)):
    data = {
        "server_name": server_utils.run_system_command("hostname"),
        "last_update": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "server_uptime": server_utils.get_uptime(),
        "platforms": server_utils.get_platforms_info()
    }
    return JSONResponse(
        content=data,
        status_code=200,
        headers={"Content-Type": "application/json"}
    )

@supervisor_api.get("/refresh-processes")
async def refresh_processes(
    endpoint_id: int, 
    supervisor_name: str,
    session: Session = Depends(authorize)
):
    return JSONResponse(
        content=server_utils.refresh_processes_table(endpoint_id, supervisor_name),
        status_code=200,
        headers={"Content-Type": "application/json"}
    )

@supervisor_api.get("/refresh-containers")
async def refresh_containers(
    endpoint_id: int,
    session: Session = Depends(authorize)
):
    return JSONResponse(
        content=server_utils.refresh_containers_table(endpoint_id),
        status_code=200,
        headers={"Content-Type": "application/json"}
    )

@supervisor_api.get("/restart-process")
async def restart_process(
    endpoint_id: int,
    supervisor_name: str,
    proc_name: str,
    session: Session = Depends(authorize)
):
    if session.membership != "write":
        raise HTTPException(status_code=403, detail="Operation not permitted")
    supervisor_api = server_utils.get_supervisor_by_name(endpoint_id, supervisor_name).get("api")

    return JSONResponse(
        content=server_utils.handle_process_command(supervisor_api, proc_name, "restart"),
        status_code=200,
        headers={"Content-Type": "application/json"}
    )

@supervisor_api.get("/restart-container")
async def restart_container(
    endpoint_id: int,
    container_name: str,
    session: Session = Depends(authorize)
):
    if session.membership != "write":
        raise HTTPException(status_code=403, detail="Operation not permitted")

    return JSONResponse(
        content=server_utils.handle_container_command(endpoint_id, container_name, "restart"),
        status_code=200,
        headers={"Content-Type": "application/json"}
    )

@supervisor_api.get("/stop-process")
async def stop_process(
    endpoint_id: int,
    supervisor_name: str,
    proc_name: str,
    session: Session = Depends(authorize)
):
    if session.membership != "write":
        raise HTTPException(status_code=403, detail="Operation not permitted")
    supervisor_api = server_utils.get_supervisor_by_name(endpoint_id, supervisor_name).get("api")
    
    return JSONResponse(
        content=server_utils.handle_process_command(supervisor_api, proc_name, "stop"),
        status_code=200,
        headers={"Content-Type": "application/json"}
    )

@supervisor_api.get("/stop-container")
async def stop_container(
    endpoint_id: int,
    container_name: str,
    session: Session = Depends(authorize)
):
    if session.membership != "write":
        raise HTTPException(status_code=403, detail="Operation not permitted")
    
    return JSONResponse(
        content=server_utils.handle_container_command(endpoint_id, container_name, "stop"),
        status_code=200,
        headers={"Content-Type": "application/json"}
    )

@supervisor_api.get("/show-process-logs")
async def show_process_logs(
    endpoint_id: int,
    supervisor_name: str,
    proc_name: str,
    session: Session = Depends(authorize)
):

    return JSONResponse(
        content=server_utils.show_process_logs(endpoint_id, supervisor_name, proc_name),
        status_code=200,
        headers={"Content-Type": "application/json"}
    )

@supervisor_api.get("/show-container-logs")
async def show_container_logs(
    endpoint_id: int,
    container_name: str,
    session: Session = Depends(authorize)
):

    return JSONResponse(
        content=server_utils.show_container_logs(endpoint_id, container_name),
        status_code=200,
        headers={"Content-Type": "application/json"}
    )

@supervisor_api.get("/download-process-log")
async def download_process_log(
    endpoint_id: int,
    supervisor_name: str,
    proc_name: str,
    log_name: str,
    session: Session = Depends(authorize)
):
    hostname, ssh_user, log_path = server_utils.get_process_log_download_data(
        endpoint_id,
        supervisor_name,
        proc_name,
        log_name
    )

    return FileResponse(
        path=server_utils.download_file(hostname, 22, ssh_user, log_path),
        filename=f"{log_name}_{datetime.now().strftime('%d.%m.%Y_%H:%M:%S')}",
        media_type="application/octet-stream"
    )

@supervisor_api.get("/download-container-log")
async def download_container_log(
    endpoint_id: int,
    container_name: str,
    log_name: str,
    session: Session = Depends(authorize)
):
    hostname, ssh_user, log_path = server_utils.get_container_log_download_data(
        endpoint_id,
        container_name,
        log_name
    )
    
    return FileResponse(
        path=server_utils.download_file(hostname, 22, ssh_user, log_path),
        filename=f"{log_name}_{datetime.now().strftime('%d.%m.%Y_%H:%M:%S')}",
        media_type="application/octet-stream"
    )

@supervisor_api.get("/logout")
async def logout(session: Session = Depends(authorize)):
    SESSIONS.pop(session.token, None)
    return {"result": "success", "notification": f"Goodbye, {session.username}!"}

@supervisor_api.get("/", response_class=HTMLResponse)
async def index():
    try:
        with open("frontend/index.html", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="File not found") from e


if __name__ == '__main__':
    import uvicorn
    uvicorn.run("webserver:supervisor_api",
                host=args.get("host"),
                port=args.get("port"))
