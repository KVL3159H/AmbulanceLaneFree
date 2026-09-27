# Contributing to LifeLane

Thanks for helping improve LifeLane. This project combines a Windows/PySide6 desktop app, a Raspberry Pi runtime, Android/Kotlin code, MQTT communication, simulation logic, and tests.

## Before you start

1. Read the main `README.md` and the relevant file under `docs/`.
2. Search existing issues and pull requests before opening a duplicate.
3. Keep changes focused. One pull request should solve one clear problem.
4. Do not commit credentials, private IP addresses, signing keys, APK secrets, or `.env` files.

## Development setup

### Python / desktop / Raspberry Pi

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
```

Windows:

```cmd
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Linux / Raspberry Pi:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run tests:

```bash
python -m pytest -q
```

### Android

Use JDK 17 and Android SDK 36.

```bash
cd android_app
./gradlew assembleDebug
```

On Windows, use `gradlew.bat assembleDebug`.

## Branch naming

Use short descriptive names, for example:

- `fix/gps-stale-packet-check`
- `feat/ambulance-priority-queue`
- `docs/pi-installation-guide`
- `test/mqtt-validation-cases`

## Commit messages

Prefer clear, imperative messages:

- `fix: reject stale telemetry packets`
- `feat: add ambulance queue aging`
- `docs: clarify Raspberry Pi setup`
- `test: cover fail-safe transition`

## Pull request checklist

Before opening a PR:

- [ ] The change has a clear purpose.
- [ ] Existing tests pass.
- [ ] New behavior has tests where practical.
- [ ] Documentation is updated when behavior changes.
- [ ] No secrets or generated build artifacts are included.
- [ ] Safety-sensitive logic keeps fail-safe behavior intact.
- [ ] Android, desktop, and Raspberry Pi impacts have been considered.

## Safety-sensitive changes

Traffic-control and emergency-preemption logic is safety-sensitive. For changes touching signal states, transition timing, GPIO, authorization, telemetry validation, or preemption logic:

1. Describe the failure mode being addressed.
2. Add or update tests for invalid and boundary inputs.
3. Preserve all-red/fail-safe behavior.
4. Do not present simulator timing values as approved road timings.
5. Clearly separate demo/simulation behavior from real-world deployment claims.

## Reporting bugs

Include:

- operating system/device
- Python or Android version
- exact steps to reproduce
- expected result
- actual result
- relevant log output
- screenshots only when they help explain the issue

Do not include passwords, tokens, private keys, or other secrets in bug reports.

## Feature proposals

A useful feature request should explain:

- the real problem
- who is affected
- the proposed behavior
- any safety or security implications
- how the feature could be tested

## Code review

Reviewers should focus on correctness, safety, regressions, readability, tests, and documentation. Suggestions should be specific and actionable.

By contributing, you agree that your contribution may be distributed under the repository's applicable license.
