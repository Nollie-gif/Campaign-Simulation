# Storage Contract

At first boot, the runtime offers two modes:

- `repository`: canonical records are read from the campaign data repository.
- `supabase`: canonical records remain in the campaign data repository; the connected knowledge layer may be used as a read accelerator.

The selection is persisted locally in an ignored runtime configuration file. It is requested only when that configuration does not exist.

For Supabase mode, the configuration stores only:

- the HTTPS Supabase project URL;
- the name of an environment variable containing the API key; and
- an optional schema name.

It never stores an API key, access token, password, or connection string. At first
selection and on subsequent boots, the runtime checks that the URL is valid, that
the named environment variable exists, and that a low-impact Supabase settings
request succeeds. If any check fails, the runtime persists repository mode and
records the fallback reason locally. The simulation continues; Supabase is never a
single point of failure.

Credentials, connection strings, and populated runtime data must never be committed.
