"""Unit tests for filegetter.common."""

from filegetter.common import get_dict_value, sanitize_filename


class TestGetDictValue:
    def test_simple_key(self):
        assert get_dict_value({"a": 1}, "a") == 1

    def test_missing_key_returns_none(self):
        assert get_dict_value({"a": 1}, "b") is None

    def test_nested_key(self):
        data = {"a": {"b": {"c": 42}}}
        assert get_dict_value(data, "a.b.c") == 42

    def test_nested_missing_returns_none(self):
        assert get_dict_value({"a": {"b": 1}}, "a.x.y") is None

    def test_list_of_dicts_first_match(self):
        data = {"items": [{"id": 1}, {"id": 2}]}
        assert get_dict_value(data, "items.id") == 1

    def test_list_of_dicts_as_array(self):
        data = {"items": [{"id": 1}, {"id": 2}]}
        assert get_dict_value(data, "items.id", as_array=True) == [1, 2]

    def test_dotted_key_in_list_of_lists(self):
        data = {"rows": [{"files": [{"url": "a"}, {"url": "b"}]}]}
        assert get_dict_value(data, "rows.files.url", as_array=True) == ["a", "b"]

    def test_missing_key_in_some_list_items(self):
        data = {"items": [{"id": 1}, {"name": "x"}, {"id": 3}]}
        assert get_dict_value(data, "items.id", as_array=True) == [1, 3]

    def test_custom_splitter(self):
        assert get_dict_value({"a": {"b": 5}}, "a:b", splitter=":") == 5

    def test_null_value_preserved(self):
        assert get_dict_value({"a": None}, "a") is None
        assert get_dict_value({"a": None}, "a", as_array=True) == [None]

    def test_non_dict_input(self):
        assert get_dict_value("scalar", "a") is None


class TestSanitizeFilename:
    def test_strips_leading_slash(self):
        assert sanitize_filename("/file1.pdf") == "file1.pdf"

    def test_strips_all_leading_slashes(self):
        assert sanitize_filename("//a//b.txt") == "a/b.txt"

    def test_preserves_subdirectories(self):
        assert sanitize_filename("/images/original/327671") == "images/original/327671"

    def test_drops_dot_segments(self):
        assert sanitize_filename("/a/./b") == "a/b"

    def test_drops_parent_segments(self):
        # '..' must never escape the storage root
        assert sanitize_filename("/../../etc/passwd") == "etc/passwd"

    def test_backslashes_converted(self):
        assert sanitize_filename("\\a\\b.txt") == "a/b.txt"

    def test_empty_name(self):
        assert sanitize_filename("/") == ""
        assert sanitize_filename("///") == ""
