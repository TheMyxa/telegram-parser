# Reversible pseudonyms

[English README](../README.md) · [Русский](../README_ru.md) · [中文](../README_cn.md)

`--anonymize` uses `anonymization_rules.json`. Edit its adjective and noun
lists to generate names such as «Зелёный слон» or «Красивый шакал». Use words
with compatible grammatical forms. Once combinations are exhausted, a numeric
suffix is added. Existing names remain unchanged when dictionaries change.
`--anonymizer-file path` accepts alternate JSON rules or legacy text name lists;
both use the new persistent map, not the old in-memory identity assignment.

The supported field rules replace `user_id`, clear `username`/`last_name`, and
put the alias in `first_name`. Other user fields, post/comment text, links and
media are unchanged. This is reversible pseudonymization, not removal of all
personal information.

## Private map

Export, Watch and local conversion share `data/private/anonymization_map.json`.
The file is created only when a user is first anonymized. It contains original
Telegram IDs, names and usernames, together with assigned aliases. Do not
publish it. It is **plain JSON, not encrypted**. Keep it on protected storage and
back it up separately from distributable exports. On POSIX, new files are
created with owner-only access; Windows access follows the directory ACL.

The map is excluded from Git and Docker build context. Compose mounts `data`,
so the same private map survives container recreation. HTTP serves only
`data/raw`, `data/content` and `data/analysis`; private/state/scheduler files
are not downloadable. MCP runtime-directory restrictions also exclude the map.
There is no HTTP or MCP tool for restoration.

Mapping entries are saved atomically before a pseudonym is returned. A lock
serializes map updates across processes. If a process crashes while holding the
lock, check that no process is using it before removing
`data/private/anonymization_map.lock` manually. Existing-user lookups are cached
until the map's file signature changes.

IDs are random negative integers within JavaScript's exact-integer range, also
compatible with PostgreSQL BIGINT and SQLite. Names are unique inside a scope;
IDs are unique across the map. `scope: "channel"` is the default. Use
`scope: "project"` for cross-channel identities when starting a new map. An
existing map's scope cannot be changed. Restoration uses the original identity
fields recorded when the user was first assigned a pseudonym.

## Local conversion and restoration

```powershell
python main.py anonymize --file examples/example.json --channel demo --output data/raw/demo_anonymous.json
python main.py deanonymize --file data/raw/demo_anonymous.json --channel demo --map data/private/anonymization_map.json --output data/raw/demo_restored.json
```

Docker equivalents:

```powershell
docker compose run --rm cli anonymize --file examples/example.json --channel demo --output data/raw/demo_anonymous.json
docker compose run --rm cli deanonymize --file data/raw/demo_anonymous.json --channel demo --map data/private/anonymization_map.json --output data/raw/demo_restored.json
```

Both commands create a new JSON file and refuse to overwrite existing files.
Unknown IDs or a wrong restoration channel abort the operation. The source
archive is untouched. Commands default to `<source>_anonymize.json` and
`<source>_deanonymize.json` when `--output` is omitted. `anonymize --rules path`
selects another rules file. Use the same channel name for conversion and export.

## Incremental archives

New anonymized exports and Watch reuse the same map after restarts. Incremental
updates validate existing users against that channel's map. A raw, legacy or
unknown anonymized identity is rejected instead of silently merging incompatible
identities. Non-anonymized updates of new pseudonymized archives are rejected.

For an existing raw archive, explicitly convert a copy first. After reviewing
it and backing up the original, place the converted file at the channel's normal
dataset path before enabling `--anonymize`. No migration replaces runtime files
automatically. Archives created by the old in-memory anonymizer generally cannot
be restored; recreate them from the original data. Losing the new private map
also prevents restoration and safe incremental updates of its archives.

## Failures

Identity conflicts raise `IdentityModeMismatchError`; bad naming rules raise
`AnonymizationRulesError`. Invalid map data raises
`AnonymizationMapCorruptedError`, and lock timeouts raise
`AnonymizationMapLockedError`. Expected CLI failures are printed without a
traceback. See [error categories](errors.md) and [implementation limits](architecture.md#known-limitations).
