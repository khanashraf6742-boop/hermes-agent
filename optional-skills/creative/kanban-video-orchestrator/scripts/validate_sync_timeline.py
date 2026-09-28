#!/usr/bin/env python3
"""Validate a narrated-explainer sync timeline using only the Python standard library."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path, PureWindowsPath
from typing import Any

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SRT_TIMING_RE = re.compile(
    r"^(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})\s+-->\s+"
    r"(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})(?:\s+.*)?$"
)
_DEFAULT_MAX_CPS = 20.0
_DEFAULT_MAX_VISUAL_LEAD_S = 0.5
_DEFAULT_MAX_VISUAL_LAG_S = 0.5
_CAPTION_START_TOLERANCE_S = 0.2
_CAPTION_EARLY_END_TOLERANCE_S = 0.15
_CAPTION_MAX_HOLD_S = 0.45
_CAPTION_OVERLAP_TOLERANCE_S = 0.03
_SRT_TIME_TOLERANCE_S = 0.02
_ALIGNMENT_OVERLAP_TOLERANCE_S = 0.02


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_keys(item: dict[str, Any], allowed: set[str], label: str, errors: list[str]) -> None:
    extras = sorted(set(item) - allowed)
    if extras:
        errors.append(f"{label} has unsupported field(s): {', '.join(extras)}.")


def _time_range(
    item: Any,
    label: str,
    duration_s: float | None,
    errors: list[str],
) -> tuple[float, float] | None:
    if not isinstance(item, dict):
        errors.append(f"{label} must be an object.")
        return None

    start = item.get("start_s")
    end = item.get("end_s")
    if not _is_number(start) or not _is_number(end):
        errors.append(f"{label} needs finite numeric start_s and end_s values.")
        return None
    if start < 0 or end <= start:
        errors.append(f"{label} must satisfy 0 <= start_s < end_s.")
    if duration_s is not None and end > duration_s + 1e-6:
        errors.append(f"{label} ends at {end:.3f}s, beyond audio duration {duration_s:.3f}s.")
    return float(start), float(end)


def _srt_time_seconds(hours: str, minutes: str, seconds: str, millis: str) -> float:
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def _validate_srt(path: Path, captions: list[Any]) -> list[str]:
    errors: list[str] = []
    try:
        content = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return [f"Cannot read SRT file {path}: {exc}"]

    blocks = [block for block in re.split(r"\n\s*\n", content.strip()) if block.strip()]
    if len(blocks) != len(captions):
        errors.append(f"SRT has {len(blocks)} cue(s), but the sync timeline has {len(captions)}.")

    for index, (block, caption) in enumerate(zip(blocks, captions)):
        label = f"SRT cue {index + 1}"
        if not isinstance(caption, dict):
            continue
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or not lines[0].isdigit():
            errors.append(f"{label} must contain a numeric cue index, timing row, and subtitle text.")
            continue
        if int(lines[0]) != index + 1:
            errors.append(f"{label} has a non-sequential cue index ({lines[0]}).")
        match = _SRT_TIMING_RE.fullmatch(lines[1])
        if match is None:
            errors.append(f"{label} has an invalid SRT timecode row.")
            continue
        groups = match.groups()
        start = _srt_time_seconds(*groups[:4])
        end = _srt_time_seconds(*groups[4:8])
        expected_start = caption.get("start_s")
        expected_end = caption.get("end_s")
        if _is_number(expected_start) and abs(start - expected_start) > _SRT_TIME_TOLERANCE_S:
            errors.append(f"{label} start differs from sync-timeline.json by more than 20ms.")
        if _is_number(expected_end) and abs(end - expected_end) > _SRT_TIME_TOLERANCE_S:
            errors.append(f"{label} end differs from sync-timeline.json by more than 20ms.")
        actual_text = " ".join(" ".join(lines[2:]).split())
        expected_text = caption.get("text")
        if _nonempty_string(expected_text) and actual_text != " ".join(expected_text.split()):
            errors.append(f"{label} text differs from the canonical timeline caption.")

    return errors


def validate_timeline(
    data: Any,
    *,
    audio_path: Path | None = None,
    srt_path: Path | None = None,
    max_cps: float = _DEFAULT_MAX_CPS,
    max_visual_lead_s: float = _DEFAULT_MAX_VISUAL_LEAD_S,
    max_visual_lag_s: float = _DEFAULT_MAX_VISUAL_LAG_S,
) -> list[str]:
    """Return structural, timing, coverage, and optional media-fingerprint/SRT errors."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Timeline root must be a JSON object."]
    _check_keys(data, {"schema_version", "audio_master", "alignment_units", "captions", "visual_events"}, "timeline", errors)

    schema_version = data.get("schema_version")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version != 1:
        errors.append("schema_version must be the integer 1.")

    audio_master = data.get("audio_master")
    if not isinstance(audio_master, dict):
        errors.append("audio_master must be an object.")
        audio_master = {}
    else:
        _check_keys(audio_master, {"path", "duration_s", "sha256", "language"}, "audio_master", errors)

    duration_s = audio_master.get("duration_s")
    if not _is_number(duration_s) or duration_s <= 0:
        errors.append("audio_master.duration_s must be a finite number greater than zero.")
        duration_s = None
    else:
        duration_s = float(duration_s)

    audio_relpath = audio_master.get("path")
    if not _nonempty_string(audio_relpath):
        errors.append("audio_master.path must be a non-empty workspace-relative path.")
    else:
        audio_posix = Path(audio_relpath)
        if (
            audio_posix.is_absolute()
            or PureWindowsPath(audio_relpath).is_absolute()
            or ".." in audio_posix.parts
            or ".." in PureWindowsPath(audio_relpath).parts
        ):
            errors.append("audio_master.path must stay inside the project workspace.")

    if not _nonempty_string(audio_master.get("language")):
        errors.append("audio_master.language must identify the spoken language.")
    fingerprint = audio_master.get("sha256")
    if not isinstance(fingerprint, str) or not _SHA256_RE.fullmatch(fingerprint):
        errors.append("audio_master.sha256 must be a lowercase 64-character SHA-256 hex digest.")

    if not _is_number(max_cps) or max_cps <= 0:
        errors.append("max_cps must be a finite number greater than zero.")
    if not _is_number(max_visual_lead_s) or max_visual_lead_s < 0:
        errors.append("max_visual_lead_s must be a finite number greater than or equal to zero.")
    if not _is_number(max_visual_lag_s) or max_visual_lag_s < 0:
        errors.append("max_visual_lag_s must be a finite number greater than or equal to zero.")

    if audio_path is not None:
        if not audio_path.is_file():
            errors.append(f"Audio file does not exist: {audio_path}")
        elif isinstance(fingerprint, str) and _SHA256_RE.fullmatch(fingerprint):
            try:
                digest = _sha256_file(audio_path)
            except OSError as exc:
                errors.append(f"Cannot hash audio file {audio_path}: {exc}")
            else:
                if digest != fingerprint:
                    errors.append(
                        "Audio fingerprint mismatch: the timeline is stale for the supplied final voice file. "
                        "Re-run transcription/alignment and rebuild dependent captions and visual timing."
                    )

    alignment_units = data.get("alignment_units")
    if not isinstance(alignment_units, list) or not alignment_units:
        errors.append("alignment_units must be a non-empty array of final-audio-aligned speech units.")
        alignment_units = []

    unit_by_id: dict[str, dict[str, Any]] = {}
    unit_index: dict[str, int] = {}
    all_ids: set[str] = set()
    previous_unit_end = -math.inf
    valid_granularities = {"word", "phrase", "sentence"}
    for index, unit in enumerate(alignment_units):
        label = f"alignment_units[{index}]"
        time_range = _time_range(unit, label, duration_s, errors)
        if not isinstance(unit, dict):
            continue
        _check_keys(
            unit,
            {"id", "granularity", "start_s", "end_s", "text", "concept_id"},
            label,
            errors,
        )
        unit_id = unit.get("id")
        if not _nonempty_string(unit_id):
            errors.append(f"{label}.id must be a non-empty string.")
        elif unit_id in all_ids:
            errors.append(f"Duplicate timeline id: {unit_id}.")
        else:
            all_ids.add(unit_id)
            unit_by_id[unit_id] = unit
            unit_index[unit_id] = index
        granularity = unit.get("granularity")
        if not isinstance(granularity, str) or granularity not in valid_granularities:
            errors.append(f"{label}.granularity must be word, phrase, or sentence.")
        if not _nonempty_string(unit.get("text")):
            errors.append(f"{label}.text must contain the aligned spoken words or phrase.")
        if not _nonempty_string(unit.get("concept_id")):
            errors.append(f"{label}.concept_id must link the speech unit to a teaching unit.")
        if time_range:
            start, end = time_range
            if start < previous_unit_end - _ALIGNMENT_OVERLAP_TOLERANCE_S:
                errors.append(f"{label} overlaps the preceding aligned unit or is out of order.")
            previous_unit_end = max(previous_unit_end, end)

    captions = data.get("captions")
    if not isinstance(captions, list) or not captions:
        errors.append("captions must be a non-empty array derived from the final audio.")
        captions = []

    captioned_unit_ids: set[str] = set()
    previous_caption_end = -math.inf
    previous_caption_last_unit_index = -1
    for index, caption in enumerate(captions):
        label = f"captions[{index}]"
        time_range = _time_range(caption, label, duration_s, errors)
        if not isinstance(caption, dict):
            continue
        _check_keys(
            caption,
            {"id", "start_s", "end_s", "text", "alignment_ids", "concept_id"},
            label,
            errors,
        )
        caption_id = caption.get("id")
        if not _nonempty_string(caption_id):
            errors.append(f"{label}.id must be a non-empty string.")
        elif caption_id in all_ids:
            errors.append(f"Duplicate timeline id: {caption_id}.")
        else:
            all_ids.add(caption_id)
        if not _nonempty_string(caption.get("text")):
            errors.append(f"{label}.text must contain a readable subtitle cue.")
        if not _nonempty_string(caption.get("concept_id")):
            errors.append(f"{label}.concept_id must identify the teaching unit.")

        references = caption.get("alignment_ids")
        if not isinstance(references, list) or not references:
            errors.append(f"{label}.alignment_ids must list the aligned speech units in this cue.")
            references = []
        if len(set(ref for ref in references if isinstance(ref, str))) != len(references):
            errors.append(f"{label}.alignment_ids must not repeat a speech-unit id.")

        referenced_units: list[dict[str, Any]] = []
        referenced_indices: list[int] = []
        for unit_id in references:
            if not isinstance(unit_id, str) or unit_id not in unit_by_id:
                errors.append(f"{label} references unknown alignment id {unit_id!r}.")
                continue
            if unit_id in captioned_unit_ids:
                errors.append(f"Aligned speech unit {unit_id} is assigned to more than one caption cue.")
            captioned_unit_ids.add(unit_id)
            referenced_units.append(unit_by_id[unit_id])
            referenced_indices.append(unit_index[unit_id])

        if referenced_indices:
            caption_concept_id = caption.get("concept_id")
            referenced_concepts = {
                unit.get("concept_id") for unit in referenced_units if isinstance(unit.get("concept_id"), str)
            }
            if _nonempty_string(caption_concept_id) and caption_concept_id not in referenced_concepts:
                errors.append(f"{label}.concept_id does not match any of its aligned speech.")
            if referenced_indices != sorted(referenced_indices):
                errors.append(f"{label}.alignment_ids must follow spoken order.")
            if referenced_indices[0] <= previous_caption_last_unit_index:
                errors.append(f"{label} is out of spoken-unit order.")
            if any(right != left + 1 for left, right in zip(referenced_indices, referenced_indices[1:])):
                errors.append(f"{label}.alignment_ids must cover one continuous phrase without skipping speech.")
            previous_caption_last_unit_index = referenced_indices[-1]

            if time_range:
                start, end = time_range
                first_unit = referenced_units[0]
                last_unit = referenced_units[-1]
                first_start = first_unit.get("start_s")
                last_end = last_unit.get("end_s")
                if _is_number(first_start) and start < first_start - _CAPTION_START_TOLERANCE_S:
                    errors.append(f"{label} appears too early relative to its first aligned speech unit.")
                if _is_number(first_start) and start > first_start + _CAPTION_START_TOLERANCE_S:
                    errors.append(f"{label} appears late relative to its first aligned speech unit.")
                if _is_number(last_end) and end < last_end - _CAPTION_EARLY_END_TOLERANCE_S:
                    errors.append(f"{label} disappears before its final aligned speech unit ends.")
                if _is_number(last_end) and end > last_end + _CAPTION_MAX_HOLD_S:
                    errors.append(f"{label} lingers too long after its final aligned speech unit.")
                if start < previous_caption_end - _CAPTION_OVERLAP_TOLERANCE_S:
                    errors.append(f"{label} overlaps the preceding subtitle cue.")
                previous_caption_end = max(previous_caption_end, end)

                text = caption.get("text")
                if _nonempty_string(text) and end > start and _is_number(max_cps):
                    char_count = len(" ".join(text.split()))
                    chars_per_second = char_count / (end - start)
                    if chars_per_second > max_cps:
                        errors.append(
                            f"{label} is too dense at {chars_per_second:.1f} characters/second "
                            f"(limit {max_cps:.1f}); split/rewrite the cue without losing meaning."
                        )

    uncaptioned = [unit_id for unit_id in unit_by_id if unit_id not in captioned_unit_ids]
    if uncaptioned:
        errors.append("Aligned speech units missing subtitle coverage: " + ", ".join(uncaptioned[:12]) + ".")

    visual_events = data.get("visual_events")
    if not isinstance(visual_events, list) or not visual_events:
        errors.append("visual_events must be a non-empty array tied to spoken teaching beats.")
        visual_events = []

    previous_visual_start = -math.inf
    visual_concepts: set[str] = set()
    for index, event in enumerate(visual_events):
        label = f"visual_events[{index}]"
        time_range = _time_range(event, label, duration_s, errors)
        if not isinstance(event, dict):
            continue
        _check_keys(
            event,
            {
                "id",
                "start_s",
                "end_s",
                "kind",
                "description",
                "anchor_alignment_ids",
                "concept_id",
                "scene_id",
            },
            label,
            errors,
        )
        event_id = event.get("id")
        if not _nonempty_string(event_id):
            errors.append(f"{label}.id must be a non-empty string.")
        elif event_id in all_ids:
            errors.append(f"Duplicate timeline id: {event_id}.")
        else:
            all_ids.add(event_id)
        if not _nonempty_string(event.get("kind")):
            errors.append(f"{label}.kind must identify the visual action.")
        if not _nonempty_string(event.get("description")):
            errors.append(f"{label}.description must explain the visual beat.")
        concept_id = event.get("concept_id")
        if not _nonempty_string(concept_id):
            errors.append(f"{label}.concept_id must identify the teaching unit.")
        else:
            visual_concepts.add(concept_id)

        anchor_ids = event.get("anchor_alignment_ids")
        if not isinstance(anchor_ids, list) or not anchor_ids:
            errors.append(f"{label}.anchor_alignment_ids must link the event to aligned speech.")
            anchor_ids = []
        if len(set(unit_id for unit_id in anchor_ids if isinstance(unit_id, str))) != len(anchor_ids):
            errors.append(f"{label}.anchor_alignment_ids must not repeat a speech-unit id.")
        if "scene_id" in event and not isinstance(event["scene_id"], str):
            errors.append(f"{label}.scene_id must be a string when provided.")
        anchors: list[dict[str, Any]] = []
        anchor_indices: list[int] = []
        for unit_id in anchor_ids:
            if not isinstance(unit_id, str) or unit_id not in unit_by_id:
                errors.append(f"{label} references unknown anchor alignment id {unit_id!r}.")
                continue
            anchors.append(unit_by_id[unit_id])
            anchor_indices.append(unit_index[unit_id])
        if anchor_indices and anchor_indices != sorted(anchor_indices):
            errors.append(f"{label}.anchor_alignment_ids must follow spoken order.")
        anchor_concepts = {
            unit.get("concept_id") for unit in anchors if isinstance(unit.get("concept_id"), str)
        }
        if anchors and _nonempty_string(concept_id) and concept_id not in anchor_concepts:
            errors.append(f"{label}.concept_id does not match any of its aligned anchors.")

        if time_range:
            start, _ = time_range
            if start < previous_visual_start:
                errors.append(f"{label} is out of timeline order.")
            previous_visual_start = start
            anchor_start = anchors[0].get("start_s") if anchors else None
            anchor_end = anchors[-1].get("end_s") if anchors else None
            if _is_number(anchor_start) and _is_number(max_visual_lead_s):
                earliest = anchor_start - max_visual_lead_s
                if start < earliest:
                    errors.append(
                        f"{label} reveals content {anchor_start - start:.2f}s before its spoken anchor "
                        f"(maximum lead {max_visual_lead_s:.2f}s)."
                    )
            if _is_number(anchor_end) and _is_number(max_visual_lag_s):
                latest = anchor_end + max_visual_lag_s
                if start > latest:
                    errors.append(
                        f"{label} starts {start - anchor_end:.2f}s after its spoken anchor ends "
                        f"(maximum lag {max_visual_lag_s:.2f}s)."
                    )

    spoken_concepts = {
        unit.get("concept_id")
        for unit in unit_by_id.values()
        if _nonempty_string(unit.get("concept_id"))
    }
    missing_visual_concepts = sorted(spoken_concepts - visual_concepts)
    if missing_visual_concepts:
        errors.append("Teaching units without a visual event: " + ", ".join(missing_visual_concepts) + ".")
    if srt_path is not None:
        errors.extend(_validate_srt(srt_path, captions))

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path, help="audio/sync-timeline.json")
    parser.add_argument("--audio", type=Path, help="locked final voice file whose SHA-256 must match")
    parser.add_argument("--srt", type=Path, help="generated SRT to compare with the canonical caption cues")
    parser.add_argument(
        "--max-cps",
        type=float,
        default=_DEFAULT_MAX_CPS,
        help=f"maximum subtitle characters per second (default: {_DEFAULT_MAX_CPS:g})",
    )
    parser.add_argument(
        "--max-visual-lead-s",
        type=float,
        default=_DEFAULT_MAX_VISUAL_LEAD_S,
        help=f"maximum visual reveal lead before its spoken anchor (default: {_DEFAULT_MAX_VISUAL_LEAD_S:g})",
    )
    parser.add_argument(
        "--max-visual-lag-s",
        type=float,
        default=_DEFAULT_MAX_VISUAL_LAG_S,
        help=f"maximum visual reveal lag after its spoken anchor (default: {_DEFAULT_MAX_VISUAL_LAG_S:g})",
    )
    args = parser.parse_args()

    try:
        data = json.loads(args.timeline.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"Cannot read timeline: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"Invalid timeline JSON: {exc}", file=sys.stderr)
        return 2

    errors = validate_timeline(
        data,
        audio_path=args.audio,
        srt_path=args.srt,
        max_cps=args.max_cps,
        max_visual_lead_s=args.max_visual_lead_s,
        max_visual_lag_s=args.max_visual_lag_s,
    )
    if errors:
        print(f"Sync timeline QA FAILED ({len(errors)} issue(s)):")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Sync timeline QA passed.")
    if args.audio is None:
        print("Note: pass --audio with the locked final voice file to verify its SHA-256 fingerprint.")
    if args.srt is None:
        print("Note: pass --srt with output/captions.srt to verify cue text and timings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
