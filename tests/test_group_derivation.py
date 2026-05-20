"""Property-based tests for derive_group function.

**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**

Property 6: Group Derivation Determinism and Correctness
- For any artifact ID, derive_group() SHALL be a pure function that always returns
  the same result for the same input.
- The result SHALL be "Phase1" through "Phase5" if the ID contains the corresponding
  pattern (case-insensitive), "CodeGen" if it contains "codegen", or "Other" if no
  pattern matches.
"""

from hypothesis import given, assume, settings
from hypothesis import strategies as st

from render_dashboard import derive_group


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid group results
VALID_GROUPS = {"Phase1", "Phase2", "Phase3", "Phase4", "Phase5", "CodeGen", "Other"}

# Patterns that trigger specific groups, in priority order
PHASE_PATTERNS = ["phase1", "phase2", "phase3", "phase4", "phase5"]
PHASE_RESULTS = ["Phase1", "Phase2", "Phase3", "Phase4", "Phase5"]

# Strategy for arbitrary artifact IDs (printable strings)
artifact_ids = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S", "Z")),
    min_size=1,
    max_size=100,
)

# Strategy for IDs that contain a specific phase pattern
def id_containing(pattern: str) -> st.SearchStrategy[str]:
    """Generate IDs that contain the given pattern in any case variation."""
    # Generate a case variation of the pattern
    case_varied = st.builds(
        lambda chars: "".join(chars),
        st.tuples(*[
            st.sampled_from([c.lower(), c.upper()]) for c in pattern
        ]),
    )
    # Embed the pattern within surrounding text
    prefix = st.text(
        alphabet=st.characters(categories=("L", "N")),
        min_size=0,
        max_size=20,
    )
    suffix = st.text(
        alphabet=st.characters(categories=("L", "N")),
        min_size=0,
        max_size=20,
    )
    return st.builds(lambda p, pat, s: p + pat + s, prefix, case_varied, suffix)


# Strategy for IDs that do NOT contain any phase or codegen pattern
def id_without_patterns() -> st.SearchStrategy[str]:
    """Generate IDs that contain none of the recognized patterns."""
    # Use characters that cannot form phase1-5 or codegen
    safe_alphabet = st.sampled_from("abdfijklmqrtuvwxyz0123456789_-")
    return st.text(safe_alphabet, min_size=1, max_size=50).filter(
        lambda s: all(
            pat not in s.lower()
            for pat in PHASE_PATTERNS + ["codegen"]
        )
    )


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------

class TestGroupDerivationDeterminism:
    """Property: derive_group is a pure deterministic function."""

    @given(artifact_id=artifact_ids)
    @settings(max_examples=50)
    def test_same_input_same_output(self, artifact_id: str):
        """Calling derive_group multiple times with the same input always
        produces the same result.

        **Validates: Requirements 5.5**
        """
        result1 = derive_group(artifact_id)
        result2 = derive_group(artifact_id)
        result3 = derive_group(artifact_id)
        assert result1 == result2 == result3


class TestGroupDerivationRange:
    """Property: derive_group always returns a valid group name."""

    @given(artifact_id=artifact_ids)
    @settings(max_examples=50)
    def test_result_always_valid_group(self, artifact_id: str):
        """The result is always one of the 7 valid group names.

        **Validates: Requirements 5.1**
        """
        result = derive_group(artifact_id)
        assert result in VALID_GROUPS


