# CETI Secrets and Recovery

This document defines where CETI secrets belong and how recovery information is organized. **No live secret values belong in this repository.**

## Roles

### HashiCorp Vault — runtime source of truth

HashiCorp Vault stores secrets that the CETI application/server needs at runtime. The validator currently reads its database connection information from Vault.

Current application secret path:

```text
ceti/data/ceti-validador
```

The application code should retrieve runtime credentials from Vault rather than hard-coding them or committing them to Git.

Examples of secrets that belong in Vault:

- MariaDB host/user/password used by the validator
- future application runtime secrets
- future service credentials that must be consumed automatically by the application

### 1Password — human recovery and administration

1Password is the human-accessible recovery store. A dedicated vault has been created:

```text
CETI Infrastructure
```

Confirmed recovery item:

```text
CETI Infrastructure
└── HashiCorp Vault Unseal Keys
```

The HashiCorp Vault unseal material was transferred directly from the Hetzner server to 1Password using SSH + the 1Password CLI. The secret values were not committed to Git or pasted into project documentation.

1Password should also be used for human recovery/administration information such as:

- HashiCorp Vault recovery/bootstrap material
- Coolify administration/API recovery credentials
- Google Drive/rclone OAuth recovery information when appropriate
- SSH keys and server access credentials
- GitHub/deployment recovery credentials when appropriate

The MacBook already uses the 1Password SSH agent for SSH access to the CETI Hetzner server.

### GitHub — documentation and code, never live secrets

GitHub contains:

- application source code
- architecture documentation
- secret names and expected locations
- recovery procedures
- operational commands that do not expose credentials
- configuration examples/placeholders

GitHub must **not** contain live secret values.

## Current recovery architecture

```text
                       +-------------------------+
                       |       1Password         |
                       |  CETI Infrastructure    |
                       |                         |
                       | human recovery material |
                       +------------+------------+
                                    |
                                    | recovery/admin
                                    v
+-------------+             +-------+--------+
|   GitHub    |             | HashiCorp Vault|
| code + docs |             | runtime secrets|
+------+------+             +-------+--------+
       |                            |
       | deploy                     | credentials
       v                            v
+------+----------------------------+------+
|       Coolify / CETI application        |
+-------------------+---------------------+
                    |
                    v
                 MariaDB
```

## Vault recovery

Server-side files/services currently involved in auto-unseal:

```text
/root/ceti-vault/unseal.sh
/root/ceti-vault/unseal-keys
/etc/systemd/system/ceti-vault-unseal.service
```

The server-local unseal key file is required by the current automatic unseal design. A recovery copy exists in 1Password under:

```text
Vault: CETI Infrastructure
Item:  HashiCorp Vault Unseal Keys
```

Do not put the contents of that item in GitHub.

Useful non-secret health check:

```bash
vault status
```

Expected after a successful boot/unseal:

```text
Initialized     true
Sealed          false
```

## 1Password CLI

The CETI administrator MacBook has the 1Password CLI (`op`) installed and the account is integrated with the 1Password desktop application.

Useful safe checks:

```bash
op --version
op vault list
op item get "HashiCorp Vault Unseal Keys" --vault "CETI Infrastructure" --format json
```

Do not print secret fields into shell history, logs, chat, or GitHub.

## rclone / Google Drive

The backup system uses the rclone remote:

```text
ceti-google-drive
```

and destination:

```text
CETI-Backups/Database/
```

The rclone configuration contains OAuth credentials/tokens and must not be committed. Determine its active location with:

```bash
rclone config file
```

See `docs/BACKUPS.md` for backup reconstruction and verification.

## Coolify

Coolify manages deployment of the CETI validator to the Hetzner server. API tokens are administrative credentials and must not be stored in GitHub.

If a Coolify API token is needed interactively, load it into a shell environment without committing it to a file in the repository. Store human recovery information in the `CETI Infrastructure` 1Password vault.

## Secret-handling rule

Use this decision rule for new credentials:

1. **Does the running application/server need it automatically?** Store it in HashiCorp Vault.
2. **Does a human administrator need it for recovery or administration?** Store it in 1Password `CETI Infrastructure`.
3. **Does the project need to know how/where it is configured?** Document the procedure and secret name in GitHub, but not the secret value.

Some credentials may have both a runtime representation in Vault and recovery/bootstrap information in 1Password. Vault remains the runtime source of truth; 1Password is the recovery/administration store.

## Never commit

Never commit any of these values to Git:

- Vault unseal/recovery keys
- Vault root tokens
- Vault AppRole Secret IDs or other authentication secrets
- MariaDB passwords
- Coolify API tokens
- rclone OAuth tokens
- Google OAuth client secrets
- SSH private keys
- 1Password credentials/tokens
- `.env` files containing live credentials

## Recovery documentation policy

Whenever a new CETI infrastructure component or credential is introduced, document:

- what the credential is for
- whether Vault or 1Password is its source of truth
- the non-secret path/item name where it is stored
- how to recreate/rotate it
- how to verify the component works afterward

Never document the live credential value itself.
