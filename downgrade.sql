BEGIN;

-- Running downgrade 20260802_0003 -> 20260802_0002

DROP TABLE jobs;

DROP TABLE workflows;

DROP TABLE videos;

DROP TABLE projects;

UPDATE alembic_version SET version_num='20260802_0002' WHERE alembic_version.version_num = '20260802_0003';

COMMIT;

