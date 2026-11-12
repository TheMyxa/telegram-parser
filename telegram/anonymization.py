"""Persistent reversible pseudonyms. The private map must never be published."""
from errors import (IdentityModeMismatchError, AnonymizationRulesError, AnonymizationMapCorruptedError, AnonymizationMapLockedError)
import copy
import json
import os
import re
import secrets
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

PRIVATE_DIR = Path(__file__).resolve().parent.parent / "data" / "private"
MAP_PATH = PRIVATE_DIR / "anonymization_map.json"
IDENTITY_FIELDS = ("user_id", "username", "first_name", "last_name")


def read_map(path):
    if not path.exists():
        return {"version": 1, "scope": None, "channels": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as error:
        raise AnonymizationMapCorruptedError("Private anonymization map contains invalid JSON") from error
    if (not isinstance(data, dict) or data.get("version") != 1
            or data.get("scope") not in {None, "channel", "project"}
            or not isinstance(data.get("channels"), dict)):
        raise AnonymizationMapCorruptedError("Invalid anonymization map; restore its backup")
    ids = set()
    for entries in data["channels"].values():
        if not isinstance(entries, dict):
            raise AnonymizationMapCorruptedError("Invalid anonymization map entries")
        names = set()
        for key, entry in entries.items():
            if (not isinstance(entry, dict) or not isinstance(entry.get("anonymous_id"), int)
                    or entry["anonymous_id"] >= 0 or entry["anonymous_id"] in ids
                    or not isinstance(entry.get("alias"), str) or entry["alias"] in names
                    or not isinstance(entry.get("original"), dict)
                    or str(entry["original"].get("user_id")) != key):
                raise AnonymizationMapCorruptedError("Invalid or duplicate anonymization map identity")
            ids.add(entry["anonymous_id"])
            names.add(entry["alias"])
    return data


@contextmanager
def map_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = path.with_suffix(".lock")
    deadline = time.monotonic() + 10
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise AnonymizationMapLockedError("Anonymization map is locked; check other processes before removing its .lock file")
            time.sleep(0.05)
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def write_private_map(data, path):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".anonymization_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class UserAnonymizer:
    def __init__(self, path="anonymization_rules.json", *, map_path=MAP_PATH):
        self.map_path = Path(map_path)
        try:
            text = Path(path).read_text(encoding="utf-8")
        except UnicodeError as error:
            raise AnonymizationRulesError("Anonymization rules must use UTF-8") from error
        if Path(path).suffix.lower() == ".json":
            try:
                rules = json.loads(text)
            except json.JSONDecodeError as error:
                raise AnonymizationRulesError("Anonymization rules contain invalid JSON") from error
            if not isinstance(rules, dict) or rules.get("version") != 1:
                raise AnonymizationRulesError("Unsupported anonymization rules")
            if rules.get("scope") not in {"channel", "project"} or rules.get("collision_policy") != "suffix":
                raise AnonymizationRulesError("Rules require scope channel/project and collision_policy suffix")
            if rules.get("fields") != {"user_id": "replace", "username": "clear", "first_name": "alias", "last_name": "clear"}:
                raise AnonymizationRulesError("Unsupported anonymization field rules")
            for field in ("adjectives", "nouns"):
                values = rules.get(field)
                if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v.strip() for v in values):
                    raise AnonymizationRulesError(f"Rules require a nonempty {field} list")
            self.aliases = list(dict.fromkeys(f"{a.strip()} {n.strip()}" for a in rules["adjectives"] for n in rules["nouns"]))
            self.scope = rules["scope"]
        else:
            self.aliases = list(dict.fromkeys(s.strip() for s in text.splitlines() if s.strip() and not s.strip().startswith("#")))
            self.scope = "channel"
        if not self.aliases:
            raise AnonymizationRulesError("Anonymization names must not be empty")
        data = read_map(self.map_path)
        if data["scope"] not in (None, self.scope):
            raise IdentityModeMismatchError("Anonymization scope differs from the existing map")
        self._cache = data
        self._stamp = self.map_stamp()

    def map_stamp(self):
        try:
            stat = self.map_path.stat()
            return stat.st_mtime_ns, stat.st_size
        except FileNotFoundError:
            return None

    def current_map(self):
        stamp = self.map_stamp()
        if stamp != self._stamp:
            self._cache = read_map(self.map_path)
            self._stamp = stamp
        if self._cache["scope"] not in (None, self.scope):
            raise IdentityModeMismatchError("Anonymization scope differs from the existing map")
        return self._cache

    def scope_key(self, channel):
        if self.scope == "project":
            return "__project__"
        if not channel:
            raise AnonymizationRulesError("Channel is required for channel-scoped anonymization")
        from telegram.messages import get_channel_name
        return get_channel_name(channel).lower()

    def anonymize_user(self, user_data, channel=None):
        if not user_data:
            return None
        scope = self.scope_key(channel)
        key = str(user_data["user_id"])
        entry = self.current_map()["channels"].get(scope, {}).get(key)
        if entry is not None:
            return {**user_data, "user_id": entry["anonymous_id"], "username": None,
                    "first_name": entry["alias"], "last_name": None}
        with map_lock(self.map_path):
            data = read_map(self.map_path)
            if data["scope"] not in (None, self.scope):
                raise IdentityModeMismatchError("Anonymization scope differs from the existing map")
            data["scope"] = self.scope
            entries = data["channels"].setdefault(scope, {})
            original = {field: user_data.get(field) for field in IDENTITY_FIELDS}
            if key not in entries:
                if not isinstance(user_data["user_id"], int) or user_data["user_id"] <= 0:
                    raise IdentityModeMismatchError("Cannot anonymize an unknown pseudonym")
                used_names = {e["alias"] for e in entries.values()}
                index = len(entries)
                while True:
                    suffix = index // len(self.aliases)
                    alias = self.aliases[index % len(self.aliases)] + (f" {suffix + 1}" if suffix else "")
                    if alias not in used_names:
                        break
                    index += 1
                used_ids = {e["anonymous_id"] for group in data["channels"].values() for e in group.values()}
                anonymous_id = -secrets.randbelow(2**52) - 1
                while anonymous_id in used_ids:
                    anonymous_id = -secrets.randbelow(2**52) - 1
                entries[key] = {"anonymous_id": anonymous_id, "alias": alias, "original": original}
                write_private_map(data, self.map_path)
            entry = entries[key]
            self._cache = data
            self._stamp = self.map_stamp()
            # Keep the identity observed when this map entry was created. This
            # makes restoration deterministic even if Telegram names change.
        return {**user_data, "user_id": entry["anonymous_id"], "username": None,
                "first_name": entry["alias"], "last_name": None}

    def validate_dataset(self, posts, channel):
        entries = self.current_map()["channels"].get(self.scope_key(channel), {})
        known = {e["anonymous_id"]: e for e in entries.values()}
        for user in iter_users(posts):
            entry = known.get(user.get("user_id"))
            if not entry or any(user.get(k) != v for k, v in {
                "username": None, "first_name": entry["alias"], "last_name": None,
            }.items()):
                raise IdentityModeMismatchError("Dataset identity mode does not match the private map; use a new dataset or explicitly convert the original with anonymize")


def iter_users(posts):
    for post in posts:
        for comment in post.get("comments") or []:
            if comment.get("user"):
                yield comment["user"]


def transform_dataset(posts, map_path, channel, *, rules=None):
    result = copy.deepcopy(posts)
    if rules is not None:
        anonymizer = UserAnonymizer(rules, map_path=map_path)
        for user in iter_users(result):
            if re.fullmatch(r"user_\d+", str(user.get("username", ""))) and str(user.get("user_id")) == str(user["username"])[5:]:
                raise IdentityModeMismatchError("Possible legacy pseudonyms: use the original export for reversible conversion")
            user.update(anonymizer.anonymize_user(user, channel))
    else:
        path = Path(map_path)
        if not path.is_file():
            raise FileNotFoundError("Private anonymization map not found")
        data = read_map(path)
        from telegram.messages import get_channel_name
        scope = "__project__" if data["scope"] == "project" else get_channel_name(channel).lower()
        entries = {e["anonymous_id"]: e for e in data["channels"].get(scope, {}).values()}
        for user in iter_users(result):
            entry = entries.get(user.get("user_id"))
            if entry is None:
                raise IdentityModeMismatchError("User cannot be restored with this map and channel")
            user.update(entry["original"])
    return result
