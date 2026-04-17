from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ClientBundle:
    client: dict[str, Any]
    contract_rules: dict[str, Any]
    field_mapping: dict[str, Any]


def load_client_bundle(client_dir: str | Path) -> ClientBundle:
    base_path = Path(client_dir)
    client = load_yaml(base_path / "client.yaml")
    contract_rules_path = _resolve_path(base_path, client["contract_rules_path"])
    field_mapping_path = _resolve_path(base_path, client["field_mapping_path"])
    return ClientBundle(
        client=client,
        contract_rules=load_yaml(contract_rules_path),
        field_mapping=load_yaml(field_mapping_path),
    )


def load_yaml(yaml_path: str | Path) -> dict[str, Any]:
    parser = _YamlParser(Path(yaml_path).read_text(encoding="utf-8"))
    parsed = parser.parse()
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected mapping at root of YAML file: {yaml_path}")
    return parsed


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _resolve_path(base_path: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return candidate.resolve()
    nested = (base_path / candidate)
    if nested.exists():
        return nested.resolve()
    return candidate.resolve()


class _YamlParser:
    def __init__(self, text: str) -> None:
        self.lines = self._tokenize(text)

    def parse(self) -> Any:
        if not self.lines:
            return {}
        value, _ = self._parse_block(0, self.lines[0]["indent"])
        return value

    def _parse_block(self, index: int, indent: int) -> tuple[Any, int]:
        if self.lines[index]["content"].startswith("- "):
            return self._parse_list(index, indent)
        return self._parse_mapping(index, indent)

    def _parse_mapping(self, index: int, indent: int) -> tuple[dict[str, Any], int]:
        mapping: dict[str, Any] = {}
        while index < len(self.lines):
            line = self.lines[index]
            if line["indent"] < indent or line["content"].startswith("- "):
                break
            if line["indent"] > indent:
                raise ValueError(f"Unexpected indentation in YAML: {line['content']}")

            key, raw_value = self._split_key_value(line["content"])
            index += 1
            if raw_value == "":
                if index < len(self.lines) and self.lines[index]["indent"] > indent:
                    value, index = self._parse_block(index, self.lines[index]["indent"])
                else:
                    value = {}
            elif raw_value == ">":
                value, index = self._parse_folded(index, indent)
            else:
                value = self._parse_scalar(raw_value)
            mapping[key] = value
        return mapping, index

    def _parse_list(self, index: int, indent: int) -> tuple[list[Any], int]:
        items: list[Any] = []
        while index < len(self.lines):
            line = self.lines[index]
            if line["indent"] != indent or not line["content"].startswith("- "):
                break
            content = line["content"][2:].strip()
            index += 1
            if content == "":
                value, index = self._parse_block(index, self.lines[index]["indent"])
                items.append(value)
                continue
            if ":" in content:
                item: dict[str, Any] = {}
                key, raw_value = self._split_key_value(content)
                if raw_value == "":
                    if index < len(self.lines) and self.lines[index]["indent"] > indent:
                        value, index = self._parse_block(index, self.lines[index]["indent"])
                    else:
                        value = {}
                elif raw_value == ">":
                    value, index = self._parse_folded(index, indent)
                else:
                    value = self._parse_scalar(raw_value)
                item[key] = value
                while index < len(self.lines):
                    next_line = self.lines[index]
                    if next_line["indent"] <= indent:
                        break
                    child_mapping, index = self._parse_mapping(index, next_line["indent"])
                    item.update(child_mapping)
                items.append(item)
                continue
            items.append(self._parse_scalar(content))
        return items, index

    def _parse_folded(self, index: int, indent: int) -> tuple[str, int]:
        parts: list[str] = []
        while index < len(self.lines) and self.lines[index]["indent"] > indent:
            parts.append(self.lines[index]["content"].strip())
            index += 1
        return " ".join(part for part in parts if part), index

    def _split_key_value(self, content: str) -> tuple[str, str]:
        key, value = content.split(":", 1)
        return key.strip(), value.strip()

    def _parse_scalar(self, value: str) -> Any:
        if value == "{}":
            return {}
        if value == "[]":
            return []
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        if value.startswith("'") and value.endswith("'"):
            return value[1:-1]
        if value.lower() in {"true", "false"}:
            return value.lower() == "true"
        if value.lower() == "null":
            return None
        if value.replace(".", "", 1).isdigit():
            return float(value) if "." in value else int(value)
        return value

    def _tokenize(self, text: str) -> list[dict[str, Any]]:
        tokens: list[dict[str, Any]] = []
        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(raw_line) - len(raw_line.lstrip(" "))
            tokens.append({"indent": indent, "content": raw_line[indent:]})
        return tokens
