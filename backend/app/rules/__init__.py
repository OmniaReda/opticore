"""Engineering / drawing rules loaded from YAML files in this folder.

Every rules file must say where its values come from (`source`), who approved them (`approved_by`)
and whether they are confirmed (`status: approved`) or still provisional (`status: TBC`).
"""

import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal, Self, cast

import yaml
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

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


def _load(name: str) -> dict[str, Any]:
    with (RULES_DIR / name).open(encoding="utf-8") as f:
        return cast(dict[str, Any], yaml.safe_load(f))


@lru_cache
def cad_layers() -> CadLayerRules:
    return CadLayerRules.model_validate(_load("cad_layers.yaml"))


SurveyField = Literal[
    "code",
    "visit_date",
    "street_name",
    "building_name",
    "building_number",
    "latitude",
    "longitude",
    "floors",
    "users_per_floor",
    "gf_users",
    "total_users",
    "hp_te_required",
    "comments",
    "sub_category",
    "final_category",
    "placemark_id",
    "entrance_length_m",
    "entrance_marked",
    "msan_note",
    "void_core",
    "hp_count",
    "qty_home_pass",
    "te_comment",
]


class SurveyColumnRules(RulesFile):
    sheet: str = Field(min_length=1)
    header_row: int = Field(ge=1)
    columns: dict[SurveyField, str]
    required: list[SurveyField]

    @model_validator(mode="after")
    def _required_columns_are_mapped(self) -> Self:
        if "code" not in self.required:
            raise ValueError("'code' (Building ID) must be required")
        unmapped = [f for f in self.required if f not in self.columns]
        if unmapped:
            raise ValueError(f"required fields without a column: {unmapped}")
        return self


@lru_cache
def survey_columns() -> SurveyColumnRules:
    return SurveyColumnRules.model_validate(_load("survey_columns.yaml"))
