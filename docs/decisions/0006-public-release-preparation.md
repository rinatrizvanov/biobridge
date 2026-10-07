# 0006: Preparing for a public source release

Status: **done locally** (2026-10-07). The repository is still private, with no tag and no published disk image. The candidate disk image built from `def7e9f` is unchanged and remains the candidate for the second-Mac test only.

## Bundle identifier: `io.github.rinatrizvanov.biobridge`

- **Why this prefix.** It is the reverse-DNS form of the maintainer's GitHub Pages domain, `rinatrizvanov.github.io`, a name the project controls without owning a domain. This is the usual choice for open-source apps without their own domain.
- **Where it is set.** In `pyproject.toml` (`bundle`) and in `launcher.py` (`APP_ID`). A unit test keeps the two equal.
- **The guard.** `check_app_bundle.py` fails a build whose `Info.plist` identifier differs from it, or that uses a placeholder prefix (`local.`, `com.example.`, `org.example.`, `org.beeware.`).
- **What changes for users.** BioBridge's data and log folders are named "BioBridge", not after the identifier, so existing setups and jobs carry over. macOS treats the new identifier as a different app, so users approve it again once.
- **Choose once.** Changing the identifier after release would repeat that approval for every user.

## Minimum macOS: 14.0 declared, still unverified

- **Before:** the app declared the support package's minimum, macOS 11, while the docs said 14.
- **Now:** Briefcase's `min_os_version` sets 14.0, and the bundle check compares it with `pyproject.toml`.
- **Still unverified:** no Mac or CI image running macOS 14 has run BioBridge.

## Third-party license texts in the app

- **The gap.** The Python packages in the app already carried their license files, but the Python runtime's own components did not. The runtime's `LICENSE.txt` covers only Python's terms.
- **What the runtime contains.** The components were identified from:
  - the runtime binary itself;
  - CPython 3.11.9's macOS installer build script;
  - version strings in the app's libraries.

  They are:
  - OpenSSL 3.0.13;
  - SQLite 3.45.1;
  - XZ 5.2.3;
  - ncurses 5.9;
  - Tcl/Tk 8.6.13, which BioBridge does not use;
  - expat and libmpdec, compiled into CPython.

  libffi and zlib are used from macOS itself.
- **The fix.** The upstream license texts, at those versions, are now in `src/biobridge/third_party_licenses/` with an index, so they ship in the app. The bundle check requires them.
- **A correction.** The Briefcase stub and template are MIT-licensed, not BSD-3-Clause as previously listed.
- **A related finding.** The runtime is Python 3.11.9, the last python.org macOS binary for 3.11, so it gets no further security fixes. It is a decision before distribution; see the [release page](../release-v0.1.0.md#release-blockers).

## Explanation wording

The wording was checked against the upstream README at `v1.3.1`, the README's history, and `spliceai/utils.py`. Findings and changes are in [wording-review-v0.1.md](../wording-review-v0.1.md). The explanation text version is now `explanations/2`. This was not the independent expert review, which stays pending.

## Citation and notices

- **`CITATION.cff`** gains the repository URL and references to the SpliceAI paper and software. It validates against CFF schema 1.2.0 (`cffconvert --validate`).
- **`THIRD_PARTY_LICENSES.md`** gains the corrected runtime table and a section on the source repository's third-party material: the license texts and the two README example variants.
