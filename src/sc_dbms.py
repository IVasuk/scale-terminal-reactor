from peewee import *
from playhouse.postgres_ext import PostgresqlExtDatabase, DateTimeTZField

SCALEDB_TYPES = ('server','registrator')

PSQL_DB = PostgresqlExtDatabase(None)


def sc_init_database(sc_dbname, sc_user, sc_password, sc_host, sc_port, db = PSQL_DB):
    db.init(sc_dbname, user=sc_user, password=sc_password, host=sc_host, port=sc_port)


def sc_connect(db = PSQL_DB):
    return db.connect()


def sc_execute(sql_str,db = PSQL_DB):
    return db.execute_sql(sql_str)


def sc_close(db = PSQL_DB):
    return db.close()


def sc_is_closed(db = PSQL_DB):
    return db.is_closed()


def sc_get_scaledb_id(db = PSQL_DB):
    scaledb_id = ''

    try:
        for scale_id in sc_execute("SELECT enum_range(null::sc_scaledb_id);",db):
            scaledb_id = scale_id[0][1:-1]
    except:
        pass
    else:
        scaledb_id = scaledb_id.replace('"', '')

        if len(scaledb_id) > 0:
            scaledb_id = scaledb_id.replace('-', '_')

    return scaledb_id


def sc_create_scaledb_id(db = PSQL_DB):
    scaledb_id = ''

    for cursor in sc_execute("SELECT * FROM gen_random_uuid();",db):
        scaledb_id = cursor[0]

    sql_str = """
        DROP TYPE IF EXISTS public.sc_scaledb_id;

        CREATE TYPE public.sc_scaledb_id AS ENUM
            ('%(scaledb_id)s');
    """%{'scaledb_id': scaledb_id}

    sc_execute(sql_str, db)

def sc_get_scaledb_type(db = PSQL_DB):
    scaledb_type = ''

    try:
        for scale_type in sc_execute("SELECT enum_range(null::sc_scaledb_type);",db):
            scaledb_type = scale_type[0][1:-1]
    except:
        pass
    else:
        scaledb_type = scaledb_type.replace('"', '')

        if scaledb_type not in SCALEDB_TYPES:
            scaledb_type = ''

    return scaledb_type

def sc_create_scaledb_type(scaledb_type,db = PSQL_DB):
    if scaledb_type not in SCALEDB_TYPES:
        raise Exception('Невідомий тип бази даних')

    sql_str = """
        DROP TYPE IF EXISTS public.sc_scaledb_type;

        CREATE TYPE public.sc_scaledb_type AS ENUM
            ('%(scaledb_type)s');
    """%{'scaledb_type': scaledb_type}

    sc_execute(sql_str, db)

def sc_drop_tables(db = PSQL_DB):
    scaledb_type = sc_get_scaledb_type(db)

    if scaledb_type == 'server':
        sql_str = """
            DROP TRIGGER IF EXISTS sc_photos_move_row ON public.sc_photos_registrator;
            DROP TRIGGER IF EXISTS sc_calculations_move_row ON public.sc_calculations_registrator;

            DROP FUNCTION IF EXISTS public.sc_photos_move_row();
            DROP FUNCTION IF EXISTS public.sc_calculations_move_row();
            
            DROP TABLE IF EXISTS public.sc_photos_server;
            DROP TABLE IF EXISTS public.sc_calculations_server;
        """

        sc_execute(sql_str, db)

    sql_str = """
        DROP TRIGGER IF EXISTS sc_set_id ON public.sc_scales;

        DROP FUNCTION IF EXISTS public.sc_set_id();

        DROP TABLE IF EXISTS public.sc_photos_registrator;
        DROP TABLE IF EXISTS public.sc_calculations_registrator;
        DROP TABLE IF EXISTS public.sc_cameras;
        DROP TABLE IF EXISTS public.sc_connections;
        DROP TABLE IF EXISTS public.sc_scale_indications;
        DROP TABLE IF EXISTS public.sc_scales;

        DROP TYPE IF EXISTS public.sc_indications;
        DROP TYPE IF EXISTS public.sc_models;
        DROP TYPE IF EXISTS public.sc_operations;
    """

    sc_execute(sql_str,db)

