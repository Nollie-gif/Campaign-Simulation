# Storage Contract

At first boot, the runtime offers two modes:

- `repository`: canonical records are read from the campaign data repository.
- `supabase`: canonical records remain in the campaign data repository; the connected knowledge layer may be used as a read accelerator.

The selection is persisted locally in an ignored runtime configuration file. It is requested only when that configuration does not exist. A provider adapter supplies the external connection probe. If that probe reports the connection unavailable or invalid, the runtime continues in repository mode and records the fallback reason locally.

Credentials, connection strings, and populated runtime data must never be committed.
