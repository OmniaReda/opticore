"""Engineering / drawing rules loaded from YAML files in this folder.

Every rules file must say where its values come from (`source`), who approved them (`approved_by`)
and whether they are confirmed (`status: approved`) or still provisional (`status: TBC`).
"""
import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import AfterValidator, BaseModel, ConfigDict, Field

RULES_DIR = Path(__file__).resolve().parent


class RulesFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1)
    approved_by: str | None
    status: Literal["TBC", "approved"]

    @property
    def provisional(self) -> bool:
        return self.status != "approved"


def _compile(pattern: str) -> str:
    compiled = re.compile(pattern)
    if compiled.groups < 1:
        raise ValueError("id_pattern needs a capture group for the Building ID")
    return pattern


class CadProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str = ""
    building_layer: str = Field(min_length=1)
    id_layer: str = Field(min_length=1)
    id_pattern: Annotated[str, AfterValidator(_compile)]

    def match_id(self, text: str) -> str | None:
        """Building ID from a label text, or None if the text is not an ID."""
        m = re.match(self.id_pattern, text)
        return m.group(1) if m else None


class CadLayerRules(RulesFile):
    min_building_area_m2: float = Field(gt=0)
    profiles: list[CadProfile] = Field(min_length=1)


def _load(name: str) -> dict:
    with open(RULES_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def cad_layers() -> CadLayerRules:
    return CadLayerRules.model_validate(_load("cad_layers.yaml"))
