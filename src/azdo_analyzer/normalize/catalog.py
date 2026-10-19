"""Task catalog (GUID/name -> task info) and task group index."""

from __future__ import annotations

from dataclasses import dataclass

from azdo_analyzer.util import is_guid

_WINDOWS_HANDLERS = {"powershell", "powershell3", "powershellexe", "azurepowershell"}


@dataclass(frozen=True)
class TaskInfo:
    id: str | None
    name: str
    major: int | None
    friendly: str
    source: str  # builtin | extension | unknown
    extension: str | None = None
    windows_only: bool = False
    category: str | None = None

    @property
    def ref(self) -> str:
        return f"{self.name}@{self.major}" if self.major is not None else self.name


def _major(spec: object) -> int | None:
    if isinstance(spec, dict):
        value = spec.get("major")
        return int(value) if value is not None else None
    if spec is None:
        return None
    text = str(spec).strip().lstrip("v")
    head = text.split(".", 1)[0]
    return int(head) if head.isdigit() else None


def _version_tuple(entry: dict) -> tuple[int, int, int]:
    v = entry.get("version") or {}
    return (int(v.get("major") or 0), int(v.get("minor") or 0), int(v.get("patch") or 0))


class TaskCatalog:
    def __init__(self, tasks: list[dict] | None):
        self.by_id: dict[str, dict[int, dict]] = {}
        self.by_name: dict[str, dict[int, dict]] = {}
        for entry in tasks or []:
            if not isinstance(entry, dict) or not entry.get("id"):
                continue
            major = _version_tuple(entry)[0]
            for index, key in ((self.by_id, entry["id"].lower()), (self.by_name, str(entry.get("name", "")).lower())):
                slot = index.setdefault(key, {})
                if major not in slot or _version_tuple(entry) > _version_tuple(slot[major]):
                    slot[major] = entry

    @property
    def empty(self) -> bool:
        return not self.by_id

    @staticmethod
    def _pick(versions: dict[int, dict], major: int | None) -> dict:
        if major is not None and major in versions:
            return versions[major]
        return versions[max(versions)]

    @staticmethod
    def _info(entry: dict, major: int | None) -> TaskInfo:
        contribution = entry.get("contributionIdentifier")
        extension = ".".join(contribution.split(".")[:2]) if contribution else None
        handlers = {k.lower() for k in (entry.get("execution") or {})}
        return TaskInfo(
            id=entry.get("id"),
            name=entry.get("name") or entry.get("id"),
            major=major if major is not None else _version_tuple(entry)[0],
            friendly=entry.get("friendlyName") or entry.get("name") or "",
            source="extension" if contribution else "builtin",
            extension=extension,
            windows_only=bool(handlers) and handlers <= _WINDOWS_HANDLERS,
            category=entry.get("category"),
        )

    def resolve_id(self, task_id: str | None, version_spec: object = None) -> TaskInfo:
        major = _major(version_spec)
        versions = self.by_id.get((task_id or "").lower())
        if not versions:
            return TaskInfo(id=task_id, name=f"unknown:{task_id}", major=major, friendly="", source="unknown")
        return self._info(self._pick(versions, major), major)

    def resolve_ref(self, ref: str) -> TaskInfo:
        """YAML reference: 'Maven@3', '<guid>@1' or 'publisher.ext.contribution.Name@2'."""
        name, _, version = (ref or "").strip().partition("@")
        major = _major(version) if version else None
        if is_guid(name):
            return self.resolve_id(name, version or None)
        short = name.split(".")[-1] if "." in name else name
        versions = self.by_name.get(short.lower())
        if not versions:
            return TaskInfo(id=None, name=short, major=major, friendly=short, source="unknown")
        return self._info(self._pick(versions, major), major)


class TaskGroupIndex:
    def __init__(self, groups: list[dict] | None):
        self.by_id: dict[str, dict[int, dict]] = {}
        for entry in groups or []:
            if not isinstance(entry, dict) or not entry.get("id"):
                continue
            slot = self.by_id.setdefault(entry["id"].lower(), {})
            major = _version_tuple(entry)[0]
            if major not in slot or (_version_tuple(entry), entry.get("revision") or 0) > (
                _version_tuple(slot[major]),
                slot[major].get("revision") or 0,
            ):
                slot[major] = entry

    def get(self, group_id: str | None, version_spec: object = None) -> dict | None:
        versions = self.by_id.get((group_id or "").lower())
        if not versions:
            return None
        major = _major(version_spec)
        if major is not None and major in versions:
            return versions[major]
        return versions[max(versions)]
