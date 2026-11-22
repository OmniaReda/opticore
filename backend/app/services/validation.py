"""Stage 03 consistency report: drawing (buildings + Building IDs) vs survey Excel.

Computed on request from the imported data (nothing stored), so it is always up to date with the latest
drawing and survey. Thresholds and decision values come from app/rules/validation.yaml.
"""

import uuid
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from geoalchemy2.shape import to_shape
from shapely.geometry.base import BaseGeometry
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import geo, rules
from app.models import Building, BuildingLabel, Project, SurveyRecord
from app.schemas import (
    IssueSeverity,
    RuleSummary,
    ValidationIssue,
    ValidationReport,
    ValidationRule,
)
from app.services.buildings import natural_key

ERROR, WARNING, INFO = IssueSeverity.error, IssueSeverity.warning, IssueSeverity.info

# rule → (severity, title). Order = order in the report.
RULES: dict[ValidationRule, tuple[IssueSeverity, str]] = {
    ValidationRule.id_outside_building: (ERROR, "Building ID not inside any building"),
    ValidationRule.duplicate_drawing_id: (ERROR, "Building ID used more than once on the drawing"),
    ValidationRule.survey_not_in_drawing: (ERROR, "Survey ID not on the drawing"),
    ValidationRule.duplicate_survey_id: (ERROR, "Building ID used on more than one survey row"),
    ValidationRule.multiple_ids: (WARNING, "Several Building IDs in one building"),
    ValidationRule.drawing_id_without_survey: (WARNING, "Drawing ID without a survey row"),
    ValidationRule.gps_missing: (WARNING, "Survey row without valid GPS"),
    ValidationRule.gps_far_from_building: (WARNING, "Survey GPS far from its building"),
    ValidationRule.total_users_formula: (WARNING, "Total Users ≠ Floors × Users per Floor + GF Users"),
    ValidationRule.total_users_missing: (WARNING, "Survey row without Total Users"),
    ValidationRule.building_without_id: (INFO, "Building without ID (courtyard or gap?)"),
    ValidationRule.home_pass_differs: (INFO, "QTY of Home Pass differs from Total Users"),
    ValidationRule.needs_decision: (INFO, "Survey row marked for a decision"),
}

_DRAWING_RULES = {
    ValidationRule.id_outside_building,
    ValidationRule.duplicate_drawing_id,
    ValidationRule.multiple_ids,
    ValidationRule.building_without_id,
}
_SURVEY_RULES = {
    ValidationRule.duplicate_survey_id,
    ValidationRule.gps_missing,
    ValidationRule.total_users_formula,
    ValidationRule.total_users_missing,
    ValidationRule.home_pass_differs,
    ValidationRule.needs_decision,
}


@dataclass
class _Label:
    code: str
    point: BaseGeometry  # EPSG:4326
    building_id: uuid.UUID | None


def _issue(
    rule: ValidationRule,
    message: str,
    *,
    code: str | None = None,
    row: int | None = None,
    where: BaseGeometry | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        rule=rule,
        severity=RULES[rule][0],
        code=code,
        row_number=row,
        message=message,
        geometry=geo.to_geojson(where) if where is not None else None,
    )


def _drawing_checks(buildings: dict[uuid.UUID, BaseGeometry], labels: list[_Label]) -> Iterable[ValidationIssue]:
    codes_by_building: dict[uuid.UUID, list[str]] = defaultdict(list)
    for lab in labels:
        if lab.building_id is None:
            yield _issue(
                ValidationRule.id_outside_building,
                f"ID {lab.code} is not inside a building outline (missing or open outline?)",
                code=lab.code,
                where=lab.point,
            )
        else:
            codes_by_building[lab.building_id].append(lab.code)

    by_code: dict[str, list[_Label]] = defaultdict(list)
    for lab in labels:
        by_code[lab.code].append(lab)
    for code, same in by_code.items():
        if len(same) > 1:
            yield _issue(
                ValidationRule.duplicate_drawing_id,
                f"ID {code} appears {len(same)} times on the drawing",
                code=code,
                where=same[0].point,
            )

    for building_id, polygon in buildings.items():
        codes = sorted(codes_by_building.get(building_id, []), key=natural_key)
        if len(codes) > 1:
            yield _issue(
                ValidationRule.multiple_ids,
                f"IDs {', '.join(codes)} are in one outline (missing dividing line?)",
                code=codes[0],
                where=polygon.representative_point(),
            )
        elif not codes:
            area = geo.area_m2(polygon)
            yield _issue(
                ValidationRule.building_without_id,
                f"Outline of {area:.0f} m² has no Building ID",
                where=polygon.representative_point(),
            )


def _gps_distance_m(gps: BaseGeometry, labels: list[_Label], buildings: dict[uuid.UUID, BaseGeometry]) -> float:
    """Metres (UTM 36N) from the survey GPS to the building of this ID, or to its label if not in a building."""
    point = geo.to_measure_crs(gps)
    targets = [buildings[lab.building_id] if lab.building_id is not None else lab.point for lab in labels]
    return min(float(point.distance(geo.to_measure_crs(t))) for t in targets)


