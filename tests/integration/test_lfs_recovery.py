"""Regression tests verifying Git LFS pointer detection and CLI generation recovery."""
import os
import sys
import subprocess
import sqlite3
import pytest
from pathlib import Path

from loyalty_ledger.db import (
    create_app_engine,
    check_sqlite_lfs_pointer,
    remove_lfs_pointer_if_present,
    is_lfs_pointer,
    init_db
)

GENUINE_LFS_POINTER_CONTENT = (
    b"version https://git-lfs.github.com/spec/v1\n"
    b"oid sha256:67845dff3d7b56b1c5a1d897b0a7088d701bfc1d2ca21c9beeda20c948740c6e\n"
    b"size 323076096\n"
)

def test_genuine_lfs_pointer_detected_and_recovered(tmp_path):
    """Verifies that a genuine Git LFS pointer is positively identified, rejected by ordinary
    database access, and successfully recovered by the documented CLI generate command.
    """
    pointer_file = tmp_path / "genuine_pointer.db"
    pointer_file.write_bytes(GENUINE_LFS_POINTER_CONTENT)
    db_url = f"sqlite:///{pointer_file}"

    # 1. is_lfs_pointer positively identifies genuine pointer
    assert is_lfs_pointer(pointer_file) is True

    # 2. Ordinary database access raises RuntimeError
    with pytest.raises(RuntimeError, match="unresolved Git LFS pointer text file"):
        check_sqlite_lfs_pointer(db_url)

    engine = create_app_engine(db_url)
    with pytest.raises(RuntimeError, match="unresolved Git LFS pointer text file"):
        with engine.connect() as conn:
            pass

    # 3. init_db attempt on target engine raises RuntimeError
    with pytest.raises(RuntimeError, match="unresolved Git LFS pointer text file"):
        init_db(target_engine=engine)

    # 4. CLI generate recovers from the genuine pointer
    env = os.environ.copy()
    src_dir = str(Path(__file__).resolve().parent.parent.parent / "src")
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else src_dir
    env["DATABASE_URL"] = db_url

    proc = subprocess.run(
        [sys.executable, "-m", "loyalty_ledger.cli", "generate", "--scale", "starter", "--seed", "20261022"],
        env=env,
        capture_output=True,
        text=True
    )

    assert proc.returncode == 0, f"CLI generate failed with stderr:\n{proc.stderr}\nstdout:\n{proc.stdout}"
    assert "Detected Git LFS pointer text file" in proc.stdout

    # Pointer was removed and replaced with a valid SQLite database
    assert pointer_file.exists()
    assert pointer_file.stat().st_size > 1000
    with open(pointer_file, "rb") as f:
        header = f.read(16)
    assert header.startswith(b"SQLite format 3")

    # Verify database contents
    conn = sqlite3.connect(pointer_file)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM customers;")
    assert cursor.fetchone()[0] == 500
    cursor.execute("SELECT COUNT(*) FROM orders;")
    assert cursor.fetchone()[0] == 2500
    conn.close()

def test_small_arbitrary_file_with_git_lfs_text_not_treated_as_pointer(tmp_path):
    """Verifies that a small arbitrary file containing 'git-lfs' but lacking the valid
    Git LFS pointer signature is NOT treated as a pointer and is NEVER deleted.
    """
    arbitrary_file = tmp_path / "notes_with_git_lfs.txt"
    content = b"Note: Install git-lfs from https://git-lfs.github.com to pull large assets."
    arbitrary_file.write_bytes(content)
    db_url = f"sqlite:///{arbitrary_file}"

    # Must NOT be detected as an LFS pointer
    assert is_lfs_pointer(arbitrary_file) is False

    # remove_lfs_pointer_if_present must return False and NOT delete the file
    removed = remove_lfs_pointer_if_present(db_url)
    assert removed is False
    assert arbitrary_file.exists()
    assert arbitrary_file.read_bytes() == content

    # check_sqlite_lfs_pointer must not raise
    check_sqlite_lfs_pointer(db_url)

def test_malformed_pointer_like_files_not_treated_as_pointer(tmp_path):
    """Verifies that malformed pointer-like files (e.g. invalid version, truncated hash,
    non-numeric size, or missing required fields) are NOT recognized as pointers and are NEVER deleted.
    """
    malformed_cases = [
        # Case 1: Version header only, missing oid and size
        (
            "missing_fields.db",
            b"version https://git-lfs.github.com/spec/v1\n"
        ),
        # Case 2: Invalid OID format (not sha256:64hex)
        (
            "invalid_oid.db",
            b"version https://git-lfs.github.com/spec/v1\n"
            b"oid sha256:invalid_hex_string_that_is_not_64_characters\n"
            b"size 12345\n"
        ),
        # Case 3: Invalid size format (non-numeric)
        (
            "invalid_size.db",
            b"version https://git-lfs.github.com/spec/v1\n"
            b"oid sha256:67845dff3d7b56b1c5a1d897b0a7088d701bfc1d2ca21c9beeda20c948740c6e\n"
            b"size abcdef\n"
        ),
        # Case 4: Has oid and size but missing exact version header line
        (
            "missing_version.db",
            b"oid sha256:67845dff3d7b56b1c5a1d897b0a7088d701bfc1d2ca21c9beeda20c948740c6e\n"
            b"size 323076096\n"
        ),
        # Case 5: Different version URL
        (
            "wrong_version.db",
            b"version https://example.com/spec/v2\n"
            b"oid sha256:67845dff3d7b56b1c5a1d897b0a7088d701bfc1d2ca21c9beeda20c948740c6e\n"
            b"size 323076096\n"
        ),
    ]

    for filename, raw_bytes in malformed_cases:
        test_file = tmp_path / filename
        test_file.write_bytes(raw_bytes)
        db_url = f"sqlite:///{test_file}"

        # Must NOT be detected as an LFS pointer
        assert is_lfs_pointer(test_file) is False, f"Failed for {filename}"

        # Must NEVER be deleted
        removed = remove_lfs_pointer_if_present(db_url)
        assert removed is False, f"Unexpected deletion for {filename}"
        assert test_file.exists(), f"File disappeared for {filename}"
        assert test_file.read_bytes() == raw_bytes, f"Content altered for {filename}"

def test_valid_sqlite_database_remains_untouched(tmp_path):
    """Verifies that a valid SQLite database is never treated as a pointer and is never deleted."""
    db_file = tmp_path / "valid_sqlite.db"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE metrics (name TEXT, value REAL);")
    conn.execute("INSERT INTO metrics VALUES ('accuracy', 0.99);")
    conn.commit()
    conn.close()

    db_url = f"sqlite:///{db_file}"

    # Must NOT be identified as an LFS pointer
    assert is_lfs_pointer(db_file) is False

    # remove_lfs_pointer_if_present must return False and NOT delete or modify
    removed = remove_lfs_pointer_if_present(db_url)
    assert removed is False
    assert db_file.exists()

    # Verify database remains fully valid and queryable
    conn2 = sqlite3.connect(db_file)
    cursor = conn2.cursor()
    cursor.execute("SELECT value FROM metrics WHERE name = 'accuracy';")
    row = cursor.fetchone()
    conn2.close()
    assert row is not None
    assert row[0] == 0.99
