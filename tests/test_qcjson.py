"""The two repairs made to WebMO's QC_JSON before Avogadro reads it."""

from avogadro_webmo import qcjson


def hartree(value):
    return {"units": "Hartree", "value": value}


def test_method_named_energy_becomes_total_energy():
    # Straight from a WebMO HF/3-21G job: the reader only knows total_energy.
    results = {
        "properties": {
            "method_energy_name": "HF",
            "uhf_energy": hartree(-55.2420114504),
        }
    }
    qcjson.normalize(results)
    assert results["properties"]["total_energy"] == hartree(-55.2420114504)
    # The original key stays, so nothing that reads it is broken.
    assert "uhf_energy" in results["properties"]


def test_the_method_matching_key_wins_over_the_others():
    results = {
        "properties": {
            "method_energy_name": "RB3LYP",
            "pm6_energy": hartree(-1.0),
            "rb3lyp_energy": hartree(-2.0),
        }
    }
    qcjson.normalize(results)
    assert results["properties"]["total_energy"]["value"] == -2.0


def test_thermochemistry_is_not_the_electronic_energy():
    results = {
        "properties": {
            "free_energy": hartree(-10.0),
            "internal_energy": hartree(-11.0),
        }
    }
    qcjson.normalize(results)
    assert "total_energy" not in results["properties"]


def test_an_existing_total_energy_is_left_alone():
    results = {"properties": {"total_energy": hartree(-1.0), "pm6_energy": hartree(-2.0)}}
    qcjson.normalize(results)
    assert results["properties"]["total_energy"]["value"] == -1.0


def test_the_molecule_is_named_after_its_job():
    results = {"properties": {}}
    qcjson.normalize(results, {"jobName": "CH2O", "jobNumber": 1963200})
    assert results["name"] == "CH2O (1963200)"


def test_normalize_survives_results_with_no_properties():
    results = {"symbols": ["H"], "geometry": [0, 0, 0]}
    assert qcjson.normalize(results, None) is results


def test_summarize_reports_what_came_back():
    results = {
        "symbols": ["C", "O"],
        "properties": {
            "total_energy": hartree(-113.0),
            "vibrations": {"frequencies": [1, 2, 3]},
            "geometry_sequence": {"geometries": [[0], [0], [0], [0]]},
        },
    }
    summary = qcjson.summarize(results)
    assert "2 atoms" in summary
    assert "4 optimization steps" in summary
    assert "3 vibrational modes" in summary
    assert "-113.0 Hartree" in summary
