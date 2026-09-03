# OWASP Security Basics

## Injection (SQL, Command, etc.)
Never build queries or shell commands by concatenating or
f-string-formatting untrusted input directly. Use parameterized
queries (e.g. with placeholders) for databases, and avoid passing
user input directly to `os.system`, `subprocess` with `shell=True`,
or `eval`/`exec`.

## Broken Authentication
Do not store passwords in plaintext. Use a strong, salted hashing
algorithm (e.g. bcrypt, argon2). Avoid hardcoding credentials or
secrets directly in source code.

## Sensitive Data Exposure
Never log or return sensitive data (API keys, passwords, tokens,
personal data) in responses or error messages. Use environment
variables or a secrets manager for credentials, never hardcode them.

## Security Misconfiguration
Avoid running services with debug mode enabled in production, using
overly permissive CORS policies (e.g. allowing all origins with
credentials), or leaving default/example credentials in place.

## Insecure Deserialization
Avoid using `pickle`, `eval`, or `exec` on data from untrusted
sources, as this can lead to arbitrary code execution. Prefer safe
formats like JSON, and validate/parse untrusted input strictly.

## Insufficient Input Validation
Always validate and sanitize external input (user-provided strings,
file uploads, API payloads) before using it in file paths, queries,
commands, or rendering it back to users (to prevent XSS).

## Using Components with Known Vulnerabilities
Keep dependencies up to date and avoid pinning to old, unmaintained
package versions with known CVEs.