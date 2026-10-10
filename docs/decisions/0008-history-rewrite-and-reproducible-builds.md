# 0008: Personal email removed from the history; reproducible app builds

Status: **history rewritten locally; old repository deleted** (2026-10-09). Creating the replacement private repository with the cleaned history is **pending**. No tag, nothing published.

## Why

Every commit carried the maintainer's personal email address as author and committer. One document also quoted it. GitHub Actions records stored it as well. Making the repository public would have published it. The maintainer chose to replace it with their GitHub noreply address and to keep their name.

## What was rewritten

- **Rewritten:** all 18 commits, in order. Each one kept its name, dates, message and code. The only changes:
  - author and committer email, now the noreply address;
  - the one quoted address, now "[personal address removed]";
  - any quoted ID of an earlier commit, in a document or a message, now that commit's new ID at the same length.
- **No old ID survives.** Because quoted IDs were remapped, no published file or message names a commit ID from the old history. The old-to-new mapping and a backup of the old history are kept privately by the maintainer.
- **No trailers were added.**
- **Checked:**
  - an independent verifier passed on every commit: names and dates unchanged, messages and files unchanged except for the mapping, packaged paths identical, and neither the address nor an old ID anywhere;
  - a negative control: the verifier flags a rewrite that leaves old IDs in documents;
  - two runs from the same input produced identical commit IDs.
- **Before publishing:** the complete rewritten history was scanned for the address in every file of every commit, in messages and in author and committer fields.
- **The repository is replaced rather than force-pushed.** The old private repository was deleted on 2026-10-09, and a new private one is to be created with the cleaned history. A force-push would leave the old commits reachable by ID in GitHub's cached views until GitHub Support removed them, and the old Actions runs would keep the address in their metadata.

## Effect on provenance

- **Commit IDs changed.** All commit IDs in the documents are the current ones. Disk images built before 2026-10-09 record the earlier IDs of the same commits.
- **The candidate was rebuilt** so that `biobridge_commit` in every CSV names a commit that exists. The README asks users to cite that commit.
- **The rebuild is equivalent** to the image retested by hand:
  - 3,469 of 3,475 files are byte-identical;
  - the rest differ only in build information, code signatures and install-record hashes of removed scripts;
  - packaged-app results are identical.

  The details are on the [release page](../release-v0.1.0.md#the-candidate-build).

## Reproducible app builds

- **Found while rebuilding.** Briefcase installed the app's indirect dependencies at whatever versions PyPI had at build time, so a rebuild picked up platformdirs 4.12.4 instead of the 4.12.3 in `uv.lock`, the version the tests use.
- **The fix.** `scripts/build_app.sh` now exports `uv.lock` (without development packages) as pip constraints for Briefcase, and `scripts/check_app_bundle.py` fails if any bundled package's version differs from `uv.lock`.
- **Unchanged:** the packaged paths, so the source sha256 is unchanged.

## For the maintainer

These GitHub settings are recommended, and left to the maintainer:
- "Keep my email addresses private";
- "Block command line pushes that expose my email".

This repository's git configuration uses the noreply address for future commits.