def sc_create_tables(scaledb_type, db = PSQL_DB):
    sc_drop_tables(db)

    sc_create_scaledb_type(scaledb_type,db)

    sc_create_scaledb_id(db)

    sql_str = """
        CREATE TYPE public.sc_indications AS ENUM
            ('net', 'tare', 'gross', 'uneven_load', 'center_displacement', 'vizok1', 'vizok2');

        CREATE TYPE public.sc_models AS ENUM
            ('XK3118T1', 'A9', 'TVP', 'C8', 'CAS1560A', 'D2008f (KU08)');

        CREATE TYPE public.sc_operations AS ENUM
            ('up', 'down');

        CREATE OR REPLACE FUNCTION public.sc_set_id()
            RETURNS trigger
            LANGUAGE 'plpgsql'
            COST 100
            VOLATILE NOT LEAKPROOF
        AS $BODY$
        BEGIN
	        IF NEW.id IS NULL THEN
		        NEW.id := gen_random_uuid();
	        END IF;
	
	        RETURN NEW;
        END;
        $BODY$;
            
        CREATE TABLE IF NOT EXISTS public.sc_scales
        (
            id uuid NOT NULL,
            name character varying(160) COLLATE pg_catalog."default" NOT NULL,
            last_seen timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
            basic_indication sc_indications NOT NULL DEFAULT 'net', 
            basic_value integer NOT NULL DEFAULT 0 ,
            operation sc_operations,
            model sc_models NOT NULL,
            CONSTRAINT sc_devices_pkey PRIMARY KEY (id)
        )

        TABLESPACE pg_default;
        
        CREATE OR REPLACE TRIGGER sc_set_id
            BEFORE INSERT
            ON public.sc_scales
            FOR EACH ROW
            EXECUTE FUNCTION public.sc_set_id();
            
        CREATE TABLE IF NOT EXISTS public.sc_scale_indications
        (
            scale uuid NOT NULL,
            indication sc_indications NOT NULL,
            value integer NOT NULL DEFAULT 0,
            value_timestamp timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
            stab_value integer NOT NULL DEFAULT 0,
            stab_timestamp timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT sc_scale_indications_pkey PRIMARY KEY (scale, indication),
            CONSTRAINT sc_scale_indications_scale_fkey FOREIGN KEY (scale)
                REFERENCES public.sc_scales (id) MATCH FULL
                ON UPDATE NO ACTION
                ON DELETE CASCADE
        )

        TABLESPACE pg_default;

        CREATE TABLE IF NOT EXISTS public.sc_connections
        (
            scale uuid NOT NULL,
            port character varying(30) COLLATE pg_catalog."default" NOT NULL,
            baudrate integer NOT NULL DEFAULT 9600,
            sleep_timeout real NOT NULL DEFAULT 0.45,
            command_timeout real NOT NULL DEFAULT 1,
            CONSTRAINT sc_connections_pkey PRIMARY KEY (scale),
            CONSTRAINT sc_connections_scale_fkey FOREIGN KEY (scale)
                REFERENCES public.sc_scales (id) MATCH FULL
                ON UPDATE NO ACTION
                ON DELETE CASCADE
        )

        TABLESPACE pg_default;

        CREATE TABLE IF NOT EXISTS public.sc_calculations_registrator
        (
            scale uuid NOT NULL,
            begin_timestamp timestamp with time zone NOT NULL,
            end_timestamp timestamp with time zone NOT NULL,
            indication sc_indications NOT NULL,
            delta integer NOT NULL,
            rest integer NOT NULL,
            operation sc_operations,
            CONSTRAINT sc_calculations_registrator_pkey PRIMARY KEY (scale, end_timestamp, indication),
            CONSTRAINT sc_calculations_registrator_scale_fkey FOREIGN KEY (scale)
                REFERENCES public.sc_scales (id) MATCH FULL
                ON UPDATE NO ACTION
                ON DELETE CASCADE,
            CONSTRAINT sc_calculations_registrator_delta_check CHECK (delta <> 0) NOT VALID
        )

        TABLESPACE pg_default;

        CREATE TABLE IF NOT EXISTS public.sc_cameras
        (  
            scale uuid NOT NULL,
            ip inet NOT NULL,
            "user" character varying(80) COLLATE pg_catalog."default" NOT NULL,
            password character varying(80) COLLATE pg_catalog."default" NOT NULL,
            read_timeout real NOT NULL DEFAULT 1,
            CONSTRAINT sc_cameras_pkey PRIMARY KEY (scale, ip),
            CONSTRAINT sc_cameras_scale_fkey FOREIGN KEY (scale)
                REFERENCES public.sc_scales (id) MATCH FULL
                ON UPDATE NO ACTION
                ON DELETE CASCADE
                NOT VALID
        )
        
        TABLESPACE pg_default;

        CREATE TABLE IF NOT EXISTS public.sc_photos_registrator
        (
            scale uuid NOT NULL,
            ip inet NOT NULL,
            photo_timestamp timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
            data bytea NOT NULL,
            CONSTRAINT sc_photos_registrator_pkey PRIMARY KEY (scale, ip, photo_timestamp),
            CONSTRAINT sc_photos_registrator_scale_fkey FOREIGN KEY (scale)
                REFERENCES public.sc_scales (id) MATCH FULL
                ON UPDATE NO ACTION
                ON DELETE CASCADE
        )
        
        TABLESPACE pg_default;
    """

    sc_execute(sql_str, db)

    if scaledb_type == 'server':
        sql_str = """
                CREATE TABLE IF NOT EXISTS public.sc_calculations_server
                (
                    scale uuid NOT NULL,
                    begin_timestamp timestamp with time zone NOT NULL,
                    end_timestamp timestamp with time zone NOT NULL,
                    indication sc_indications NOT NULL,
                    delta integer NOT NULL,
                    rest integer NOT NULL,
                    operation sc_operations,
                    CONSTRAINT sc_calculations_server_pkey PRIMARY KEY (scale, end_timestamp, indication),
                    CONSTRAINT sc_calculations_server_scale_fkey FOREIGN KEY (scale)
                        REFERENCES public.sc_scales (id) MATCH FULL
                        ON UPDATE NO ACTION
                        ON DELETE CASCADE,
                    CONSTRAINT sc_calculations_server_delta_check CHECK (delta <> 0) NOT VALID
                )

                TABLESPACE pg_default;

                CREATE TABLE IF NOT EXISTS public.sc_photos_server
                (
                    scale uuid NOT NULL,
                    ip inet NOT NULL,
                    photo_timestamp timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    data bytea NOT NULL,
                    CONSTRAINT sc_photos_server_pkey PRIMARY KEY (scale, ip, photo_timestamp),
                    CONSTRAINT sc_photos_server_scale_fkey FOREIGN KEY (scale)
                        REFERENCES public.sc_scales (id) MATCH FULL
                        ON UPDATE NO ACTION
                        ON DELETE CASCADE
                )

                TABLESPACE pg_default;

                CREATE OR REPLACE FUNCTION public.sc_calculations_move_row()
                    RETURNS trigger
                    LANGUAGE 'plpgsql'
                    COST 100
                    VOLATILE NOT LEAKPROOF
                AS $BODY$
                    BEGIN
                        INSERT INTO public.sc_calculations_server SELECT NEW.*;
  
                        DELETE FROM public.sc_calculations_registrator WHERE (scale=NEW.scale) AND (indication=NEW.indication) AND (end_timestamp=NEW.end_timestamp);
                
                        RETURN NULL;
                    END;
                $BODY$;

                CREATE OR REPLACE TRIGGER sc_calculations_move_row
                    AFTER INSERT
                    ON public.sc_calculations_registrator
                    FOR EACH ROW
                    EXECUTE FUNCTION public.sc_calculations_move_row();

                CREATE OR REPLACE FUNCTION public.sc_photos_move_row()
                    RETURNS trigger
                    LANGUAGE 'plpgsql'
                    COST 100
                    VOLATILE NOT LEAKPROOF
                AS $BODY$
                    BEGIN
                        INSERT INTO public.sc_photos_server SELECT NEW.*;
  
                        DELETE FROM public.sc_photos_registrator WHERE (scale=NEW.scale) AND (ip=NEW.ip) AND (photo_timestamp=NEW.photo_timestamp);
                
                        RETURN NULL;
                    END;
                $BODY$;

                CREATE OR REPLACE TRIGGER sc_photos_move_row
                    AFTER INSERT
                    ON public.sc_photos_registrator
                    FOR EACH ROW
                    EXECUTE FUNCTION public.sc_photos_move_row();
                
                ALTER TABLE public.sc_calculations_registrator ENABLE ALWAYS TRIGGER sc_calculations_move_row;
                
                ALTER TABLE public.sc_photos_registrator ENABLE ALWAYS TRIGGER sc_photos_move_row;
        """

        sc_execute(sql_str, db)


