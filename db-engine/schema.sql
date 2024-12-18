BEGIN;

SET LOCAL citus.multi_shard_modify_mode TO 'sequential';

-- CREATE OR REPLACE FUNCTION log_schema_changes()
-- RETURNS event_trigger AS $$
-- DECLARE
--     r RECORD;
-- BEGIN
--     FOR r IN SELECT * FROM pg_event_trigger_ddl_commands() LOOP
--         PERFORM pg_notify('schema_changes', json_build_object(
--             'command_tag', r.command_tag,
--             'object_type', r.object_type,
--             'schema_name', r.schema_name,
--             'object_identity', r.object_identity
--         )::text);
--     END LOOP;
-- END;
-- $$
-- LANGUAGE plpgsql;

-- -- Create event trigger for schema changes
-- CREATE EVENT TRIGGER schema_change_trigger
-- ON ddl_command_end
-- EXECUTE FUNCTION log_schema_changes();

CREATE TABLE university(
    uni_id VARCHAR(5),
    university_name VARCHAR(25),
    city VARCHAR(25),
    state VARCHAR(25),
    PRIMARY KEY (uni_id)
);
SELECT create_distributed_table('university', 'uni_id');

CREATE TABLE fest(
    fest_id VARCHAR(5),
    fest_name VARCHAR(25) NOT NULL,
    year DATE,
    head_teamID VARCHAR(5),
    uni_id VARCHAR(5),
    PRIMARY KEY (uni_id, fest_id),
    FOREIGN KEY (uni_id) REFERENCES university(uni_id)
);
SELECT create_distributed_table('fest', 'uni_id');

CREATE TABLE team(
    team_id VARCHAR(5),
    team_name VARCHAR(25) NOT NULL,
    team_type INT,
    fest_id VARCHAR(5),
    uni_id VARCHAR(5),
    PRIMARY KEY (uni_id, team_id),
    FOREIGN KEY (uni_id, fest_id) REFERENCES fest(uni_id, fest_id)
);
SELECT create_distributed_table('team', 'uni_id');

ALTER TABLE fest ADD CONSTRAINT fest_head_name FOREIGN KEY(uni_id, head_teamID) REFERENCES team(uni_id, team_id);

CREATE TABLE member(
    mem_id VARCHAR(5),
    mem_name VARCHAR(25) NOT NULL,
    DOB DATE,
    super_memID VARCHAR(5),
    team_id VARCHAR(5),
    uni_id VARCHAR(5),
    PRIMARY KEY (uni_id, mem_id),
    FOREIGN KEY (uni_id, super_memID) REFERENCES member(uni_id, mem_id),
    FOREIGN KEY (uni_id, team_id) REFERENCES team(uni_id, team_id)
);
SELECT create_distributed_table('member', 'uni_id');

CREATE TABLE event(
    event_id VARCHAR(5),
    event_name VARCHAR(25) NOT NULL,
    building VARCHAR(15),
    floor VARCHAR(10),
    room_no INT,
    price DECIMAL(10,2),
    team_id VARCHAR(5),
    uni_id VARCHAR(5),
    PRIMARY KEY (uni_id, event_id),
    CHECK (price <= 1500.00),
    FOREIGN KEY (uni_id, team_id) REFERENCES team(uni_id, team_id) ON DELETE CASCADE
);
SELECT create_distributed_table('event', 'uni_id');

CREATE TABLE event_conduction(
    event_id VARCHAR(5),
    date_of_conduction DATE,
    uni_id VARCHAR(5),
    PRIMARY KEY(uni_id, event_id, date_of_conduction),
    FOREIGN KEY (uni_id, event_id) REFERENCES event(uni_id, event_id)
);
SELECT create_distributed_table('event_conduction', 'uni_id');

