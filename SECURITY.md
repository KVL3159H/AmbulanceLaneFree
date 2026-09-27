# Security Policy

LifeLane / AmbulanceLaneFree is an engineering prototype that combines software, networking, location data, and traffic-control logic. Security issues can affect both data integrity and safety-related behaviour, so responsible disclosure is encouraged.

## Supported code

Security reports should target the current default branch and the latest documented application/firmware paths.

## Reporting a vulnerability

Please do **not** publish exploit details, credentials, private keys, personal location data, or unsafe traffic-control instructions in a public issue.

Instead, open a minimal GitHub issue that says a private security report is needed, without including the sensitive details. A maintainer can then coordinate an appropriate private channel.

Include, where possible:

- affected component or file;
- impact and realistic threat scenario;
- steps to reproduce at a high level;
- environment/device information;
- suggested mitigation;
- whether credentials or personal data may be exposed.

## Security-sensitive areas

Examples include:

- MQTT authentication/authorization;
- GPS or telemetry spoofing;
- stale/replayed emergency requests;
- unsafe traffic-signal state transitions;
- Raspberry Pi or ESP32 command validation;
- exposed API keys, tokens, or secrets;
- local/network privilege escalation;
- insecure update or deployment procedures;
- location/privacy leakage.

## Safety boundary

This repository is a prototype and is **not a certified road traffic controller**. Do not connect prototype outputs directly to real traffic infrastructure without independent engineering review, certified hardware, fail-safe controls, conflict monitoring, legal approval, and field validation.

## Secrets

Never commit passwords, API keys, tokens, certificates, signing keys, private IP credentials, or production `.env` files. If a secret is accidentally committed, revoke/rotate it immediately; deleting the file alone is not sufficient.

## Disclosure

Please allow reasonable time for investigation and remediation before publishing sensitive technical details.
