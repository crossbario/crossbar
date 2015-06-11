DROP FUNCTION IF EXISTS crossbar.call (TEXT, JSONB, JSONB, JSONB, TEXT);

CREATE OR REPLACE FUNCTION call (
    p_proc      TEXT,
    p_args      JSONB DEFAULT NULL,
    p_kwargs    JSONB DEFAULT NULL,
    p_options   JSONB DEFAULT NULL,
    p_server    TEXT DEFAULT current_setting('crossbar.router_url')
)
RETURNS JSONB
LANGUAGE plpythonu
VOLATILE
AS
$$
return None
$$;
