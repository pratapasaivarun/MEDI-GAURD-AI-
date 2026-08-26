# Medi Gaurd AI Security Operations

## Private storage

Set `MEDIGUARD_STORAGE_DIR` to a directory outside the project’s public/static directories. Keep the SQLite database, uploaded documents, policy source files, ChromaDB files, and backup staging files under protected storage.

On Windows, run the following from an elevated PowerShell session after replacing the path and service account with the actual application account. Review the resulting ACL before using real documents.

```powershell
$Storage = 'C:\MediGaurdPrivate'
$Account = "$env:USERDOMAIN\$env:USERNAME"
New-Item -ItemType Directory -Force $Storage | Out-Null
icacls $Storage /inheritance:r
icacls $Storage /grant:r "$Account:(OI)(CI)F" 'SYSTEM:(OI)(CI)F' 'Administrators:(OI)(CI)F'
icacls $Storage /remove 'Users' 'Authenticated Users' 'Everyone'
```

Do not put the storage directory under a web server, `static`, `public`, or a directory served by Streamlit components. The application rejects storage roots that resolve to the project root or contain a `public` or `static` path component.

## Encrypted database backup

Configure `MEDIGUARD_BACKUP_KEY` through the operating-system environment or a deployment secret store. It must be at least 32 characters and must not be committed to the repository.

The administrator-only `create_encrypted_backup()` function uses SQLite’s backup API and Fernet authenticated encryption. The application writes only the encrypted `.enc` artifact. The raw temporary SQLite file is deleted after encryption. `restore_encrypted_backup()` verifies the authentication tag and rejects a wrong key.

Example controlled backup invocation:

```powershell
$env:MEDIGUARD_BACKUP_KEY = '<secret from the protected secret store>'
.\.venv\Scripts\python.exe -c "import app; a=app.get_user('<admin-user-id>'); print(app.create_encrypted_backup(a, 'C:\\MediGaurdBackups\\mediguard.sqlite.enc'))"
```

Do not print the backup key, password, invitation token, or document content in command history or logs. Prefer a scheduled process that reads the key from a secret manager rather than placing it permanently in a shell profile.

## Restore test

Restore to a separate, non-production path first. Confirm that the restored file opens, contains the expected schema, and can be queried. Never overwrite the live database during a restore test. Record the backup identifier, restore timestamp, operator, and result in the operational log without recording claim contents.

## Retention and deletion

The administrator-only `purge_expired_documents()` function requires an explicit retention period and deletes the physical document and its database record. Deletion is audited. Before enabling automated retention, the product owner must approve the retention period and legal hold behavior.

Retention must eventually cover policy source files, ChromaDB records, generated reports, and backup copies, not only uploaded bill files. A legal hold must prevent deletion of a claim under active review or appeal.

## Logging rules

Logs and audit events must not contain passwords, raw setup tokens, backup keys, full OCR text, full policy documents, or raw document contents. Store identifiers, event types, timestamps, and short safe metadata only.

## Current limitations

The current local prototype does not provide OS-level encryption by itself, malware scanning, managed secret storage, automatic backup scheduling, or a formal legal-retention engine. These controls require deployment and operational decisions before real patient data is used.