CREATE TABLE participant(
    SRN VARCHAR(10),
    name VARCHAR(25) NOT NULL,
    department VARCHAR(20),
    semester INT,
    gender INT,
    uni_id VARCHAR(5),
    PRIMARY KEY (uni_id, SRN),
    FOREIGN KEY (uni_id) REFERENCES university(uni_id)
);
SELECT create_distributed_table('participant', 'uni_id');

CREATE TABLE visitor(
    SRN VARCHAR(10),
    name VARCHAR(25),
    age INT,
    gender INT,
    uni_id VARCHAR(5),
    PRIMARY KEY (uni_id, SRN, name),
    FOREIGN KEY (uni_id, SRN) REFERENCES participant(uni_id, SRN)
);
SELECT create_distributed_table('visitor', 'uni_id');

CREATE TABLE registration(
    event_id VARCHAR(5),
    SRN VARCHAR(10),
    registration_id VARCHAR(5) NOT NULL,
    uni_id VARCHAR(5),
    PRIMARY KEY (uni_id, event_id, SRN),
    FOREIGN KEY (uni_id, event_id) REFERENCES event(uni_id, event_id),
    FOREIGN KEY (uni_id, SRN) REFERENCES participant(uni_id, SRN)
);
SELECT create_distributed_table('registration', 'uni_id');

CREATE TABLE stall(
    stall_id VARCHAR(5),
    name VARCHAR(25) NOT NULL,
    fest_id VARCHAR(5),
    uni_id VARCHAR(5),
    PRIMARY KEY (uni_id, stall_id),
    FOREIGN KEY (uni_id, fest_id) REFERENCES fest(uni_id, fest_id)
);
SELECT create_distributed_table('stall', 'uni_id');

CREATE TABLE item(
    name VARCHAR(25),
    type INT,
    uni_id VARCHAR(5),
    PRIMARY KEY (uni_id, name),
    FOREIGN KEY (uni_id) REFERENCES university(uni_id)
);
SELECT create_distributed_table('item', 'uni_id');

CREATE TABLE stall_items(
    stall_id VARCHAR(5),
    item_name VARCHAR(25),
    price_per_unit DECIMAL(10,2),
    total_quantity INT,
    uni_id VARCHAR(5),
    PRIMARY KEY (uni_id, stall_id, item_name),
    FOREIGN KEY (uni_id, stall_id) REFERENCES stall(uni_id, stall_id),
    FOREIGN KEY (uni_id, item_name) REFERENCES item(uni_id, name)
);
SELECT create_distributed_table('stall_items', 'uni_id');

CREATE TABLE purchased(
    SRN VARCHAR(10),
    stall_id VARCHAR(5),
    item_name VARCHAR(25),
    timestamp TIMESTAMP,
    quantity INT,
    uni_id VARCHAR(5),
    PRIMARY KEY (uni_id, SRN, stall_id, item_name, timestamp),
    FOREIGN KEY (uni_id, SRN) REFERENCES participant(uni_id, SRN),
    FOREIGN KEY (uni_id, stall_id) REFERENCES stall(uni_id, stall_id),
    FOREIGN KEY (uni_id, item_name) REFERENCES item(uni_id, name)
);
SELECT create_distributed_table('purchased', 'uni_id');

-- CREATE OR REPLACE FUNCTION notify_data_changes()
-- RETURNS trigger AS $$
-- BEGIN
--     PERFORM pg_notify('data_changes', json_build_object(
--         'university_id', COALESCE(NEW.uni_id, OLD.uni_id),
--         'table_name', TG_TABLE_NAME,
--         'operation', TG_OP
--     )::text);
--     RETURN NEW;
-- END;
-- $$
-- LANGUAGE plpgsql;

-- SELECT run_command_on_shards(
--     'university', 
--     $cmd$
--         CREATE TRIGGER university_changes_trigger
--         AFTER INSERT OR UPDATE OR DELETE ON %s
--         FOR EACH ROW EXECUTE FUNCTION notify_data_changes()
--     $cmd$
-- );

