"""Tests for gleplot.parser.metadata: the ``! gleplot:`` comment block
(Track A2). Pure module tests only -- not wired into GLEWriter yet.
"""

import pytest

from gleplot.parser import metadata as md


class TestEmitMetadata:
    def test_empty_dict_emits_nothing(self):
        assert md.emit_metadata({}) == []

    def test_all_defaults_still_emits_dpi_and_import_data(self):
        data = {"dpi": 100, "sharex": False, "sharey": False,
                "msize_scale": 1.0, "import-data": []}
        lines = md.emit_metadata(data)
        assert lines[0] == "! gleplot-meta-begin v1"
        assert lines[-1] == "! gleplot-meta-end"
        assert "! gleplot: dpi = 100" in lines
        assert "! gleplot: import-data = " in lines
        # Defaults omitted.
        assert not any("sharex" in line for line in lines)
        assert not any("sharey" in line for line in lines)
        assert not any("msize_scale" in line for line in lines)

    def test_documented_example_format(self):
        data = {
            "dpi": 100,
            "sharex": False,
            "sharey": False,
            "msize_scale": 1.0,
            "import-data": ["data_0.dat", "data_1.dat"],
        }
        lines = md.emit_metadata(data)
        assert lines == [
            "! gleplot-meta-begin v1",
            "! gleplot: dpi = 100",
            "! gleplot: import-data = data_0.dat, data_1.dat",
            "! gleplot-meta-end",
        ]

    def test_non_default_values_emitted(self):
        data = {"dpi": 150, "sharex": True, "sharey": True, "msize_scale": 2.5}
        lines = md.emit_metadata(data)
        assert "! gleplot: dpi = 150" in lines
        assert "! gleplot: sharex = true" in lines
        assert "! gleplot: sharey = true" in lines
        assert "! gleplot: msize_scale = 2.5" in lines

    def test_float_with_integral_value_keeps_decimal_point(self):
        lines = md.emit_metadata({"dpi": 100, "msize_scale": 2.0})
        assert "! gleplot: msize_scale = 2.0" in lines

    def test_unknown_key_emitted_verbatim(self):
        lines = md.emit_metadata({"dpi": 100, "future_flag": "hello"})
        assert "! gleplot: future_flag = hello" in lines

    def test_import_data_always_emitted_even_when_empty(self):
        lines = md.emit_metadata({"dpi": 100, "import-data": []})
        assert "! gleplot: import-data = " in lines


