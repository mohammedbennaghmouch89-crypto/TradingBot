"""Validation tests for the ICT skill (`.claude/skills/ict/`).

This skill is documentation, not executable code, so these tests guard its
*structural integrity* rather than trading behavior: that the skill is a valid
Claude Code skill (parseable frontmatter), that its reference files exist, that
the in-document links are not broken, and that a few load-bearing conventions are
actually present. They use only the standard library, so they pass in CI even
when third-party packages cannot be installed. See ``docs/TESTING.md``.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "ict"
SKILL_MD = SKILL_DIR / "SKILL.md"

REQUIRED_REFERENCES = (
    "reference/market-structure-and-liquidity.md",
    "reference/pd-arrays.md",
    "reference/time-and-price.md",
    "reference/entry-models-and-theory.md",
)

# Matches a leading YAML frontmatter block: ---\n ... \n---
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
# Matches markdown links: [text](target)
_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _frontmatter(text: str) -> str:
    """Return the raw YAML frontmatter block of ``text`` (without the fences)."""
    match = _FRONTMATTER_RE.match(text)
    assert match is not None, "SKILL.md must start with a '---' YAML frontmatter block"
    return match.group(1)


def test_skill_md_exists() -> None:
    """The skill entry point ``SKILL.md`` must exist.

    Without it the directory is not a recognizable Claude Code skill and would
    never load.
    """
    assert SKILL_MD.is_file(), f"missing {SKILL_MD}"


def test_frontmatter_has_name_and_description() -> None:
    """Frontmatter must declare both ``name`` and ``description`` keys.

    These are the two fields the skill loader uses to register the skill and to
    decide when to surface it; a missing key silently breaks discovery.
    """
    fm = _frontmatter(SKILL_MD.read_text(encoding="utf-8"))
    assert re.search(r"^name:\s*\S+", fm, re.MULTILINE), "frontmatter missing 'name'"
    assert re.search(r"^description:\s*\S", fm, re.MULTILINE), "frontmatter missing 'description'"


def test_skill_name_is_ict() -> None:
    """The skill's ``name`` must be exactly ``ict``.

    The name is how the skill is invoked/referenced; pinning it prevents an
    accidental rename from detaching the skill from anything that calls it.
    """
    fm = _frontmatter(SKILL_MD.read_text(encoding="utf-8"))
    name_match = re.search(r"^name:\s*(\S+)", fm, re.MULTILINE)
    assert name_match is not None and name_match.group(1) == "ict"


def test_required_reference_files_exist() -> None:
    """All four reference files referenced by the skill must be present.

    SKILL.md is an index that delegates detail to these files; a missing one
    means a dead end for any concept it documents.
    """
    for rel in REQUIRED_REFERENCES:
        assert (SKILL_DIR / rel).is_file(), f"missing reference file: {rel}"


def test_skill_md_relative_links_resolve() -> None:
    """Every relative markdown link in SKILL.md must point to a real file.

    Catches typos and renames that would otherwise leave the skill's navigation
    broken. External (http) and anchor-only (#...) links are skipped.
    """
    text = SKILL_MD.read_text(encoding="utf-8")
    for target in _LINK_RE.findall(text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        path_part = target.split("#", 1)[0]  # strip any #anchor
        if not path_part:
            continue
        resolved = (SKILL_DIR / path_part).resolve()
        assert resolved.is_file(), f"broken link in SKILL.md -> {target}"


def test_reference_files_are_nonempty_and_cite_sources() -> None:
    """Each reference file must be substantial and include a Sources section.

    Sourcing makes the ICT claims auditable (the content was researched, not
    invented); a near-empty file would signal a botched write.
    """
    for rel in REQUIRED_REFERENCES:
        content = (SKILL_DIR / rel).read_text(encoding="utf-8")
        assert len(content) > 1000, f"{rel} looks too small to be complete"
        assert "## Sources" in content, f"{rel} missing a '## Sources' section"


def test_key_conventions_documented() -> None:
    """SKILL.md must keep the load-bearing implementation conventions.

    These specific rules (NY timezone, close-vs-wick break, the OTE focal level)
    are the ones most likely to cause indicator/chart mismatches if dropped, so
    we assert they remain documented.
    """
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "America/New_York" in text, "timezone convention missing"
    assert "useCloseForBreak" in text, "close-vs-wick break convention missing"
    assert "0.705" in text, "OTE focal fib level missing"