class TestGroupDerivationPhaseMatching:
    """Property: IDs containing phaseN patterns map to the correct group."""

    @given(artifact_id=id_containing("phase1"))
    @settings(max_examples=30)
    def test_phase1_matching(self, artifact_id: str):
        """If ID contains 'phase1' (case-insensitive), result is 'Phase1'.

        **Validates: Requirements 5.2**
        """
        result = derive_group(artifact_id)
        assert result == "Phase1"

    @given(artifact_id=id_containing("phase2"))
    @settings(max_examples=30)
    def test_phase2_matching(self, artifact_id: str):
        """If ID contains 'phase2' (case-insensitive), result is 'Phase2'.

        **Validates: Requirements 5.2**
        """
        # phase2 contains no phase1 substring, so it should always be Phase2
        assume("phase1" not in artifact_id.lower())
        result = derive_group(artifact_id)
        assert result == "Phase2"

    @given(artifact_id=id_containing("phase3"))
    @settings(max_examples=30)
    def test_phase3_matching(self, artifact_id: str):
        """If ID contains 'phase3' (case-insensitive), result is 'Phase3'.

        **Validates: Requirements 5.2**
        """
        assume("phase1" not in artifact_id.lower())
        assume("phase2" not in artifact_id.lower())
        result = derive_group(artifact_id)
        assert result == "Phase3"

    @given(artifact_id=id_containing("phase4"))
    @settings(max_examples=30)
    def test_phase4_matching(self, artifact_id: str):
        """If ID contains 'phase4' (case-insensitive), result is 'Phase4'.

        **Validates: Requirements 5.2**
        """
        assume("phase1" not in artifact_id.lower())
        assume("phase2" not in artifact_id.lower())
        assume("phase3" not in artifact_id.lower())
        result = derive_group(artifact_id)
        assert result == "Phase4"

    @given(artifact_id=id_containing("phase5"))
    @settings(max_examples=30)
    def test_phase5_matching(self, artifact_id: str):
        """If ID contains 'phase5' (case-insensitive), result is 'Phase5'.

        **Validates: Requirements 5.2**
        """
        assume("phase1" not in artifact_id.lower())
        assume("phase2" not in artifact_id.lower())
        assume("phase3" not in artifact_id.lower())
        assume("phase4" not in artifact_id.lower())
        result = derive_group(artifact_id)
        assert result == "Phase5"


class TestGroupDerivationCodeGen:
    """Property: IDs containing 'codegen' but no phaseN map to 'CodeGen'."""

    @given(artifact_id=id_containing("codegen"))
    @settings(max_examples=30)
    def test_codegen_matching(self, artifact_id: str):
        """If ID contains 'codegen' (case-insensitive) but no phaseN pattern,
        result is 'CodeGen'.

        **Validates: Requirements 5.3**
        """
        assume(all(
            f"phase{i}" not in artifact_id.lower() for i in range(1, 6)
        ))
        result = derive_group(artifact_id)
        assert result == "CodeGen"


class TestGroupDerivationOther:
    """Property: IDs without any recognized pattern map to 'Other'."""

    @given(artifact_id=id_without_patterns())
    @settings(max_examples=50)
    def test_no_pattern_returns_other(self, artifact_id: str):
        """If ID contains none of the recognized patterns, result is 'Other'.

        **Validates: Requirements 5.4**
        """
        result = derive_group(artifact_id)
        assert result == "Other"


class TestGroupDerivationPriority:
    """Property: When multiple patterns match, priority order determines result."""

    @given(
        prefix=st.text(
            alphabet=st.characters(categories=("L", "N")),
            min_size=0,
            max_size=10,
        ),
        suffix=st.text(
            alphabet=st.characters(categories=("L", "N")),
            min_size=0,
            max_size=10,
        ),
    )
    @settings(max_examples=30)
    def test_phase1_beats_codegen(self, prefix: str, suffix: str):
        """If ID contains both 'phase1' and 'codegen', 'Phase1' wins.

        **Validates: Requirements 5.1 (priority order)**
        """
        artifact_id = f"{prefix}phase1{suffix}codegen"
        result = derive_group(artifact_id)
        assert result == "Phase1"

    @given(
        prefix=st.text(
            alphabet=st.characters(categories=("L", "N")),
            min_size=0,
            max_size=10,
        ),
        suffix=st.text(
            alphabet=st.characters(categories=("L", "N")),
            min_size=0,
            max_size=10,
        ),
    )
    @settings(max_examples=30)
    def test_phase1_beats_phase2(self, prefix: str, suffix: str):
        """If ID contains both 'phase1' and 'phase2', 'Phase1' wins.

        **Validates: Requirements 5.1 (priority order)**
        """
        artifact_id = f"{prefix}phase1{suffix}phase2"
        result = derive_group(artifact_id)
        assert result == "Phase1"

    @given(
        prefix=st.text(
            alphabet=st.characters(categories=("L", "N")),
            min_size=0,
            max_size=10,
        ),
    )
    @settings(max_examples=30)
    def test_phase2_beats_codegen(self, prefix: str):
        """If ID contains both 'phase2' and 'codegen' but not 'phase1',
        'Phase2' wins.

        **Validates: Requirements 5.1 (priority order)**
        """
        artifact_id = f"{prefix}phase2codegen"
        assume("phase1" not in artifact_id.lower())
        result = derive_group(artifact_id)
        assert result == "Phase2"


