DROP FUNCTION IF EXISTS crossbar.publish (TEXT, JSONB, JSONB, JSONB, BOOLEAN);

CREATE OR REPLACE FUNCTION crossbar.publish (
    topic       TEXT,
    args        JSONB       DEFAULT NULL,
    kwargs      JSONB       DEFAULT NULL,
    options     JSONB       DEFAULT NULL,
    autonomous  BOOLEAN     DEFAULT FALSE
) RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
VOLATILE
AS
$$
DECLARE
    l_event_id  BIGINT := NULL;
    l_payload   TEXT;
    l_buffered  BOOLEAN := FALSE;
    l_rec       RECORD;
BEGIN
    -- check/sanitize arguments
    --
    IF topic LIKE 'wamp.%' OR topic LIKE 'crossbar.%' OR topic LIKE 'io.crossbar.%' THEN
        RAISE EXCEPTION 'use of restricted topic "%"',topic;
    END IF;

    IF args IS NOT NULL AND jsonb_typeof(args) != 'array' THEN
        RAISE EXCEPTION 'args must be a jsonb array, was %', jsonb_typeof(args);
    END IF;

    IF kwargs IS NOT NULL AND jsonb_typeof(kwargs) != 'object' THEN
        RAISE EXCEPTION 'kwargs must be a jsonb object, was %', jsonb_typeof(kwargs);
    END IF;

    IF options IS NOT NULL THEN
        IF jsonb_typeof(options) != 'object' THEN
            RAISE EXCEPTION 'options must be a jsonb object, was %', jsonb_typeof(options);
        END IF;
        FOR l_rec IN (SELECT jsonb_object_keys(options) AS key)
        LOOP
            IF NOT l_rec.key = ANY('{exclude,eligible,acknowledge}'::text[]) THEN
                RAISE EXCEPTION 'illegal attribute "%" in "options"', l_rec.key;
            END IF;
        END LOOP;
    END IF;

    IF autonomous = TRUE THEN
        RAISE EXCEPTION 'publishing in an automonmous transaction not yet supported';
    END IF;

    l_payload := json_build_object(
        'type', 'inline',
        'topic', topic,
        'args', args,
        'kwargs', kwargs,
        'options', options,
        'details', json_build_object(
            'session_user', session_user,
            'pg_backend_pid', pg_backend_pid(),
            'published_at', to_char(now() at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
        )
    )::text;

    -- maximum payload for NOTIFY is 8000 octets
    IF LENGTH(l_payload) >= 8000 THEN
        RAISE EXCEPTION 'serialized payload exceeds maximum 8000-1 bytes for unbuffered events (was %), and buffered events not yet supported', LENGTH(l_payload)::text;
        l_buffered := TRUE;
    END IF;

    IF (options->>'acknowledge')::boolean = TRUE THEN
        RAISE EXCEPTION 'acknowledged publications not yet supported';
        l_buffered := TRUE;
    END IF;

    IF l_buffered THEN

        INSERT INTO crossbar.event (payload)
            VALUES (l_payload) RETURNING id INTO l_event_id;

        l_payload := json_build_object(
            'type', 'buffered',
            'id', l_event_id
        )::text;
        PERFORM pg_notify('crossbar_publish', l_payload);
    ELSE
        PERFORM pg_notify('crossbar_publish', l_payload);
    END IF;

    RETURN l_event_id;
END
$$;

COMMENT ON FUNCTION crossbar.publish (TEXT, JSONB, JSONB, JSONB, BOOLEAN) IS
'Publish an event on the given topic.

An event can have positional payload (args) and keyword-based payload (kwargs).
Using options allows to take finer control over publishing, like request
acknowledgement or black- or whitelist receivers.
';

GRANT EXECUTE ON FUNCTION crossbar.publish
    (TEXT, JSONB, JSONB, JSONB, BOOLEAN)
        TO PUBLIC
;
