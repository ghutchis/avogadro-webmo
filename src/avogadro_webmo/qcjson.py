#  This source file is part of the Avogadro project
#  This source code is released under the BSD-3-Clause License, (see "LICENSE").

"""Prepare WebMO's QC_JSON for Avogadro, and describe what is in it.

Avogadro parses this dialect natively -- quantumio/qcschema.cpp treats
schema_name "QC_JSON" as the WebMO variant, Angstroms with one-based
connectivity -- so there is nothing to convert here.
"""

# Thermochemistry, not the electronic energy.
_NOT_ELECTRONIC = {"free_energy", "internal_energy", "zero_point_energy"}


def normalize(results, metadata=None):
    """Give the imported molecule a name tying it back to its job.

    The energy used to be repaired here as well: WebMO names it after the
    method it ran (uhf_energy, pm6_energy, rb3lyp_energy) where the reader
    only looked for total_energy. That fallback now lives in qcschema.cpp,
    where it also fixes every WebMO file opened any other way, so nothing is
    rewritten here any more.
    """
    if not isinstance(results, dict) or not metadata:
        return results

    name = metadata.get("jobName") or ""
    number = metadata.get("jobNumber")
    if name and number is not None:
        # The reader prefers "name" over "comment".
        results["name"] = f"{name} ({number})"
    elif name:
        results["name"] = name
    return results


def summarize(results):
    """One line about what came back, for the message shown to the user."""
    if not isinstance(results, dict):
        return ""

    parts = []
    symbols = results.get("symbols")
    if isinstance(symbols, list):
        parts.append(f"{len(symbols)} atoms")

    properties = results.get("properties") or {}
    sequence = properties.get("geometry_sequence") or {}
    geometries = sequence.get("geometries")
    if isinstance(geometries, list) and len(geometries) > 1:
        parts.append(f"{len(geometries)} optimization steps")

    vibrations = properties.get("vibrations") or {}
    frequencies = vibrations.get("frequencies")
    if isinstance(frequencies, list) and frequencies:
        parts.append(f"{len(frequencies)} vibrational modes")

    energy = electronic_energy(properties)
    if energy:
        units = energy.get("units", "")
        parts.append(f"energy {energy['value']} {units}".strip())

    return ", ".join(parts)


def electronic_energy(properties):
    """The energy block, wherever WebMO put it, or None.

    Read-only: this mirrors what qcschema.cpp does when it reads the file, so
    the message can quote the same number Avogadro ends up showing.
    """
    if not isinstance(properties, dict):
        return None
    if isinstance(properties.get("total_energy"), dict):
        return properties["total_energy"]

    method = str(properties.get("method_energy_name", "")).lower()
    fallback = None
    for key, value in properties.items():
        if not key.endswith("_energy") or key in _NOT_ELECTRONIC:
            continue
        if not isinstance(value, dict) or "value" not in value:
            continue
        if method and key.lower() == f"{method}_energy":
            return value
        if fallback is None:
            fallback = value
    return fallback
