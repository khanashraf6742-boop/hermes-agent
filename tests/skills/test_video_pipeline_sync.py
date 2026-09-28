"""Tests for the three-layer audio/subtitle/visual synchronization gate."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "optional-skills/creative/kanban-video-orchestrator/scripts/bootstrap_pipeline.py"
SPEC = importlib.util.spec_from_file_location("video_pipeline_bootstrap", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)

VALIDATOR_PATH = REPO / "optional-skills/creative/kanban-video-orchestrator/scripts/validate_sync_timeline.py"
VALIDATOR_SPEC = importlib.util.spec_from_file_location("video_pipeline_sync_validator", VALIDATOR_PATH)
assert VALIDATOR_SPEC is not None and VALIDATOR_SPEC.loader is not None
validator = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(validator)


def _member(profile: str, role: str, *, skills: list[str] | None = None) -> dict:
    return {
        "profile": profile,
        "role": role,
        "toolsets": ["kanban", "terminal", "file"],
        "skills": skills or [],
        "responsibilities": f"Handle {role} work.",
    }


def _sync_plan() -> dict:
    return {
        "title": "Narrated explainer",
        "slug": "narrated-explainer",
        "tenant": "narrated-explainer",
        "duration_s": 60,
        "aspect": "9:16",
        "resolution": "1080x1920",
        "fps": 30,
        "three_layer_sync": True,
        "team": [
            _member("director", "director"),
            _member("writer", "writer"),
            _member("cinematographer", "cinematographer"),
            _member("voice-talent", "voice-talent"),
            _member("renderer-manim", "renderer-manim", skills=["manim-video"]),
            _member("captioner", "captioner"),
            _member("editor", "editor"),
            _member("reviewer", "reviewer"),
        ],
        "scenes": [
            {"n": 1, "time": "0:00-0:10", "content": "Explain the first condition", "tool": "renderer-manim"},
        ],
        "audio": {"approach": "TTS narration", "vo": "Authorized stock voice", "music": "n/a", "sfx": "n/a"},
        "deliverables": [{"format": "mp4", "resolution": "1080x1920", "notes": "main"}],
    }


class ThreeLayerSyncBootstrapTests(unittest.TestCase):
    def test_sync_plan_requires_captioner_and_voice_source(self):
        plan = _sync_plan()
        self.assertEqual(bootstrap.validate_plan(plan), [])
        self.assertIn("plan must be a JSON object", bootstrap.validate_plan([]))

        malformed_team = copy.deepcopy(plan)
        malformed_team["team"][0] = None
        self.assertTrue(any("team[0] must be an object" in error for error in bootstrap.validate_plan(malformed_team)))

        no_captioner = copy.deepcopy(plan)
        no_captioner["team"] = [member for member in no_captioner["team"] if member["role"] != "captioner"]
        self.assertTrue(any("requires a captioner role" in error for error in bootstrap.validate_plan(no_captioner)))

        no_voice = copy.deepcopy(plan)
        no_voice["team"] = [member for member in no_voice["team"] if member["role"] != "voice-talent"]
        no_voice["audio"]["vo"] = "n/a"
        self.assertTrue(any("requires a voice-talent profile or audio.vo source" in error for error in bootstrap.validate_plan(no_voice)))

    def test_sync_task_graph_aligns_audio_before_render_and_burns_after_edit(self):
        graph = bootstrap.render_team_md(_sync_plan())
        align = graph.index("captioner — transcribe/force-align locked voice")
        renderer = graph.index("renderer-manim — scene 1")
        editor = graph.index("editor — assemble + mux")
        burn = graph.index("captioner — burn the reviewed captions.srt")
        reviewer = graph.index("reviewer — final QA + delivery gate")

        self.assertLess(align, renderer)
        self.assertLess(renderer, editor)
        self.assertLess(editor, burn)
        self.assertLess(burn, reviewer)
        self.assertIn("audio/sync-timeline.json", graph)
        self.assertIn("output/captions.srt", graph)
        self.assertIn("(parent: T3)", graph)
        self.assertIn("(parents: T2, T1, T4)", graph)
        self.assertIn("(parents: T6, T4)", graph)
        self.assertIn("master clock", graph)

    def test_voice_and_captioner_roles_enable_alignment_without_explicit_flag(self):
        plan = _sync_plan()
        plan.pop("three_layer_sync")
        self.assertIn("captioner — transcribe/force-align locked voice", bootstrap.render_team_md(plan))

    def test_generated_profiles_receive_sync_contract(self):
        plan = _sync_plan()
        director = bootstrap.render_soul_md(plan["team"][0], plan)
        writer = bootstrap.render_soul_md(plan["team"][1], plan)
        voice_talent = bootstrap.render_soul_md(plan["team"][3], plan)
        renderer = bootstrap.render_soul_md(plan["team"][4], plan)
        self.assertIn("director/requester approval", writer)
        self.assertIn("approved, locked narration script", voice_talent)
        self.assertIn("final voice audio is the master clock", director)
        self.assertIn("synchronization dependency gate", director)
        self.assertIn("For teaching explainers, keep the canvas continuous", renderer)
        self.assertIn("audio/sync-timeline.json", renderer)
        self.assertIn("tools/validate_sync_timeline.py", renderer)
        self.assertIn("Do not approve or deliver a mismatch", renderer)

    def test_brief_names_the_master_timeline_requirement(self):
        plan = _sync_plan()
        brief = bootstrap.render_brief(plan)
        self.assertIn("Three-layer synchronization", brief)
        self.assertIn("MANDATORY", brief)

    def test_generated_setup_embeds_sync_contract_and_shared_timeline(self):
        plan = _sync_plan()
        brief = bootstrap.render_brief(plan)
        team = bootstrap.render_team_md(plan)
        setup = bootstrap.render_setup_sh(plan, brief, team)
        self.assertIn("audio/sync-timeline.json", setup)
        self.assertIn("final voice audio is the master clock", setup)
        self.assertIn('cat > "$WORKSPACE/tools/sync-timeline.schema.json"', setup)
        self.assertIn('cat > "$WORKSPACE/tools/validate_sync_timeline.py"', setup)
        self.assertIn("def _validate_srt", setup)
        self.assertIn("--srt output/captions.srt", setup)
        self.assertIn('cat > "$WORKSPACE/tools/sync-timeline.example.json"', setup)
        self.assertEqual(setup.count("SYNC_SCHEMA_EOF"), 2)
        self.assertEqual(setup.count("SYNC_EXAMPLE_EOF"), 2)
        self.assertEqual(setup.count("SYNC_VALIDATOR_EOF"), 2)
        self.assertNotIn("{{THREE_LAYER_SYNC}}", setup)
        self.assertNotIn("{{SYNC_TOOL_INSTALL}}", setup)

    def test_sync_timeline_validator_checks_alignment_and_audio_fingerprint(self):
        example = REPO / "optional-skills/creative/kanban-video-orchestrator/assets/sync-timeline.example.json"
        timeline = json.loads(example.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp_dir:
            audio = Path(temp_dir) / "final.mp3"
            srt = Path(temp_dir) / "captions.srt"
            audio.write_bytes(b"locked final narration")
            srt.write_text(
                chr(10).join(["1", "00:00:00,200 --> 00:00:02,550", "The maximum", "period is three hundred days.", ""]),
                encoding="utf-8",
            )
            timeline["audio_master"]["sha256"] = hashlib.sha256(audio.read_bytes()).hexdigest()
            self.assertEqual([], validator.validate_timeline(timeline, audio_path=audio, srt_path=srt))

            sentence_level = copy.deepcopy(timeline)
            sentence_level["alignment_units"] = [
                {
                    "id": "a001",
                    "granularity": "sentence",
                    "start_s": 0.20,
                    "end_s": 2.40,
                    "text": "The maximum period is three hundred days.",
                    "concept_id": "maximum-period",
                }
            ]
            sentence_level["captions"][0]["alignment_ids"] = ["a001"]
            for event in sentence_level["visual_events"]:
                event["anchor_alignment_ids"] = ["a001"]
            self.assertEqual([], validator.validate_timeline(sentence_level))

            incomplete = copy.deepcopy(timeline)
            incomplete["captions"][0]["alignment_ids"].pop()
            errors = validator.validate_timeline(incomplete)
            self.assertTrue(any("missing subtitle coverage" in error for error in errors))

            dense = copy.deepcopy(timeline)
            dense["captions"][0]["text"] = "Uncomfortably dense caption " * 8
            errors = validator.validate_timeline(dense)
            self.assertTrue(any("too dense" in error for error in errors))

            mismatched_srt = Path(temp_dir) / "wrong-captions.srt"
            mismatched_srt.write_text(
                chr(10).join(["1", "00:00:00,200 --> 00:00:02,550", "A different sentence.", ""]),
                encoding="utf-8",
            )
            errors = validator.validate_timeline(timeline, audio_path=audio, srt_path=mismatched_srt)
            self.assertTrue(any("text differs" in error for error in errors))

            stale = copy.deepcopy(timeline)
            stale["audio_master"]["sha256"] = "0" * 64
            errors = validator.validate_timeline(stale, audio_path=audio)
            self.assertTrue(any("fingerprint mismatch" in error for error in errors))

            premature = copy.deepcopy(timeline)
            premature["visual_events"][1]["start_s"] = 0.2
            errors = validator.validate_timeline(premature, audio_path=audio)
            self.assertTrue(any("before its spoken anchor" in error for error in errors))

            late = copy.deepcopy(timeline)
            late["visual_events"][1]["start_s"] = 3.6
            late["visual_events"][1]["end_s"] = 3.9
            errors = validator.validate_timeline(late, audio_path=audio)
            self.assertTrue(any("after its spoken anchor" in error for error in errors))

    def test_silent_captioned_plan_does_not_create_voice_alignment_task(self):
        plan = _sync_plan()
        plan.pop("three_layer_sync")
        plan["team"] = [member for member in plan["team"] if member["role"] != "voice-talent"]
        plan["audio"]["approach"] = "silent"
        plan["audio"]["vo"] = "n/a"
        graph = bootstrap.render_team_md(plan)
        self.assertNotIn("transcribe/force-align locked voice", graph)
        self.assertNotIn("Three-layer synchronization contract", graph)
        self.assertIn("captioner — generate requested captions + burn after assembly", graph)
        setup = bootstrap.render_setup_sh(plan, bootstrap.render_brief(plan), graph)
        self.assertNotIn('cat > "$WORKSPACE/tools/validate_sync_timeline.py"', setup)


if __name__ == "__main__":
    unittest.main()
