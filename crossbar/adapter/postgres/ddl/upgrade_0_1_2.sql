DROP FUNCTION IF EXISTS crossbar.publish (TEXT, JSONB, JSONB, JSONB);

CREATE OR REPLACE FUNCTION crossbar.publish (
    topic       TEXT,
    args        JSONB       DEFAULT NULL,
    kwargs      JSONB       DEFAULT NULL,
    options     JSONB       DEFAULT NULL
) RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
AS
$$
DECLARE
    l_event_id  BIGINT := NULL;
    l_payload   TEXT;
BEGIN
    l_payload := json_build_object(
        'type', 'inline',
        'topic', topic,
        'args', args,
        'kwargs', kwargs
    )::text;

    IF LENGTH(l_payload) > 4000 OR (options->>'acknowledge')::boolean IS NOT NULL THEN

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

COMMENT ON FUNCTION crossbar.publish (TEXT, JSONB, JSONB, JSONB) IS
'Publish an event on the given topic.

An event can have positional payload (args) and keyword-based payload (kwargs).
Using options allows to take finer control over publishing, like request
acknowledgement or black- or whitelist receivers.
'
;

GRANT EXECUTE ON FUNCTION crossbar.publish
    (TEXT, JSONB, JSONB, JSONB)
        TO PUBLIC
;
