# Installing BioBridge (draft for the M0 feasibility build)

BioBridge is not notarized by Apple: notarization needs a paid Apple Developer
account, and this is a free, volunteer project. macOS therefore asks you to confirm
that you want to open the downloaded disk image, and possibly the app itself. Each
approval is needed only once. You never need the Terminal.

Requirements: a Mac with Apple Silicon (M1 or later) running macOS 14 or later,
an internet connection for the first setup (about 330 MB), and about 2 GB of free space.

## Steps

1. **Download** `BioBridge-<version>.dmg`.
2. **Approve the disk image.** Double-click the `.dmg`. macOS blocks it before
   opening it, saying it could not verify that it is free of malware. Click **Done**.
   Open **System Settings › Privacy & Security**, scroll to **Security**, and click
   **Open Anyway** next to the message about `BioBridge-<version>.dmg`. Confirm, and
   enter your Mac password or use Touch ID. The disk image opens.
   (Observed on macOS 15.6.1.)
3. **Drag BioBridge to Applications** in the window that opens, then eject the disk image.
4. **Open BioBridge** from Applications. If macOS shows *"BioBridge" Not Opened*,
   click **Done**, return to **System Settings › Privacy & Security**, click
   **Open Anyway** next to *"BioBridge" was blocked to protect your Mac*, confirm, and
   authenticate. *(Whether this second approval appears after step 2 is still being
   confirmed.)*
5. In BioBridge, read the SpliceAI license notice, tick the confirmation, and click
   **Set up and run demo**. The first setup downloads the SpliceAI engine and part of
   the GRCh38 reference genome. The window shows its progress, and a browser tab
   opens with the result.

If your Mac is managed by your institution's IT department, the **Open Anyway**
button may be unavailable; ask IT to allow BioBridge.

## Removing BioBridge

Drag BioBridge from Applications to the Bin, then delete these two folders in Finder
(Go › Go to Folder…):

- `~/Library/Application Support/BioBridge`
- `~/Library/Logs/BioBridge`
