UPDATE crossbar.meta SET value = 1::text::jsonb
    WHERE key = 'schema_version'
;