def sc_delete_publication(publication_name, db = PSQL_DB):
    sql_str = f"""
        DROP PUBLICATION IF EXISTS {publication_name};
    """

    sc_execute(sql_str, db)


def sc_create_publication(publication_name, table_name,actions,db = PSQL_DB):
    sql_str = f"""
        CREATE PUBLICATION {publication_name} FOR TABLE {table_name} WITH (publish = '{actions}');
    """

    sc_execute(sql_str, db)


def sc_delete_publications(variant, db = PSQL_DB):
    scaledb_type = sc_get_scaledb_type(db)

    if scaledb_type == 'registrator':
        if variant in ('all','status'):
            sc_delete_publication('sc_status', db)

        if variant in ('all', 'calculations'):
            sc_delete_publication('sc_calculations', db)

        if variant in ('all', 'photos'):
            sc_delete_publication('sc_photos', db)
    elif scaledb_type == 'server':
        if variant in ('all', 'calculations'):
            sc_delete_publication('sc_calculations_delete', db)

        if variant in ('all', 'photos'):
            sc_delete_publication('sc_photos_delete', db)


def sc_create_publications(variant, db = PSQL_DB):
    scaledb_type = sc_get_scaledb_type(db)

    if scaledb_type == 'registrator':
        if variant in ('all','status'):
            sc_create_publication('sc_status','sc_scales,sc_scale_indications', 'insert,update', db)

        if variant in ('all', 'calculations'):
            sc_create_publication('sc_calculations',"sc_calculations_registrator",'insert', db)

        if variant in ('all', 'photos'):
            sc_create_publication('sc_photos',"sc_photos_registrator", 'insert',db)
    elif scaledb_type == 'server':
        if variant in ('all', 'calculations'):
            sc_create_publication('sc_calculations_delete', "sc_calculations_registrator", 'delete', db)

        if variant in ('all', 'photos'):
            sc_create_publication('sc_photos_delete', "sc_photos_registrator", 'delete', db)


