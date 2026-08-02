BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 20260802_0001

INSERT INTO alembic_version (version_num) VALUES ('20260802_0001') RETURNING alembic_version.version_num;

-- Running upgrade 20260802_0001 -> 20260802_0002

CREATE TABLE assets (
    id UUID NOT NULL, 
    object_key VARCHAR(512) NOT NULL, 
    filename VARCHAR(255) NOT NULL, 
    content_type VARCHAR(255) NOT NULL, 
    size_bytes BIGINT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (object_key)
);

UPDATE alembic_version SET version_num='20260802_0002' WHERE alembic_version.version_num = '20260802_0001';

-- Running upgrade 20260802_0002 -> 20260802_0003

CREATE TYPE projectstatus AS ENUM ('DRAFT', 'PROCESSING', 'COMPLETED', 'FAILED');

CREATE TABLE projects (
    id UUID NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    status projectstatus NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE TABLE videos (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    asset_id UUID, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(asset_id) REFERENCES assets (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id)
);

CREATE TABLE workflows (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    workflow_type VARCHAR(100) NOT NULL, 
    config JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id)
);

CREATE TYPE jobstatus AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED');

CREATE TABLE jobs (
    id UUID NOT NULL, 
    workflow_id UUID NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    status jobstatus NOT NULL, 
    input_data JSONB NOT NULL, 
    output_data JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(workflow_id) REFERENCES workflows (id)
);

UPDATE alembic_version SET version_num='20260802_0003' WHERE alembic_version.version_num = '20260802_0002';

COMMIT;