class TestGroupDerivationCaseInsensitivity:
    """Property: Matching is case-insensitive."""

    @given(
        case_bits=st.tuples(*[st.booleans() for _ in range(6)]),
        prefix=st.text(
            alphabet=st.characters(categories=("L", "N")),
            min_size=0,
            max_size=10,
        ),
    )
    @settings(max_examples=50)
    def test_phase1_case_insensitive(self, case_bits: tuple, prefix: str):
        """'PHASE1', 'Phase1', 'pHaSe1' all produce 'Phase1'.

        **Validates: Requirements 5.2 (case-insensitive)**
        """
        pattern = "phase1"
        varied = "".join(
            c.upper() if bit else c.lower()
            for c, bit in zip(pattern, case_bits)
        )
        artifact_id = prefix + varied
        assume("phase1" in artifact_id.lower())
        # Ensure no higher-priority pattern accidentally formed by prefix
        # (phase1 is highest priority, so this is always safe)
        result = derive_group(artifact_id)
        assert result == "Phase1"


class TestGroupDerivationExplicitField:
    """Tests for explicit group field taking priority over ID matching."""

    def test_explicit_group_field_takes_priority(self):
        """When artifact dict has a non-empty 'group' field, it is returned directly."""
        artifact = {"id": "Plan.Phase1-Something", "group": "CustomGroup"}
        result = derive_group(artifact)
        assert result == "CustomGroup"

    def test_empty_group_field_falls_back_to_id(self):
        """When artifact dict has group='', falls back to ID matching."""
        artifact = {"id": "Plan.Phase1-Something", "group": ""}
        result = derive_group(artifact)
        assert result == "Phase1"

    def test_missing_group_field_falls_back_to_id(self):
        """When artifact dict has no 'group' key, falls back to ID matching."""
        artifact = {"id": "Plan.Phase2-Registry"}
        result = derive_group(artifact)
        assert result == "Phase2"

    def test_string_input_backward_compat(self):
        """Passing a plain string still works (backward compat)."""
        result = derive_group("Plan.Phase3-Fragment")
        assert result == "Phase3"

    def test_explicit_group_overrides_phase_keyword(self):
        """Explicit group wins even when ID contains a phase keyword."""
        artifact = {"id": "Plan.Phase1-BitStream", "group": "CodeGen"}
        result = derive_group(artifact)
        assert result == "CodeGen"

    def test_no_id_no_group_returns_other(self):
        """Artifact with no id and no group returns 'Other'."""
        artifact = {"id": "", "group": ""}
        result = derive_group(artifact)
        assert result == "Other"

    @given(group_name=st.text(min_size=1, max_size=30).filter(lambda s: s.strip()))
    @settings(max_examples=30)
    def test_any_nonempty_group_returned_directly(self, group_name: str):
        """Any non-empty group string is returned as-is."""
        artifact = {"id": "anything", "group": group_name}
        result = derive_group(artifact)
        assert result == group_name