class TestParseMetadata:
    def test_no_block_returns_empty(self):
        data, warnings = md.parse_metadata(["begin graph", "  xtitle \"x\"", "end graph"])
        assert data == {}
        assert warnings == []

    def test_round_trip_documented_example(self):
        lines = [
            "! gleplot-meta-begin v1",
            "! gleplot: dpi = 100",
            "! gleplot: sharex = false",
            "! gleplot: sharey = false",
            "! gleplot: msize_scale = 1.0",
            "! gleplot: import-data = data_0.dat, data_1.dat",
            "! gleplot-meta-end",
        ]
        data, warnings = md.parse_metadata(lines)
        assert warnings == []
        assert data == {
            "dpi": 100,
            "sharex": False,
            "sharey": False,
            "msize_scale": 1.0,
            "import-data": ["data_0.dat", "data_1.dat"],
        }
        assert isinstance(data["dpi"], int)
        assert isinstance(data["msize_scale"], float)
        assert isinstance(data["sharex"], bool)

    def test_block_embedded_in_larger_file(self):
        lines = [
            "! GLE graphics file",
            "size 20.32 15.24",
            "! gleplot-meta-begin v1",
            "! gleplot: dpi = 200",
            "! gleplot-meta-end",
            "",
            "begin graph",
            "end graph",
        ]
        data, warnings = md.parse_metadata(lines)
        assert data == {"dpi": 200}
        assert warnings == []

    def test_malformed_lines_skipped_with_warnings(self):
        lines = [
            "! gleplot-meta-begin v1",
            "! gleplot: dpi = 100",
            "! gleplot: nomatchhere",
            "! not-a-gleplot-line-at-all",
            "! gleplot: = novalue",
            "! gleplot-meta-end",
        ]
        data, warnings = md.parse_metadata(lines)
        assert data == {"dpi": 100}
        assert len(warnings) == 3

    def test_unknown_keys_preserved(self):
        lines = [
            "! gleplot-meta-begin v1",
            "! gleplot: dpi = 100",
            "! gleplot: some_future_key = 42",
            "! gleplot-meta-end",
        ]
        data, warnings = md.parse_metadata(lines)
        assert data["some_future_key"] == 42
        assert warnings == []

    def test_empty_import_data_parses_to_empty_list(self):
        lines = [
            "! gleplot-meta-begin v1",
            "! gleplot: import-data = ",
            "! gleplot-meta-end",
        ]
        data, warnings = md.parse_metadata(lines)
        assert data["import-data"] == []

    def test_import_data_with_whitespace_around_commas(self):
        lines = [
            "! gleplot-meta-begin v1",
            "! gleplot: import-data = a.dat,  b.dat ,c.dat",
            "! gleplot-meta-end",
        ]
        data, warnings = md.parse_metadata(lines)
        assert data["import-data"] == ["a.dat", "b.dat", "c.dat"]

    def test_only_first_block_parsed_when_multiple_present(self):
        lines = [
            "! gleplot-meta-begin v1",
            "! gleplot: dpi = 100",
            "! gleplot-meta-end",
            "! gleplot-meta-begin v1",
            "! gleplot: dpi = 999",
            "! gleplot-meta-end",
        ]
        data, warnings = md.parse_metadata(lines)
        assert data == {"dpi": 100}

    def test_unrecognized_version_marker_warns_but_still_parses(self):
        lines = [
            "! gleplot-meta-begin v2",
            "! gleplot: dpi = 100",
            "! gleplot-meta-end",
        ]
        data, warnings = md.parse_metadata(lines)
        assert data == {"dpi": 100}
        assert len(warnings) == 1
        assert "version" in warnings[0].lower()

    def test_bool_parsing_case_insensitive(self):
        lines = [
            "! gleplot-meta-begin v1",
            "! gleplot: sharex = TRUE",
            "! gleplot: sharey = False",
            "! gleplot-meta-end",
        ]
        data, _ = md.parse_metadata(lines)
        assert data["sharex"] is True
        assert data["sharey"] is False

    def test_missing_end_marker_still_parses_lines_seen(self):
        lines = [
            "! gleplot-meta-begin v1",
            "! gleplot: dpi = 100",
        ]
        data, warnings = md.parse_metadata(lines)
        assert data == {"dpi": 100}


class TestEmitParseRoundTrip:
    @pytest.mark.parametrize("data", [
        {"dpi": 100, "import-data": []},
        {"dpi": 150, "sharex": True, "import-data": []},
        {"dpi": 100, "sharex": True, "sharey": True, "msize_scale": 0.75,
         "import-data": ["x.dat", "y.dat", "z.dat"]},
        {"dpi": 300, "import-data": ["only.dat"]},
    ])
    def test_emit_then_parse_recovers_non_default_data(self, data):
        lines = md.emit_metadata(data)
        parsed, warnings = md.parse_metadata(lines)
        assert warnings == []
        assert parsed == data

    def test_absent_optional_keys_apply_documented_defaults(self):
        # A caller applying DEFAULTS as fallback recovers the full picture
        # even though only non-default keys were emitted.
        data = {"dpi": 100, "sharex": True}
        lines = md.emit_metadata(data)
        parsed, _ = md.parse_metadata(lines)
        merged = dict(md.DEFAULTS)
        merged.update(parsed)
        assert merged["sharey"] is False
        assert merged["msize_scale"] == 1.0
        assert merged["sharex"] is True


class TestListQuoting:
    """MA-review fix: comma/quote-containing filenames survive round-trip."""

    def test_comma_in_filename_roundtrips(self):
        from gleplot.parser.metadata import emit_metadata, parse_metadata
        names = ["my, file.dat", "other.dat"]
        lines = emit_metadata({"dpi": 100, "import-data": names})
        parsed, warnings = parse_metadata(lines)
        assert parsed["import-data"] == names

    def test_quote_in_filename_roundtrips(self):
        from gleplot.parser.metadata import emit_metadata, parse_metadata
        names = ['weird "name".dat', "plain.dat", "a, b, c.dat"]
        lines = emit_metadata({"dpi": 100, "import-data": names})
        parsed, _ = parse_metadata(lines)
        assert parsed["import-data"] == names

    def test_unquoted_lists_still_parse(self):
        from gleplot.parser.metadata import parse_metadata
        parsed, _ = parse_metadata(
            ["! gleplot-meta-begin v1",
             "! gleplot: import-data = data_0.dat, data_1.dat",
             "! gleplot-meta-end"]
        )
        assert parsed["import-data"] == ["data_0.dat", "data_1.dat"]
