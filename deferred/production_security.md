# Production-security backlog

All items in this document are out of scope for the local academic prototype.

- MFA and TOTP enrollment, encrypted MFA secrets, password reset, account invitations, role provisioning, and hardened authentication.
- Encryption-key lifecycle, encrypted database backups, restore controls, document retention/purging, and operational audit administration.
- HTTPS termination, secure deployment headers, monitoring/alerting, backup scheduling, and recovery drills.
- Secret-manager integration and production validation of credentials, signing keys, and deployment configuration.

The prototype intentionally runs locally with an anonymous demo identity. These controls should be redesigned and independently reviewed before any real-user or real-health-data deployment.
