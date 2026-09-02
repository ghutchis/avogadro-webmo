#  This source file is part of the Avogadro project
#  This source code is released under the BSD-3-Clause License, (see "LICENSE").

"""Small repairs to WebMO's QC_JSON before Avogadro reads it.

Avogadro parses this dialect natively -- quantumio/qcschema.cpp treats
schema_name "QC_JSON" as the WebMO variant, Angstroms with one-based
connectivity -- so there is no conversion to do here, only the handful of
places where WebMO's key names differ from what that reader looks for.
"""

# Thermochemistry, not the electronic energy the reader wants.
_NOT_ELECTRONIC = {"free_energy", "internal_energy", "zero_point_energy"}


def normalize(results, metadata=None):
    """Adjust `results` in place and hand it back."""
    if not isinstance(results, dict):
        return results

    properties = results.get("properties")
    if isinstance(properties, dict):
        _add_total_energy(properties)

    if metadata:
        name = metadata.get("jobName") or ""
        number = metadata.get("jobNumber")
        if name and number is not None:
            # The reader prefers "name" over "comment", and this keeps the
            # imported molecule traceable to the job it came from.
            results["name"] = f"{name} ({number})"
        elif name:
            results["name"] = name

    return results


def _add_total_energy(properties):
    """WebMO names the energy after the method; the reader wants total_energy.

    Real examples from a WebMO server: uhf_energy, pm6_energy, rb3lyp_energy.
    qcschema.cpp only ever looks for "total_energy", so without this the
    imported molecule carries no energy at all.
    """
    if "total_energy" in properties:
        return

    candidates = {
        key: value
        for key, value in properties.items()
        if key.endswith("_energy")
        and key not in _NOT_ELECTRONIC
        and isinstance(value, dict)
        and "value" in value
    }
    if not candidates:
        return

    # Prefer the one naming the method WebMO reported, when it matches.
    method = str(properties.get("method_energy_name", "")).lower()
    if method:
        wanted = f"{method}_energy"
        for key, value in candidates.items():
            if key.lower() == wanted or key.lower().endswith(wanted):
                properties["total_energy"] = value
                return

    properties["total_energy"] = next(iter(candidates.values()))


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

    energy = properties.get("total_energy") or {}
    if isinstance(energy, dict) and "value" in energy:
        units = energy.get("units", "")
        parts.append(f"energy {energy['value']} {units}".strip())

    return ", ".join(parts)