def sc_delete_subscription(subscription_name, db = PSQL_DB):
    sql_str = f"""
        DROP SUBSCRIPTION IF EXISTS {subscription_name};
    """

    sc_execute(sql_str, db)


def sc_create_subscription(subscription_name, publication_name, host, port, dbname, user, password, db = PSQL_DB):
    con_str = f"host={host} port={port} user={user} password={password} dbname={dbname}"

    sql_str = f"""
        CREATE SUBSCRIPTION {subscription_name} CONNECTION '{con_str}' PUBLICATION {publication_name} WITH (copy_data = true, origin = any);
    """

    sc_execute(sql_str, db)

def sc_delete_subscriptions(variant, host='', db = PSQL_DB):
    scaledb_type = sc_get_scaledb_type(db)

    if scaledb_type == 'registrator':
        scaledb_id = sc_get_scaledb_id(db)
        if variant in ('all', 'calculations'):
            sc_delete_subscription(f"sc_calculations_delete_{scaledb_id}", db)

        if variant in ('all', 'photos'):
            sc_delete_subscription(f"sc_photos_delete_{scaledb_id}", db)
    elif scaledb_type == 'server':
        host_name = host.replace('.','_')

        if variant in ('all', 'satus'):
            sc_delete_subscription(f"sc_status_{host_name}", db)

        if variant in ('all', 'calculations'):
            sc_delete_subscription(f"sc_calculations_{host_name}", db)

        if variant in ('all', 'photos'):
            sc_delete_subscription(f"sc_photos_{host_name}", db)


