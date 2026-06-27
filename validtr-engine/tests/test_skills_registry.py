"""Tests for recommender/skills_registry.py — catalog config and path matching."""

from recommender.skills_registry import CATALOGS, _matches_skills_path


class TestMatchesSkillsPath:
    def test_matches_under_fixed_prefix(self):
        assert _matches_skills_path("skills/foo/SKILL.md", "skills")

    def test_rejects_outside_fixed_prefix(self):
        assert not _matches_skills_path("docs/foo/SKILL.md", "skills")

    def test_none_matches_any_path(self):
        # pm-skills nests SKILL.md under per-plugin folders, e.g.
        # "product-management/skills/foo/SKILL.md" — there's no single shared root.
        assert _matches_skills_path("product-management/skills/foo/SKILL.md", None)
        assert _matches_skills_path("anything/at/all/SKILL.md", None)


class TestCatalogs:
    def test_pm_skills_catalog_present(self):
        sources = {c["source"] for c in CATALOGS}
        assert "pm-skills" in sources

    def test_pm_skills_uses_unbounded_path(self):
        pm = next(c for c in CATALOGS if c["source"] == "pm-skills")
        assert pm["skills_path"] is None
        assert pm["owner"] == "phuryn"
        assert pm["repo"] == "pm-skills"

    def test_all_catalogs_have_required_keys(self):
        for catalog in CATALOGS:
            assert {"owner", "repo", "skills_path", "source"} <= catalog.keys()
