// Fixed reachability check, not a query runner or an environment/role verifier.
// Execute through mongosh --nodb --norc --quiet --file; capture BOTH output streams
// in private local files. Do not expose a URI, profile, documents or raw errors.
(() => {
  let succeeded = false;
  try {
    disableTelemetry();
    const fs = require('fs');
    const {URLSearchParams} = require('url');
    const profilePath = process.env.DB_PROFILE_FILE;
    const requestedEnvironment = process.env.DB_TARGET_ENV;
    if (!profilePath || !['local', 'dev', 'staging', 'prod'].includes(requestedEnvironment)) {
      throw new Error('Required explicit profile and environment missing');
    }
    const stat = fs.lstatSync(profilePath);
    if (!stat.isFile() || stat.isSymbolicLink() || (stat.mode & 0o077) !== 0 || stat.uid !== process.getuid()) {
      throw new Error('Profile must be an owner-only regular file');
    }
    const profile = JSON.parse(fs.readFileSync(profilePath, 'utf8'));
    if (profile.configured !== true || profile.environment !== requestedEnvironment ||
        typeof profile.database !== 'string' || !profile.database.trim() ||
        typeof profile.connection_uri !== 'string' || !/^mongodb(?:\+srv)?:\/\//.test(profile.connection_uri)) {
      throw new Error('Profile is not configured for requested environment');
    }
    // Require explicit verified TLS for this example, including local databases.
    // The owner must also review CA/hostname/timeout settings and server role grants.
    const query = new URLSearchParams(profile.connection_uri.split('?')[1] || '');
    const options = new Map();
    for (const [rawKey, value] of query.entries()) {
      const key = rawKey.toLowerCase();
      if (options.has(key)) throw new Error('Ambiguous duplicate URI option');
      options.set(key, value.toLowerCase());
    }
    if (options.get('tls') !== 'true' || [...options.keys()].some(key =>
      key.startsWith('tlsallow') || key === 'tlsinsecure' || key === 'ssl')) {
      throw new Error('Verified explicit TLS required');
    }
    const connection = new Mongo(profile.connection_uri);
    const response = connection.getDB(profile.database).runCommand({ping: 1});
    if (response.ok !== 1) throw new Error('Ping failed');
    succeeded = true;
  } catch (_) {
    // Never print the exception: a client/parser error may contain a secret URI.
    succeeded = false;
  }
  print(succeeded ? 'Database reachability check succeeded.' :
    'Database reachability check failed; review configuration privately.');
  quit(succeeded ? 0 : 1);
})();