def _survey_checks(
    rows: list[SurveyRecord],
    labels_by_code: dict[str, list[_Label]],
    buildings: dict[uuid.UUID, BaseGeometry],
    cfg: rules.ValidationRules,
) -> Iterable[ValidationIssue]:
    has_drawing = bool(labels_by_code)
    counts = Counter(r.code for r in rows)
    reported_duplicates: set[str] = set()

    for r in rows:
        gps = to_shape(r.geometry) if r.geometry is not None else None
        here = gps or (labels_by_code[r.code][0].point if r.code in labels_by_code else None)

        if counts[r.code] > 1 and r.code not in reported_duplicates:
            reported_duplicates.add(r.code)
            yield _issue(
                ValidationRule.duplicate_survey_id,
                f"ID {r.code} is on {counts[r.code]} survey rows",
                code=r.code,
                row=r.row_number,
                where=here,
            )
        if has_drawing and r.code not in labels_by_code:
            yield _issue(
                ValidationRule.survey_not_in_drawing,
                f"Survey row for ID {r.code} has no matching ID on the drawing",
                code=r.code,
                row=r.row_number,
                where=here,
            )
        if gps is None:
            yield _issue(
                ValidationRule.gps_missing,
                "GPS N / E missing or out of range",
                code=r.code,
                row=r.row_number,
                where=here,
            )
        elif r.code in labels_by_code:
            distance = _gps_distance_m(gps, labels_by_code[r.code], buildings)
            if distance > cfg.gps_max_distance_m:
                yield _issue(
                    ValidationRule.gps_far_from_building,
                    f"GPS is {distance:.0f} m from building {r.code} (limit {cfg.gps_max_distance_m:.0f} m)",
                    code=r.code,
                    row=r.row_number,
                    where=gps,
                )

        if r.total_users is None:
            yield _issue(
                ValidationRule.total_users_missing,
                "Total Users is empty",
                code=r.code,
                row=r.row_number,
                where=here,
            )
        elif cfg.check_total_users_formula and r.floors is not None and r.users_per_floor is not None:
            expected = r.floors * r.users_per_floor + (r.gf_users or 0)
            if expected != r.total_users:
                yield _issue(
                    ValidationRule.total_users_formula,
                    f"Total Users {r.total_users}, but {r.floors} × {r.users_per_floor} + {r.gf_users or 0}"
                    f" = {expected}",
                    code=r.code,
                    row=r.row_number,
                    where=here,
                )
        if r.qty_home_pass is not None and r.total_users is not None and r.qty_home_pass != r.total_users:
            yield _issue(
                ValidationRule.home_pass_differs,
                f"QTY of Home Pass {r.qty_home_pass}, Total Users {r.total_users}",
                code=r.code,
                row=r.row_number,
                where=here,
            )

        decisions = []
        if r.te_comment in cfg.decision_values.te_comment:
            decisions.append(f"TE Comment: {r.te_comment}")
        if r.hp_count in cfg.decision_values.hp_count:
            decisions.append(f"HP: {r.hp_count}")
        if decisions:
            yield _issue(
                ValidationRule.needs_decision,
                " · ".join(decisions),
                code=r.code,
                row=r.row_number,
                where=here,
            )


def _drawing_ids_without_survey(
    labels_by_code: dict[str, list[_Label]], survey_codes: set[str]
) -> Iterable[ValidationIssue]:
    for code in sorted(set(labels_by_code) - survey_codes, key=natural_key):
        yield _issue(
            ValidationRule.drawing_id_without_survey,
            f"ID {code} is on the drawing but has no survey row",
            code=code,
            where=labels_by_code[code][0].point,
        )


def _sort_key(issue: ValidationIssue) -> tuple[int, list[int | str], int]:
    rule_order = list(RULES).index(issue.rule)
    return rule_order, natural_key(issue.code or "~"), issue.row_number or 0


def report(db: Session, project: Project) -> ValidationReport:
    cfg = rules.validation()
    buildings = {
        b.id: to_shape(b.geometry) for b in db.scalars(select(Building).where(Building.project_id == project.id))
    }
    labels = [
        _Label(lab.code, to_shape(lab.geometry), lab.building_id)
        for lab in db.scalars(select(BuildingLabel).where(BuildingLabel.project_id == project.id))
    ]
    rows = list(db.scalars(select(SurveyRecord).where(SurveyRecord.project_id == project.id)))
    labels_by_code: dict[str, list[_Label]] = defaultdict(list)
    for lab in labels:
        labels_by_code[lab.code].append(lab)

    has_drawing, has_survey = bool(buildings or labels), bool(rows)
    issues: list[ValidationIssue] = []
    ran: set[ValidationRule] = set()
    if has_drawing:
        issues += _drawing_checks(buildings, labels)
        ran |= _DRAWING_RULES
    if has_survey:
        issues += _survey_checks(rows, labels_by_code, buildings, cfg)
        ran |= _SURVEY_RULES
        if has_drawing:
            ran.add(ValidationRule.gps_far_from_building)
    if has_drawing and has_survey:
        issues += _drawing_ids_without_survey(labels_by_code, {r.code for r in rows})
        ran |= {ValidationRule.survey_not_in_drawing, ValidationRule.drawing_id_without_survey}
    issues.sort(key=_sort_key)

    counts = Counter(i.rule for i in issues)
    summary = [
        RuleSummary(rule=rule, severity=severity, title=title, count=counts[rule])
        for rule, (severity, title) in RULES.items()
        if rule in ran
    ]
    return ValidationReport(
        provisional=cfg.provisional,
        gps_max_distance_m=cfg.gps_max_distance_m,
        has_drawing=has_drawing,
        has_survey=has_survey,
        rules=summary,
        issues=issues,
    )
