"""Naming the imported molecule, and describing what came back."""

from avogadro_webmo import qcjson


def hartree(value):
    return {"units": "Hartree", "value": value}


def test_the_molecule_is_named_after_its_job():
    results = {"properties": {}}
    qcjson.normalize(results, {"jobName": "CH2O", "jobNumber": 1963200})
    assert results["name"] == "CH2O (1963200)"


def test_normalize_survives_results_with_no_properties():
    results = {"symbols": ["H"], "geometry": [0, 0, 0]}
    assert qcjson.normalize(results, None) is results


def test_the_energy_is_not_rewritten_into_the_document():
    # qcschema.cpp resolves the method-named key itself; the plugin must not
    # also edit the document on its way past.
    results = {"properties": {"method_energy_name": "HF", "uhf_energy": hartree(-55.2)}}
    qcjson.normalize(results, None)
    assert "total_energy" not in results["properties"]


def test_the_method_named_energy_is_found_for_the_message():
    # Straight from a WebMO HF/3-21G job.
    properties = {"method_energy_name": "HF", "uhf_energy": hartree(-55.2420114504)}
    assert qcjson.electronic_energy(properties) == hartree(-55.2420114504)


def test_the_key_matching_the_method_wins():
    properties = {
        "method_energy_name": "RB3LYP",
        "pm6_energy": hartree(-1.0),
        "rb3lyp_energy": hartree(-2.0),
    }
    assert qcjson.electronic_energy(properties)["value"] == -2.0


def test_thermochemistry_is_not_the_electronic_energy():
    properties = {"free_energy": hartree(-10.0), "internal_energy": hartree(-11.0)}
    assert qcjson.electronic_energy(properties) is None


def test_a_conforming_total_energy_wins_outright():
    properties = {"total_energy": hartree(-1.0), "pm6_energy": hartree(-2.0)}
    assert qcjson.electronic_energy(properties)["value"] == -1.0


def test_summarize_reports_what_came_back():
    results = {
        "symbols": ["C", "O"],
        "properties": {
            "method_energy_name": "PM6",
            "pm6_energy": hartree(-113.0),
            "vibrations": {"frequencies": [1, 2, 3]},
            "geometry_sequence": {"geometries": [[0], [0], [0], [0]]},
        },
    }
    summary = qcjson.summarize(results)
    assert "2 atoms" in summary
    assert "4 optimization steps" in summary
    assert "3 vibrational modes" in summary
    assert "-113.0 Hartree" in summary