-- SELECT run_command_on_shards(
--     'fest', 
--     $cmd$
--         CREATE TRIGGER fest_changes_trigger
--         AFTER INSERT OR UPDATE OR DELETE ON %s
--         FOR EACH ROW EXECUTE FUNCTION notify_data_changes()
--     $cmd$
-- );

-- SELECT run_command_on_shards(
--     'team', 
--     $cmd$
--         CREATE TRIGGER team_changes_trigger
--         AFTER INSERT OR UPDATE OR DELETE ON %s
--         FOR EACH ROW EXECUTE FUNCTION notify_data_changes()
--     $cmd$
-- );

-- SELECT run_command_on_shards(
--     'member', 
--     $cmd$
--         CREATE TRIGGER member_changes_trigger
--         AFTER INSERT OR UPDATE OR DELETE ON %s
--         FOR EACH ROW EXECUTE FUNCTION notify_data_changes()
--     $cmd$
-- );

-- SELECT run_command_on_shards(
--     'event', 
--     $cmd$
--         CREATE TRIGGER event_changes_trigger
--         AFTER INSERT OR UPDATE OR DELETE ON %s
--         FOR EACH ROW EXECUTE FUNCTION notify_data_changes()
--     $cmd$
-- );

-- SELECT run_command_on_shards(
--     'event_conduction', 
--     $cmd$
--         CREATE TRIGGER event_conduction_changes_trigger
--         AFTER INSERT OR UPDATE OR DELETE ON %s
--         FOR EACH ROW EXECUTE FUNCTION notify_data_changes()
--     $cmd$
-- );

-- SELECT run_command_on_shards(
--     'participant', 
--     $cmd$
--         CREATE TRIGGER participant_changes_trigger
--         AFTER INSERT OR UPDATE OR DELETE ON %s
--         FOR EACH ROW EXECUTE FUNCTION notify_data_changes()
--     $cmd$
-- );

-- SELECT run_command_on_shards(
--     'visitor', 
--     $cmd$
--         CREATE TRIGGER visitor_changes_trigger
--         AFTER INSERT OR UPDATE OR DELETE ON %s
--         FOR EACH ROW EXECUTE FUNCTION notify_data_changes()
--     $cmd$
-- );

-- SELECT run_command_on_shards(
--     'registration', 
--     $cmd$
--         CREATE TRIGGER registration_changes_trigger
--         AFTER INSERT OR UPDATE OR DELETE ON %s
--         FOR EACH ROW EXECUTE FUNCTION notify_data_changes()
--     $cmd$
-- );

-- SELECT run_command_on_shards(
--     'stall', 
--     $cmd$
--         CREATE TRIGGER stall_changes_trigger
--         AFTER INSERT OR UPDATE OR DELETE ON %s
--         FOR EACH ROW EXECUTE FUNCTION notify_data_changes()
--     $cmd$
-- );

-- SELECT run_command_on_shards(
--     'item', 
--     $cmd$
--         CREATE TRIGGER item_changes_trigger
--         AFTER INSERT OR UPDATE OR DELETE ON %s
--         FOR EACH ROW EXECUTE FUNCTION notify_data_changes()
--     $cmd$
-- );

-- SELECT run_command_on_shards(
--     'stall_items', 
--     $cmd$
--         CREATE TRIGGER stall_items_changes_trigger
--         AFTER INSERT OR UPDATE OR DELETE ON %s
--         FOR EACH ROW EXECUTE FUNCTION notify_data_changes()
--     $cmd$
-- );

-- SELECT run_command_on_shards(
--     'purchased', 
--     $cmd$
--         CREATE TRIGGER purchased_changes_trigger
--         AFTER INSERT OR UPDATE OR DELETE ON %s
--         FOR EACH ROW EXECUTE FUNCTION notify_data_changes()
--     $cmd$
-- );

-- COMMIT;