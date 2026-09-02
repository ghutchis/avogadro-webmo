"""The table payload and the row the picker sends back."""

import json

import pytest

from avogadro_webmo import jobs
from avogadro_webmo.client import WebMOAuthError

METADATA = {
    1963207: {
        "jobNumber": 1963207,
        "jobName": "H2N",
        "jobDescription": "Molecular Energy",
        "jobEngine": "gaussian",
        "jobDate": "9/1/2026 18:27",
        "jobStatus": "complete",
    },
    1963200: {
        "jobNumber": 1963200,
        "jobName": "CH2O",
        "jobDescription": "Geometry Optimization",
        "jobEngine": "mopac",
        "jobDate": "9/1/2026 17:44",
        "jobStatus": "running",
    },
}

RESULTS = {
    "schema_name": "QC_JSON",
    "symbols": ["N", "H", "H"],
    "geometry": [0, 0, 0.137281, 0, 0.873651, -0.480484, 0, -0.873651, -0.480484],
    "connectivity": [[1, 2, 1], [1, 3, 1]],
    "properties": {"method_energy_name": "HF", "uhf_energy": {"units": "Hartree", "value": -55.2}},
}


class FakeClient:
    def __init__(self, numbers=(1963207, 1963200)):
        self.numbers = list(numbers)
        self.filters = None

    def jobs(self, **filters):
        self.filters = filters
        return self.numbers

    def job(self, number):
        return METADATA[int(number)]

    def results(self, number):
        return json.loads(json.dumps(RESULTS))


@pytest.fixture
def offline(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(jobs, "connect", lambda *args: client)
    monkeypatch.setattr(
        jobs.config,
        "load_config",
        lambda: {"url": "u", "username": "guest", "job_count": 25, "only_completed": True},
    )
    return client


def test_the_table_is_selectable_sortable_and_row_shaped(offline):
    table = jobs.user_options({})["userOptions"]["Job"]
    assert table["type"] == "table"
    assert table["selectable"] is True
    assert table["sortable"] is True
    assert table["headers"] == jobs.HEADERS
    assert table["rows"][0] == [
        "1963207",
        "H2N",
        "Molecular Energy",
        "gaussian",
        "9/1/2026 18:27",
    ]
    # Every row has to match the header width, or cells land under the wrong
    # column once the user sorts.
    assert all(len(row) == len(jobs.HEADERS) for row in table["rows"])


def test_only_completed_becomes_a_server_side_filter(offline):
    jobs.user_options({})
    assert offline.filters == {"status": "complete"}


def test_a_failure_still_produces_a_form_not_an_empty_dialog(monkeypatch):
    def refuse(*args):
        raise WebMOAuthError("The WebMO session has expired.")

    monkeypatch.setattr(jobs, "connect", refuse)
    options = jobs.user_options({})["userOptions"]
    # An empty userOptions would make Avogadro run the command immediately.
    assert options
    assert options["Status"]["type"] == "text"
    assert "expired" in options["Status"]["default"]


def test_the_selected_row_is_read_back_as_a_job_number(offline):
    row = jobs.DELIMITER.join(["1963207", "H2N", "Molecular Energy", "gaussian", "x"])
    result = jobs.run({"options": {"Job": row}})
    assert result["moleculeFormat"] == "qcjson"
    document = json.loads(result["qcjson"])
    assert document["schema_name"] == "QC_JSON"
    # Normalization happened on the way out.
    assert document["properties"]["total_energy"]["value"] == -55.2
    assert document["name"] == "H2N (1963207)"
    # WebMO supplied connectivity, so Avogadro must not re-perceive bonds.
    assert "bond" not in result


def test_no_selection_leaves_the_molecule_alone(offline):
    assert jobs.run({"options": {"Job": ""}}) == {"message": "No job selected."}


def test_an_unfinished_job_is_reported_rather_than_imported(offline):
    row = jobs.DELIMITER.join(["1963200", "CH2O", "", "", ""])
    result = jobs.run({"options": {"Job": row}})
    assert "running" in result["message"]
    assert "qcjson" not in result
