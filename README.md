# avogadro-webmo

Browse and import [WebMO](https://www.webmo.net/) jobs from Avogadro over its
REST/JSON interface.

**Prototype.** It depends on the `table` user-option type, which needs the
`jsonwidget` / `command` fixes on the avogadrolibs `fix-json-table` branch, so
it will not work against Avogadro 2.0.

## Commands

* **Extensions › WebMO › Server Settings…** — point at a server, sign in, and
  keep the session token. The URL may be the login page, the `cgi-bin/webmo`
  directory, a bare host, or the `rest.cgi` endpoint itself.
* **Extensions › WebMO › Open Job…** — a sortable table of recent jobs; pick
  one and it is loaded as a molecule.

## What gets imported

`/jobs/{n}/results` returns `schema_name: "QC_JSON"`, which Avogadro parses
natively — `quantumio/qcschema.cpp` treats it as the WebMO variant (Ångströms,
one-based connectivity). So the plugin hands the document straight over rather
than converting it, and geometry, bonding, partial charges, dipole moment,
optimization trajectories and vibrational modes all come across.

Two things it repairs first: WebMO names the energy after the method
(`uhf_energy`, `pm6_energy`, `rb3lyp_energy`) where the reader only looks for
`total_energy`, and the molecule gets a name tying it back to its job number.

Not imported: orbital energies and molecular orbitals. The reader does not read
them, and the REST interface does not expose basis sets or MO coefficients, so
no orbital or cube rendering from a WebMO import.

## Credentials

The server URL, user name and list preferences go to
`<config dir>/avogadro/webmo.json`. The password and session token go to the
system keychain via `keyring`. Where no keychain is available the token — never
the password — falls back to a mode-0600 file next to the config, and the
plugin says so.

## Trying it without Avogadro

```sh
pixi run demo-login                 # defaults to the public demo server, guest/guest
pixi run demo-options open          # the exact JSON Avogadro builds the table from
pixi run demo-open 1963204          # import one job
pixi run -e test test               # unit tests, no network
```

## Notes on the REST interface

`/jobs` returns **job numbers only**, capped at 250, so each row of the table
costs one more request at roughly 0.4 s. The server serializes them — a thread
pool measured no faster than doing them one at a time — so the list is capped
("Jobs to list", 25 by default) and abandoned after 20 s, comfortably inside
the 30 s Avogadro allows a `--user-options` call.
