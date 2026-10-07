# Installation checklist: a second Apple Silicon Mac (v0.1.0)

This checklist takes about 20 minutes. It tests BioBridge as a user would get it: downloaded in a browser, approved by macOS, and set up without a terminal. It is the closest check so far to a clean-machine install.

**Before you start**
- **The Mac:** Apple Silicon (M1 or later), macOS 14 or later, internet access, and about 2 GB of free space.
- **Record:** the Mac's chip and macOS version (Apple menu › **About This Mac**). Also note whether it is managed by an institution: it is if **System Settings › General** has a **Device Management** item listing a profile.
- **First install only:** BioBridge should never have been installed on this Mac or this account. In Finder, choose **Go › Go to Folder…** and enter `~/Library/Application Support/BioBridge`. The folder should not exist.
- **No security changes:** do not change any security setting except clicking **Open Anyway** as described below.
- **Developer tools:** if macOS ever offers to install *command line developer tools*, click **Cancel** and write it down. BioBridge must not need them.

**Getting the disk image there.** Put `dist/BioBridge-0.1.0.dmg` somewhere private that you control, shared with nobody: for example your own cloud storage. Do not post it publicly. Then download it **with a browser** (Safari or Chrome) on the second Mac, so macOS treats it as downloaded. Copying it over a cable, a network share or a USB drive does not test that.

**Use the candidate built from `3a6f738`.** Do not use the superseded `def7e9f` disk image kept in `dist/historical/`. The expected values, also recorded in [release-v0.1.0.md](release-v0.1.0.md) under *The candidate build*, are:

| Item | Expected |
|---|---|
| Disk image | `BioBridge-0.1.0.dmg`, 49,220,279 bytes, sha256 `7fc22fedd200bda9347e829bc4e15230298c950d6961de0516d945d50f488b3d` |
| Packaged source commit (`biobridge_commit` in the CSV) | `3a6f738bf74a7551327f7cc007c86339dcabf110` |
| Source sha256 (`biobridge_source_sha256` in the CSV) | `1f90830a31c88fb541f126be430280839dde5e1af4adde2b6cc3dc1c2ed68a40` |
| App identifier: in the app's `Info.plist`; macOS's messages show only the name BioBridge | `io.github.rinatrizvanov.biobridge` |

The CSV shows the packaged source commit, not the repository's latest commit: later commits are not in this disk image.

| # | Step | Expected | Record |
|---|---|---|---|
| 1 | Download `BioBridge-0.1.0.dmg` in the browser. *Optional:* in Terminal, `shasum -a 256 ~/Downloads/BioBridge-0.1.0.dmg`. | The file is in Downloads. The optional checksum is `7fc22fed…8b3d` (full value above). | browser, checksum matched? |
| 2 | Double-click the disk image. | macOS blocks it: it could not verify that it is free of malware. Click **Done**. | the exact message |
| 3 | **System Settings › Privacy & Security**, scroll to **Security**, click **Open Anyway** next to the disk-image message, confirm, and authenticate. | The disk image opens. | worked? |
| 4 | Drag **BioBridge** to **Applications**, then eject the disk image. | | |
| 5 | Open BioBridge from Applications. | Either the BioBridge window opens, or *"BioBridge" Not Opened* appears. If it appears, click **Done**, then **Open Anyway** next to *"BioBridge" was blocked…* in Privacy & Security, confirm and authenticate. | **was a second approval needed?** |
| 6 | Read the license notice, tick the confirmation, and click **Start BioBridge**. | The window shows setup progress and then *BioBridge is running*. Your browser opens BioBridge. Setup takes about a minute on a fast connection. | setup time; any "retrying" or error text |
| 7 | Paste `chr17-43057051-C-T`, tick **These coordinates are GRCh38 (hg38).**, and click **Run SpliceAI**. | The first run also downloads chr17. Results show *Scored* and *Largest masked* `0.99 DL`. In the chart, the 0.99 label is fully visible. The value table reads AG 0.00, AL 0.00, DG 0.02, DL 0.99, masked and raw alike. | time to results |
| 8 | Click **Download CSV** and open the file in TextEdit. | `biobridge_commit` is `3a6f738bf74a7551327f7cc007c86339dcabf110`, with **no** `+uncommitted changes`. `biobridge_source_sha256` is `1f90830a…0a40`. `DS_DL_masked` is `0.99`. | match? |
| 9 | Click **Quit BioBridge** on the page. Then open **Activity Monitor** and search for `BioBridge`. | The page says *BioBridge is quitting*, the BioBridge window closes, and Activity Monitor lists no BioBridge process. | |
| 10 | Copy `~/Library/Logs/BioBridge/launcher.log` and the CSV back to the first Mac. | The log shows setup, the job and Quit cleanup. The CSV can be compared with the SpliceAI runner on the first Mac. Neither check changes anything. | |

If a step fails, stop there. Note the step and the exact message, and keep the log; don't retry with changed settings.

**This checklist answers:**
- whether a downloaded copy needs a second approval;
- whether BioBridge sets up on a Mac other than the developer's, without developer tools;
- whether provenance shows the clean commit on another machine.

**It does not cover** IT-managed Macs, unless this Mac happens to be managed.

**Removing BioBridge afterwards** (optional): see [install.md](install.md#removing-biobridge).
