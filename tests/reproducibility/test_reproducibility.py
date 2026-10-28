"""Automated test for two-run fixed-seed reproducibility."""
import pytest
from loyalty_ledger.reports.reproducibility import ReproducibilityVerifier

def test_fixed_seed_reproducibility():
    verifier = ReproducibilityVerifier(seed=20261022, scale="starter")
    report = verifier.verify()
    assert report["reproducible"] is True
    assert report["row_counts_identical"] is True
    assert report["checksums_identical"] is True
    assert len(report["checksum_differences"]) == 0
