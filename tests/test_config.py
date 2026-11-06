import pytest
from ps_cli.config import ConfigError, load_credentials


def write(tmp_path, text, mode=0o600):
    d = tmp_path / ".powersched"
    d.mkdir()
    f = d / ".env"
    f.write_text(text)
    f.chmod(mode)
    return d / ".env"


def test_legacy_two_line_with_url_from_env(tmp_path):
    p = write(tmp_path, "parent1\nsecretpw\n")
    c = load_credentials({"PS_BASE_URL": "https://d.powerschool.com"}, p)
    assert (c.username, c.password) == ("parent1", "secretpw")
    assert c.base_url == "https://d.powerschool.com"


def test_base_url_is_required_no_default(tmp_path):
    p = write(tmp_path, "parent1\nsecretpw\n")
    with pytest.raises(ConfigError) as ei:
        load_credentials({}, p)
    msg = str(ei.value)
    assert "PS_BASE_URL" in msg and "powerschool.com" in msg
    assert "secretpw" not in msg and "parent1" not in msg


def test_no_hardcoded_district_in_package():
    import pathlib
    import ps_cli
    root = pathlib.Path(ps_cli.__file__).parent
    assert not [f for f in root.rglob("*.py") if ("arlington" + "diocese") in f.read_text().lower()]


def test_key_value_with_quotes_and_comments(tmp_path):
    p = write(tmp_path, '# c\nPS_USERNAME="u"\nPS_PASSWORD=\'p w\'\nPS_BASE_URL=https://x.powerschool.com/\n')
    c = load_credentials({}, p)
    assert (c.username, c.password, c.base_url) == ("u", "p w", "https://x.powerschool.com")


def test_env_priority(tmp_path):
    p = write(tmp_path, "fileu\nfilep\n")
    c = load_credentials({"PS_USERNAME": "eu", "PS_PASSWORD": "ep", "PS_BASE_URL": "https://d.powerschool.com"}, p)
    assert (c.username, c.password) == ("eu", "ep")


def test_env_only_no_file(tmp_path):
    c = load_credentials({"PS_USERNAME": "a", "PS_PASSWORD": "b", "PS_BASE_URL": "https://d.powerschool.com"}, tmp_path / "none")
    assert c.username == "a"


def test_missing_raises_without_secrets(tmp_path):
    with pytest.raises(ConfigError) as e:
        load_credentials({}, tmp_path / "none")
    assert "PS_USERNAME" in str(e.value)


def test_repr_hides_password(tmp_path):
    p = write(tmp_path, "parent1\nsecretpw\n")
    c = load_credentials({"PS_BASE_URL": "https://d.powerschool.com"}, p)
    assert "secretpw" not in repr(c) and "secretpw" not in str(c)


def test_perm_warning(tmp_path, caplog):
    p = write(tmp_path, "u\nsecretpw\n", 0o644)
    with caplog.at_level("WARNING"):
        load_credentials({"PS_BASE_URL": "https://d.powerschool.com"}, p)
    assert "600" in caplog.text and "secretpw" not in caplog.text


def test_malformed_file_error_has_no_secret(tmp_path):
    p = write(tmp_path, "onlyonesecretline\n")
    with pytest.raises(ConfigError) as e:
        load_credentials({}, p)
    assert "onlyonesecretline" not in str(e.value)


@pytest.mark.parametrize("url", [
    "http://a.powerschool.com", "https://evilpowerschool.com",
    "https://x.powerschool.com.evil.io", "https://powerschool.com.evil.io/",
    "https://evil.io/@a.powerschool.com", "ftp://a.powerschool.com", "a.powerschool.com"])
def test_bad_base_url_rejected(url, tmp_path):
    with pytest.raises(ConfigError) as e:
        load_credentials({"PS_USERNAME": "u", "PS_PASSWORD": "pw9", "PS_BASE_URL": url},
                         tmp_path / "none")
    assert "pw9" not in str(e.value)


def test_allowed_host_escape_hatch(tmp_path):
    c = load_credentials({"PS_USERNAME": "u", "PS_PASSWORD": "p",
                          "PS_BASE_URL": "https://portal.example.org",
                          "PS_ALLOWED_HOST": "portal.example.org"}, tmp_path / "none")
    assert c.host == "portal.example.org"


def test_allowed_host_must_match_exactly(tmp_path):
    with pytest.raises(ConfigError):
        load_credentials({"PS_USERNAME": "u", "PS_PASSWORD": "p",
                          "PS_BASE_URL": "https://evil.example.org",
                          "PS_ALLOWED_HOST": "portal.example.org"}, tmp_path / "none")


def test_foreign_owner_warns(tmp_path, caplog, monkeypatch):
    p = write(tmp_path, "u\npw\n")
    monkeypatch.setattr("ps_cli.config.os.getuid", lambda: p.stat().st_uid + 1)
    with caplog.at_level("WARNING"):
        load_credentials({"PS_BASE_URL": "https://d.powerschool.com"}, p)
    assert "owned by another user" in caplog.text