def sc_create_subscriptions(variant,host,port,dbname,user,password, db = PSQL_DB):
    scaledb_type = sc_get_scaledb_type(db)

    if scaledb_type == 'registrator':
        scaledb_id = sc_get_scaledb_id(db)

        if variant in ('all', 'calculations'):
            sc_create_subscription(f"sc_calculations_delete_{scaledb_id}", "sc_calculations_delete", host, port, dbname, user, password, db)

        if variant in ('all', 'photos'):
            sc_create_subscription(f"sc_photos_delete_{scaledb_id}","sc_photos_delete", host, port, dbname, user, password, db)
    elif scaledb_type == 'server':
        host_name = host.replace('.','_')

        if variant in ('all', 'satus'):
            sc_create_subscription(f"sc_status_{host_name}", 'sc_status', host, port, dbname, user, password, db)

        if variant in ('all', 'calculations'):
            sc_create_subscription(f"sc_calculations_{host_name}", 'sc_calculations',host, port, dbname, user, password, db)

        if variant in ('all', 'photos'):
            sc_create_subscription(f"sc_photos_{host_name}", 'sc_photos',host, port, dbname, user, password, db)


def sc_init_tables(db = PSQL_DB):
    scaledb_type = sc_get_scaledb_type(db)

    ScCalculations._meta.set_table_name(f"sc_calculations_{scaledb_type}")

    ScPhotos._meta.set_table_name(f"sc_photos_{scaledb_type}")


class BaseModel(Model):
    class Meta:
        database = PSQL_DB
        legacy_table_names = False
        only_save_dirty = True


class ScScales(BaseModel):
    id = UUIDField(primary_key=True)
    name = CharField()
    basic_indication = CharField()
    basic_value = IntegerField()
    last_seen = DateTimeTZField()
    operation = CharField()
    model = CharField()


class ScScaleIndications(BaseModel):
    scale = ForeignKeyField(ScScales, backref='indications', column_name='scale')
    indication = CharField()
    value = IntegerField()
    value_timestamp = DateTimeTZField()
    stab_value = IntegerField()
    stab_timestamp = DateTimeTZField()

    class Meta:
        primary_key = CompositeKey('scale', 'indication')


class ScConnections(BaseModel):
    scale = ForeignKeyField(ScScales, backref='connections', column_name='scale')
    port = CharField()
    baudrate = IntegerField()
    sleep_timeout = FloatField()
    command_timeout = FloatField()

    class Meta:
        primary_key = CompositeKey('scale', 'port')


class ScCalculations(BaseModel):
    scale = ForeignKeyField(ScScales, backref='calculations', column_name='scale')
    begin_timestamp = DateTimeTZField()
    end_timestamp = DateTimeTZField()
    indication = CharField()
    delta = IntegerField()
    rest = IntegerField()
    operation = CharField()

    class Meta:
        primary_key = CompositeKey('scale', 'end_timestamp', 'indication')


class ScCameras(BaseModel):
    connection = ForeignKeyField(ScConnections, backref='cameras', column_name='connection')
    ip = CharField()
    user = CharField()
    password = CharField()
    read_timeout = FloatField()

    class Meta:
        primary_key = CompositeKey('connection', 'ip')


class ScPhotos(BaseModel):
    scale = ForeignKeyField(ScScales, backref='photos', column_name='scale')
    ip = CharField()
    photo_timestamp = DateTimeTZField()
    data = BlobField()

    class Meta:
        primary_key = CompositeKey('scale', 'ip', 'photo_timestamp')