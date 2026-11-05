-- Reachability only: this does not verify deployment identity, privileges or schema.
BEGIN READ ONLY;
SET LOCAL statement_timeout = '5s';
SET LOCAL lock_timeout = '1s';
SELECT 1;
ROLLBACK;
