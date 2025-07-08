BEGIN TRANSACTION;

CREATE TABLE platforms (
    id INTEGER PRIMARY KEY,
    platform_name TEXT NOT NULL,
    host TEXT NOT NULL,
    ssh_user TEXT NOT NULL
);
INSERT INTO platforms (id, platform_name, host, ssh_user) VALUES
    (3, 'Platform #1', '127.0.0.1', 'root'),
    (4, 'Platform #2', '192.168.0.9', 'root');
-- TODO: add your platforms

CREATE TABLE containers (
    id SERIAL PRIMARY KEY,
    container_name TEXT NOT NULL,
    description TEXT,
    platform_id INTEGER NOT NULL,
    FOREIGN KEY (platform_id) REFERENCES platforms(id)
);
INSERT INTO containers (container_name, description, platform_id) VALUES
    ('nginx', 'Nginx container', 3),
    ('httpd', 'Apache web server', 3),
    ('nginx', 'Nginx container', 4),
    ('postgres', 'Postgres Database', 4);
-- TODO: add your containers

CREATE TABLE container_logs (
    id SERIAL PRIMARY KEY,
    log_name TEXT NOT NULL,
    log_path TEXT NOT NULL,
    container_id INTEGER NOT NULL,
    FOREIGN KEY (container_id) REFERENCES containers(id)
);
INSERT INTO container_logs (log_name, log_path, container_id) VALUES
    ('test1.out.log', '/root/supervisor-webui/logs/', 1),
    ('test1.err.log', '/root/supervisor-webui/logs/', 1),
    ('test1.out.log', '/root/supervisor-webui/logs/', 2),
    ('test1.err.log', '/root/supervisor-webui/logs/', 2),
    ('test1.out.log', '/root/supervisor-webui/logs/', 3),
    ('test1.err.log', '/root/supervisor-webui/logs/', 3),
    ('test1.out.log', '/root/supervisor-webui/logs/', 4),
    ('test1.err.log', '/root/supervisor-webui/logs/', 4);
-- TODO: add your custom logs

CREATE TABLE supervisors (
    id SERIAL PRIMARY KEY,
    supervisor_name TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    platform_id INTEGER NOT NULL,
    FOREIGN KEY (platform_id) REFERENCES platforms(id)
);
INSERT INTO supervisors (supervisor_name, host, port, platform_id) VALUES
    ('Supervisor1', '127.0.0.1', 4444, 3),
    ('Supervisor_test_name1', '192.168.0.9', 4444, 4);
-- TODO: add your supervisors

CREATE TABLE processes (
    id SERIAL PRIMARY KEY,
    process_name TEXT NOT NULL,
    description TEXT NOT NULL,
    supervisor_id INTEGER NOT NULL,
    FOREIGN KEY (supervisor_id) REFERENCES supervisors(id)
);
INSERT INTO processes (process_name, description, supervisor_id) VALUES
    ('test1', 'Cron to check a PostgreSQL database availability', 1),
    ('test2', 'Cron to check a server load', 1),
    ('test1', 'Cron to handle PostgreSQL table cleaning', 2),
    ('test2', 'Cron that pings remote servers', 2);
-- TODO: add your processes

CREATE TABLE process_logs (
    id SERIAL PRIMARY KEY,
    log_name TEXT NOT NULL,
    log_path TEXT NOT NULL,
    process_id INTEGER NOT NULL,
    FOREIGN KEY (process_id) REFERENCES processes(id)
);
INSERT INTO process_logs (log_name, log_path, process_id) VALUES
    ('test1.out.log', '/root/supervisor-webui/logs/', 1),
    ('test1.err.log', '/root/supervisor-webui/logs/', 1),
    ('test1.out.log', '/root/supervisor-webui/logs/', 2),
    ('test1.err.log', '/root/supervisor-webui/logs/', 2),
    ('test1.out.log', '/root/supervisor-webui/logs/', 3),
    ('test1.err.log', '/root/supervisor-webui/logs/', 3),
    ('test1.out.log', '/root/supervisor-webui/logs/', 4),
    ('test1.err.log', '/root/supervisor-webui/logs/', 4);
-- TODO: add your custom logs

CREATE TABLE profiles (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    membership TEXT NOT NULL
);
INSERT INTO profiles (username, password, membership) VALUES
    ('admin', 'password', 'write'),
    ('control', 'password', 'read');
-- TODO: don't forget to change the passwords

COMMIT;