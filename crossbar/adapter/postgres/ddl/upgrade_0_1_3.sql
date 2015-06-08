DROP TABLE IF EXISTS crossbar.registration;

CREATE TABLE crossbar.registration
(
    id              BIGSERIAL PRIMARY KEY,
    uri             TEXT NOT NULL,
    proc            TEXT NOT NULL,
    signature       TEXT,
    proc_oid        INT NOT NULL,
    options         JSONB,
    registered_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    unregistered_at TIMESTAMP WITH TIME ZONE
);

CREATE UNIQUE INDEX idx_registration_procedure
    ON crossbar.registration (uri)
        WHERE unregistered_at IS NULL
;

DROP FUNCTION IF EXISTS crossbar.register (TEXT, TEXT, TEXT, JSONB);

CREATE OR REPLACE FUNCTION crossbar.register (
    uri         TEXT,
    proc        TEXT,
    signature   TEXT        DEFAULT NULL,
    options     JSONB       DEFAULT NULL
) RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
AS
$$
DECLARE
    l_proc              TEXT;
    l_registration_id   BIGINT;
    l_full_sig          TEXT;
    l_proc_oid          INT;
    l_return_type       TEXT;
    l_payload   TEXT;
 BEGIN
    IF signature IS NOT NULL THEN
        RAISE EXCEPTION 'using arbitrary procedure signatures is not yet supported - expecting (jsonb, jsonb, jsonb)';
    END IF;

    l_full_sig := TRIM(LOWER(proc)) || ' (jsonb, jsonb, jsonb)';

    BEGIN
        SELECT l_full_sig::regprocedure::oid INTO l_proc_oid;
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'no function "%" exists', l_full_sig;
    END;

    SELECT pg_get_function_result(l_proc_oid) INTO l_return_type;

    IF l_return_type != 'jsonb' THEN
        RAISE EXCEPTION 'currently only JSONB as return type is supported';
    END IF;

    SELECT r.proc INTO l_proc FROM crossbar.registration AS r
        WHERE proc_oid = l_proc_oid AND unregistered_at IS NULL;

    IF l_proc IS NOT NULL THEN
        RAISE EXCEPTION 'procedure "%" already registered under URI "%"', l_full_sig, l_proc;
    END IF;

    INSERT INTO crossbar.registration (uri, proc, signature, proc_oid, options)
        VALUES (uri, proc, signature, l_proc_oid, options)
            RETURNING id INTO l_registration_id
    ;

    l_payload := json_build_object(
        'type', 'register',
        'uri', uri,
        'proc', proc,
        'signature', signature,
        'proc_oid', l_proc_oid,
        'registration_id', l_registration_id,
        'options', options
    )::text;

    PERFORM pg_notify('crossbar_register', l_payload);

    RETURN l_registration_id;
END
$$;

COMMENT ON FUNCTION crossbar.register (TEXT, TEXT, TEXT, JSONB) IS
'Register a function.
'
;

GRANT EXECUTE ON FUNCTION crossbar.register
    (TEXT, TEXT, TEXT, JSONB)
        TO PUBLIC
;

-- SELECT crossbar.register('io.crossbar.cdc.database.account.create_user', 'account.create_user');

-- SELECT * FROM crossbar.registration;
