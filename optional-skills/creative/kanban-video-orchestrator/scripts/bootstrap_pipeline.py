#!/usr/bin/env python3
"""
Bootstrap a video production kanban from a structured plan JSON.

Reads a plan.json describing the team + brief, expands templates from
../assets/, and writes a setup.sh that creates Hermes profiles and fires the
initial kanban task.

Profile-config patching, SOUL.md-per-profile, TEAM.md task-graph convention,
and the `hermes kanban create --workspace dir:` initial-task pattern are
adapted from alt-glitch's NousResearch/kanban-video-pipeline.

Usage:
    bootstrap_pipeline.py plan.json [--out setup.sh]

The plan.json schema is documented inline below — see the `validate_plan`
function. A minimal example:

    {
      "title": "Q3 Product Teaser",
      "slug": "q3-product-teaser",
      "tenant": "q3-product-teaser",
      "duration_s": 30,
      "aspect": "1:1",
      "resolution": "1080x1080",
      "fps": 30,
      "team": [
        {
          "profile": "director",
          "role": "director",
          "toolsets": ["kanban", "terminal", "file"],
          "skills": [],
          "responsibilities": "...",
          "inputs": "brief.md, TEAM.md, taste/",
          "outputs": "kanban tasks for the team"
        },
        ...
      ],
      "scenes": [
        {"n": 1, "time": "0:00-0:08", "content": "...", "tool": "renderer-ascii"},
        ...
      ],
      "audio": {"approach": "voiceover + music bed", "vo": "ElevenLabs Lily",
                "music": "license-free", "sfx": "n/a"},
      "three_layer_sync": true,
      "deliverables": [
        {"format": "mp4", "resolution": "1080x1080", "notes": "primary"}
      ],
      "api_keys_required": ["ELEVENLABS_API_KEY", "OPENROUTER_API_KEY"],
      "brief_extra": {
        "concept_one_liner": "...",
        "emotional_north_star": "...",
        "visual_refs": "...",
        "tone": "...",
        "brand_constraints": "..."
      }
    }
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def load_template(name: str) -> str:
    return (ASSETS_DIR / name).read_text(encoding="utf-8")


PROFILE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]+$")


def _has_voiceover(plan: dict) -> bool:
    """Whether the plan supplies or generates spoken narration."""
    team = plan.get("team")
    roles = (
        {member.get("role") for member in team if isinstance(member, dict) and isinstance(member.get("role"), str)}
        if isinstance(team, list)
        else set()
    )
    if "voice-talent" in roles:
        return True
    audio = plan.get("audio")
    audio = audio if isinstance(audio, dict) else {}
    voice = audio.get("vo")
    if isinstance(voice, str):
        return voice.strip().lower() not in {"", "n/a", "na", "none", "silent", "_(n/a)_"}
    return bool(voice)


def _requires_three_layer_sync(plan: dict) -> bool:
    """Whether to gate renderer timing on final-audio alignment."""
    team = plan.get("team")
    roles = (
        {member.get("role") for member in team if isinstance(member, dict) and isinstance(member.get("role"), str)}
        if isinstance(team, list)
        else set()
    )
    return bool(plan.get("three_layer_sync")) or (
        _has_voiceover(plan) and "captioner" in roles
    )


def validate_plan(plan: dict) -> list[str]:
    """Return a list of validation error strings; empty list = valid."""
    if not isinstance(plan, dict):
        return ["plan must be a JSON object"]
    errors = []
    required_top = ["title", "slug", "tenant", "duration_s", "aspect",
                    "resolution", "fps", "team", "scenes", "audio",
                    "deliverables"]
    for k in required_top:
        if k not in plan:
            errors.append(f"missing required key: {k}")

    if "team" in plan:
        team = plan["team"]
        if not isinstance(team, list) or not team:
            errors.append("team must be a non-empty list")
        else:
            roles: list[str] = []
            seen_profiles: set[str] = set()
            for i, member in enumerate(team):
                if not isinstance(member, dict):
                    errors.append(f"team[{i}] must be an object")
                    continue
                for key in ["profile", "role", "toolsets", "skills", "responsibilities"]:
                    if key not in member:
                        errors.append(f"team[{i}] missing {key}")

                role = member.get("role")
                if isinstance(role, str) and role:
                    roles.append(role)
                else:
                    errors.append(f"team[{i}].role must be a non-empty string")

                profile = member.get("profile")
                if not isinstance(profile, str) or not PROFILE_NAME_RE.fullmatch(profile):
                    errors.append(
                        f"team[{i}].profile {profile!r} must match "
                        f"[a-z0-9][a-z0-9_-]{{0,63}} per Hermes profile rules"
                    )
                elif profile in seen_profiles:
                    errors.append(f"team[{i}].profile {profile!r} is duplicated")
                else:
                    seen_profiles.add(profile)

                for key in ("toolsets", "skills"):
                    value = member.get(key)
                    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                        errors.append(f"team[{i}].{key} must be a list of strings")

            if "director" not in roles:
                errors.append("team must include a director role")

    if "three_layer_sync" in plan and not isinstance(plan["three_layer_sync"], bool):
        errors.append("three_layer_sync must be a boolean when provided")
    if plan.get("three_layer_sync") is True:
        team = plan.get("team")
        roles = (
            {member.get("role") for member in team if isinstance(member, dict) and isinstance(member.get("role"), str)}
            if isinstance(team, list)
            else set()
        )
        if "captioner" not in roles:
            errors.append("three_layer_sync requires a captioner role for alignment and caption QA")
        if not _has_voiceover(plan):
            errors.append("three_layer_sync requires a voice-talent profile or audio.vo source")

    if "slug" in plan:
        if not isinstance(plan["slug"], str) or not SLUG_RE.fullmatch(plan["slug"]):
            errors.append("slug must be lowercase, hyphenated, "
                          "starting with [a-z0-9]")

    return errors


def render_brief(plan: dict) -> str:
    """Render brief.md from the plan."""
    tmpl = load_template("brief.md.tmpl")
    extra = plan.get("brief_extra", {})

    # Scene table rows
    scene_rows = []
    for s in plan["scenes"]:
        scene_rows.append(
            f"| {s.get('n', '?')} | {s.get('time', '?')} | "
            f"{s.get('content', '')} | {s.get('tool', '')} | "
            f"{s.get('audio', '')} | {s.get('notes', '')} |"
        )
    scene_table = "\n".join(scene_rows) if scene_rows else "_(none yet)_"

    # Deliverable rows
    deliv_rows = []
    for d in plan["deliverables"]:
        deliv_rows.append(
            f"| {d.get('format', '?')} | {d.get('resolution', '?')} | "
            f"{d.get('notes', '')} |"
        )
    deliv_table = "\n".join(deliv_rows) if deliv_rows else "_(none)_"

    # Replacements (single-pass)
    replacements = {
        "TITLE": plan["title"],
        "SLUG": plan["slug"],
        "TENANT": plan["tenant"],
        "WORKSPACE": f"~/projects/video-pipeline/{plan['slug']}",
        "ONE_LINE_PITCH": extra.get("concept_one_liner", "_(TBD)_"),
        "EMOTIONAL_NORTH_STAR": extra.get("emotional_north_star", "_(TBD)_"),
        "DURATION_S": str(plan["duration_s"]),
        "ASPECT": plan["aspect"],
        "RESOLUTION": plan["resolution"],
        "FPS": str(plan["fps"]),
        "PLATFORMS": extra.get("platforms", "_(TBD)_"),
        "DEADLINE": extra.get("deadline", "_(none)_"),
        "QUALITY_BAR": extra.get("quality_bar", "polished"),
        "VISUAL_REFS": extra.get("visual_refs", "_(none)_"),
        "TONE": extra.get("tone", "_(TBD)_"),
        "BRAND_CONSTRAINTS": extra.get("brand_constraints", "_(none)_"),
        "AESTHETIC_RULES": extra.get("aesthetic_rules", "_(TBD)_"),
        "AUDIO_APPROACH": plan["audio"].get("approach", "_(TBD)_"),
        "VO_DETAILS": plan["audio"].get("vo", "_(n/a)_"),
        "THREE_LAYER_SYNC": (
            "MANDATORY — lock final voice audio, align it, author the shared timeline from the bundled schema, and validate it before renderer timing."
            if _requires_three_layer_sync(plan)
            else (
                "Not enabled for this voiceover; follow the brief's caption and visual-sync requirements."
                if _has_voiceover(plan)
                else "Not applicable — no voiceover is planned."
            )
        ),
        "MUSIC_DETAILS": plan["audio"].get("music", "_(n/a)_"),
        "SFX_DETAILS": plan["audio"].get("sfx", "_(n/a)_"),
        "PRIMARY_FORMAT": plan["deliverables"][0]["format"],
        "PRIMARY_RES": plan["deliverables"][0]["resolution"],
        "ALT_FORMAT_1": (plan["deliverables"][1]["format"]
                          if len(plan["deliverables"]) > 1 else "_(none)_"),
        "ALT_RES_1": (plan["deliverables"][1]["resolution"]
                       if len(plan["deliverables"]) > 1 else ""),
        "ALT_NOTES_1": (plan["deliverables"][1].get("notes", "")
                         if len(plan["deliverables"]) > 1 else ""),
        "API_KEYS_REQUIRED": ", ".join(plan.get("api_keys_required", [])) or "none",
        "EXT_DEPS": extra.get("ext_deps", "ffmpeg, Python 3.11+"),
        "SOURCE_ASSETS": extra.get("source_assets", "_(none)_"),
    }
    out = tmpl
    for k, v in replacements.items():
        out = out.replace("{{" + k + "}}", str(v))

    # Scene + deliv tables: replace the placeholder row in the template
    out = re.sub(
        r"\|\s*1\s*\|\s*0:00–0:0X.+?\n\|\s*2\s*\|.+?\n",
        scene_table + "\n",
        out, flags=re.DOTALL,
    )
    return out


def render_team_md(plan: dict) -> str:
    """Render TEAM.md with audio-alignment dependencies when sync is required."""
    lines = [f"# Team & Task Graph — {plan['title']}", "", "## Team", ""]
    for member in plan["team"]:
        skills = (
            f"loads `{', '.join(member['skills'])}`"
            if member["skills"] else "no skills required"
        )
        lines.append(
            f"- `{member['profile']}` — {member['responsibilities']} ({skills})"
        )
    lines.extend(["", "## Task Graph", "", "```"])

    profiles_by_role = {member["role"]: member["profile"] for member in plan["team"]}
    lines.append(f"T0  {profiles_by_role.get('director', 'director')} — decompose")
    next_id = 1

    def add_task(role: str, description: str, parents: list[str]) -> str | None:
        nonlocal next_id
        profile = profiles_by_role.get(role)
        if profile is None:
            return None
        task_id = f"T{next_id}"
        next_id += 1
        parent_label = "parent" if len(parents) == 1 else "parents"
        lines.append(
            f"{task_id:5} {profile} — {description} "
            f"({parent_label}: {', '.join(parents)})"
        )
        return task_id

    writer_role = next(
        (role for role in ("writer", "screenwriter", "copywriter") if role in profiles_by_role),
        None,
    )
    writer_id = add_task(
        writer_role,
        "atomic coverage + batched approved script/narration",
        ["T0"],
    ) if writer_role else None

    cinematographer_id = add_task(
        "cinematographer", "visual spec for all scenes", [writer_id or "T0"]
    )
    music_id = add_task(
        "music-supervisor", "track analysis + beats.json", ["T0"]
    )

    voice_id = add_task(
        "voice-talent", "generate/lock final narration audio", [writer_id or "T0"]
    )
    sync_required = _requires_three_layer_sync(plan)
    alignment_id = None
    if sync_required:
        alignment_id = add_task(
            "captioner",
            "transcribe/force-align locked voice + SHA-256; write audio/sync-timeline.json + output/captions.srt",
            [voice_id or "T0"],
        )

    scene_ids: list[str] = []
    for scene in plan["scenes"]:
        renderer_role_or_profile = scene.get("tool") or "renderer"
        renderer_profile = renderer_role_or_profile
        for member in plan["team"]:
            if member["role"] == renderer_role_or_profile or member["profile"] == renderer_role_or_profile:
                renderer_profile = member["profile"]
                break

        parents = [cinematographer_id or writer_id or "T0"]
        if writer_id and writer_id not in parents:
            parents.append(writer_id)
        if music_id:
            parents.append(music_id)
        if alignment_id:
            parents.append(alignment_id)
        task_id = f"T{next_id}"
        next_id += 1
        parent_label = "parent" if len(parents) == 1 else "parents"
        lines.append(
            f"{task_id:5} {renderer_profile} — scene {scene.get('n', '?')}: "
            f"{scene.get('content', '')[:50]} ({parent_label}: {', '.join(parents)})"
        )
        scene_ids.append(task_id)

    mix_parents = [task_id for task_id in (music_id, voice_id) if task_id]
    audio_mix_id = add_task("audio-mixer", "mix audio", mix_parents or ["T0"])

    editor_parents = list(scene_ids)
    for task_id in (audio_mix_id, voice_id, music_id, alignment_id):
        if task_id and task_id not in editor_parents:
            editor_parents.append(task_id)
    editor_id = add_task("editor", "assemble + mux", editor_parents or ["T0"])

    last_id = editor_id
    if "captioner" in profiles_by_role and editor_id:
        caption_parents = [editor_id]
        if alignment_id:
            caption_parents.append(alignment_id)
        caption_task = (
            "burn the reviewed captions.srt into the assembled video"
            if alignment_id
            else "generate requested captions + burn after assembly"
        )
        last_id = add_task("captioner", caption_task, caption_parents)

    add_task("reviewer", "final QA + delivery gate", [last_id or editor_id or "T0"])

    if sync_required:
        lines.extend([
            "```",
            "",
            "## Three-layer synchronization contract",
            "",
            "This sync-enabled narrated project requires aligned voice, subtitles, and visual timing.",
            "The final voice audio is the master clock. The alignment task must finish before",
            "renderer timing is finalized; all renderers and the editor consume the same",
            "`audio/sync-timeline.json`. Any audio change invalidates downstream timing.",
            "The bootstrap places the schema and validator in `tools/`; run",
            "`python3 tools/validate_sync_timeline.py audio/sync-timeline.json --audio audio/voiceover/final.mp3 --srt output/captions.srt`",
            "before render timing. Automated checks do not replace semantic or final-video review.",
            "A final voice/subtitle/visual mismatch fails QA and blocks delivery.",
            "",
            "## Required synchronization artifacts",
            "",
            "- `audio/voiceover/final.mp3` — locked narration",
            "- `audio/transcript.json` — reviewed transcript and available word/phrase/sentence timestamps",
            "- `audio/sync-timeline.json` — canonical voice/caption/visual event timeline",
            "- `output/captions.srt` — subtitle cues derived from the final audio",
            "- `tools/sync-timeline.schema.json`, `tools/sync-timeline.example.json`, and `tools/validate_sync_timeline.py` — contract, starter, and validator",
        ])
    else:
        lines.append("```")

    lines.extend([
        "",
        "## Per-task workspace requirement",
        "",
        "All `kanban_create` calls MUST pass:",
        "```",
        'workspace_kind="dir"',
        f'workspace_path="$HOME/projects/video-pipeline/{plan["slug"]}"',
        f'tenant="{plan["tenant"]}"',
        "```",
    ])
    return "\n".join(lines)


def render_setup_sh(plan: dict, brief_md: str, team_md: str) -> str:
    """Render setup.sh from the plan."""
    tmpl = load_template("setup.sh.tmpl")

    # API key checks
    key_checks = []
    for key in plan.get("api_keys_required", []):
        key_checks.append(f'check_key {key} hermes {key} || exit 1')
    key_checks_str = "\n".join(key_checks) if key_checks else "# (no API keys required)"

    # Scene dirs
    scene_dir_lines = []
    for s in plan["scenes"]:
        n = s.get("n", "?")
        scene_dir_lines.append(f'mkdir -p "$WORKSPACE/scenes/scene-{n:02d}"/checkpoints')
    scene_dirs = "\n".join(scene_dir_lines) if scene_dir_lines else ""

    # Profile create
    profile_creates = []
    for t in plan["team"]:
        profile_creates.append(
            f'hermes profile create {t["profile"]} --clone 2>/dev/null || true'
        )

    # Profile config — emit JSON arrays so the bash function can pass them
    # safely through to the Python YAML patcher.
    profile_configs = []
    for t in plan["team"]:
        ts_json = json.dumps(t["toolsets"])
        sk_json = json.dumps(t["skills"])
        # Use single-quoted bash strings; JSON only contains "/[/], no single
        # quotes, so this is safe.
        profile_configs.append(
            f"configure_profile {t['profile']!r} {ts_json!r} {sk_json!r}"
        )

    # SOUL writes — uses heredocs per profile
    soul_writes = []
    for t in plan["team"]:
        soul_writes.append(
            f'cat > "$HOME/.hermes/profiles/{t["profile"]}/SOUL.md" <<\'SOUL_EOF\'\n'
            f"{render_soul_md(t, plan)}\n"
            f"SOUL_EOF\n"
            f'echo "  ✓ SOUL.md for {t["profile"]}"'
        )

    # Taste writes (placeholder; real content optional)
    taste_writes = (
        'cat > "$WORKSPACE/taste/brand-guide.md" <<\'TASTE_EOF\'\n'
        '# Brand Guide\n\n'
        '_(Populate with project-specific colors, typography, motion rules)_\n'
        'TASTE_EOF\n'
        'cat > "$WORKSPACE/taste/emotional-dna.md" <<\'DNA_EOF\'\n'
        '# Emotional DNA\n\n'
        '_(What this piece should FEEL like — populate from the brief.)_\n'
        'DNA_EOF'
    )

    # Embed the dependency-free sync validator and JSON Schema in narrated explainer workspaces.
    sync_tool_install = ""
    if _requires_three_layer_sync(plan):
        skill_root = Path(__file__).resolve().parents[1]
        schema = (skill_root / "assets/sync-timeline.schema.json").read_text(encoding="utf-8")
        example = (skill_root / "assets/sync-timeline.example.json").read_text(encoding="utf-8")
        validator = (skill_root / "scripts/validate_sync_timeline.py").read_text(encoding="utf-8")
        sync_tool_install = (
            'cat > "$WORKSPACE/tools/sync-timeline.schema.json" <<\'SYNC_SCHEMA_EOF\'\n'
            f"{schema}\nSYNC_SCHEMA_EOF\n"
            'cat > "$WORKSPACE/tools/sync-timeline.example.json" <<\'SYNC_EXAMPLE_EOF\'\n'
            f"{example}\nSYNC_EXAMPLE_EOF\n"
            'cat > "$WORKSPACE/tools/validate_sync_timeline.py" <<\'SYNC_VALIDATOR_EOF\'\n'
            f"{validator}\nSYNC_VALIDATOR_EOF\n"
            'chmod +x "$WORKSPACE/tools/validate_sync_timeline.py"\n'
            'echo "  ✓ sync timeline example, schema + validator"'
        )

    # Asset copies — leave empty by default; user fills in
    asset_copies = "# Add cp/rsync commands here for any provided assets"

    out = tmpl
    out = out.replace("{{TITLE}}", plan["title"])
    out = out.replace("{{SLUG}}", plan["slug"])
    out = out.replace("{{TENANT}}", plan["tenant"])
    out = out.replace("{{WORKSPACE}}", f"~/projects/video-pipeline/{plan['slug']}")
    out = out.replace("{{KEY_CHECKS}}", key_checks_str)
    out = out.replace("{{SCENE_DIRS}}", scene_dirs)
    out = out.replace("{{SYNC_TOOL_INSTALL}}", sync_tool_install)
    out = out.replace("{{PROFILE_CREATE_COMMANDS}}", "\n".join(profile_creates))
    out = out.replace("{{PROFILE_CONFIG_COMMANDS}}", "\n".join(profile_configs))
    out = out.replace("{{SOUL_WRITES}}", "\n".join(soul_writes))
    out = out.replace("{{BRIEF_CONTENTS}}", brief_md)
    out = out.replace("{{TEAM_CONTENTS}}", team_md)
    out = out.replace("{{TASTE_WRITES}}", taste_writes)
    out = out.replace("{{ASSET_COPIES}}", asset_copies)

    return out


def render_soul_md(team_member: dict, plan: dict) -> str:
    """Render a profile's SOUL.md from a team member dict + plan context."""
    tmpl = load_template("soul.md.tmpl")
    role = team_member["role"]

    common_rules = (
        "- **Read the brief and team graph** before doing anything else.\n"
        "- **Pass `workspace_kind=\"dir\"` and `workspace_path` on every "
        "`kanban_create` call.** This keeps the team in one shared workspace.\n"
        f"- **Use tenant `{plan['tenant']}`** on every kanban call.\n"
        "- **Write outputs to predictable paths.** Other profiles depend on "
        "your filename conventions.\n"
        "- **Emit heartbeats** during long-running work. Renderers should "
        "report frame counts; editors should report assembly progress.\n"
    )

    if _requires_three_layer_sync(plan):
        common_rules += (
            "- **Three-layer synchronization is mandatory for this project.** "
            "The final voice audio is the master clock; never time subtitles "
            "or visual events independently from it.\n"
            "- **Consume `audio/sync-timeline.json`** for spoken beats, subtitle "
            "cues, and visual reveal/highlight times. The captioner aligns the "
            "actual locked audio and owns `output/captions.srt`.\n"
            "- **For teaching explainers, keep the canvas continuous.** Build "
            "context progressively; never reveal an unexplained answer early.\n"
            "- **Validate the handoff.** Follow `tools/sync-timeline.schema.json` "
            "and run `python3 tools/validate_sync_timeline.py "
            "audio/sync-timeline.json --audio audio/voiceover/final.mp3 "
            "--srt output/captions.srt`; fix "
            "all failures before renderer timing proceeds.\n"
            "- **If the audio changes, stop dependent work.** Regenerate the "
            "transcript/alignment and update captions, visuals, and edit timing.\n"
            "- **Do not approve or deliver a mismatch** between spoken meaning, "
            "caption text, and the visible teaching content.\n"
        )

    if role in {"writer", "screenwriter", "copywriter"}:
        common_rules += (
            "- **Approval gate:** do not hand narration to voice-talent until the "
            "source-coverage matrix and script have director/requester approval.\n"
            "- Once narration is approved and recorded, route any wording change "
            "back through approval before regenerating audio.\n"
        )
    if role in {"voice-talent", "narrator"}:
        common_rules += (
            "- **Use only the approved, locked narration script.** Report any "
            "pronunciation or wording correction before recording; do not "
            "silently ad-lib or change technical terms, Rule references, or numbers.\n"
        )

    if role == "director":
        common_rules += (
            "- **Do not execute the work yourself.** For every concrete task, "
            "create a kanban task and assign it to the appropriate profile.\n"
            "- **Decompose, route, comment, approve — that's the whole job.**\n"
            "- **Read TEAM.md** for the canonical task graph. Do not invent "
            "new roles unless the brief truly demands it.\n"
        )
        if _requires_three_layer_sync(plan):
            common_rules += (
                "- **Respect the synchronization dependency gate.** Final TTS "
                "must precede captioner alignment; alignment must precede "
                "renderer timing; final caption burn follows assembly; reviewer "
                "checks all three layers. Do not start downstream timing early.\n"
            )

    common_commands = (
        "```bash\n"
        "# Inspect a clip\n"
        "ffprobe -v quiet -show_entries format=duration -show_entries "
        "stream=codec_name,width,height,r_frame_rate <file.mp4>\n"
        "\n"
        "# Extract a frame for QA\n"
        "ffmpeg -y -i <input.mp4> -vf \"select='eq(n,30)'\" -vsync vfr <out.png>\n"
        "```"
    )

    out = tmpl
    out = out.replace("{{ROLE_NAME}}", role)
    out = out.replace("{{ROLE_RESPONSIBILITIES}}", team_member["responsibilities"])
    out = out.replace("{{INPUTS_READ}}", team_member.get("inputs", "_(see brief)_"))
    out = out.replace("{{OUTPUTS_PRODUCED}}", team_member.get("outputs", "_(see brief)_"))
    out = out.replace("{{TOOLSETS}}", ", ".join(team_member["toolsets"]))
    out = out.replace(
        "{{SKILLS}}",
        ", ".join(team_member["skills"]) if team_member["skills"] else "(none)"
    )
    out = out.replace(
        "{{EXTERNAL_TOOLS}}",
        team_member.get("external_tools", "ffmpeg, ffprobe (via terminal)")
    )
    out = out.replace(
        "{{ROLE_RULES}}",
        team_member.get("role_rules", "_(see TEAM.md and brief.md)_")
    )
    out = out.replace("{{COMMON_RULES}}", common_rules)
    out = out.replace("{{COMMON_COMMANDS}}", common_commands)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan_json", help="Path to plan.json")
    ap.add_argument("--out", default="setup.sh",
                    help="Output path for setup.sh (default: ./setup.sh)")
    ap.add_argument("--brief-out", default=None,
                    help="Write brief.md alongside (default: skipped)")
    ap.add_argument("--team-out", default=None,
                    help="Write TEAM.md alongside (default: skipped)")
    args = ap.parse_args()

    plan = json.loads(Path(args.plan_json).read_text(encoding="utf-8"))
    errors = validate_plan(plan)
    if errors:
        print("Plan validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(2)

    brief = render_brief(plan)
    team = render_team_md(plan)
    setup = render_setup_sh(plan, brief, team)

    Path(args.out).write_text(setup, encoding="utf-8")
    os.chmod(args.out, 0o755)
    print(f"Wrote {args.out}")

    if args.brief_out:
        Path(args.brief_out).write_text(brief, encoding="utf-8")
        print(f"Wrote {args.brief_out}")
    if args.team_out:
        Path(args.team_out).write_text(team, encoding="utf-8")
        print(f"Wrote {args.team_out}")


if __name__ == "__main__":
    main()
