# Installing BioBridge

BioBridge is not notarized by Apple: notarization needs a paid Apple Developer account, and this is a free, volunteer project. macOS therefore asks you, once, to confirm that you want to open the downloaded disk image, and possibly the app. You never need the Terminal.

You need a Mac with Apple Silicon (M1 or later) and macOS 14 or later, an internet connection for the first setup (about 330 MB), and about 2 GB of free space.

## Steps

1. **Download** `BioBridge-<version>.dmg`.
2. **Approve the disk image.**
   - Double-click the `.dmg`. macOS blocks it, saying it could not verify that it is free of malware. Click **Done**.
   - Open **System Settings › Privacy & Security** and scroll to **Security**. Click **Open Anyway** next to the message about `BioBridge-<version>.dmg`.
   - Confirm, and enter your Mac password or use Touch ID. The disk image opens.
   - (Observed on macOS 15.6.1.)
3. **Drag BioBridge to Applications**, then eject the disk image.
4. **Open BioBridge** from Applications. If macOS shows *"BioBridge" Not Opened*:
   - Click **Done**.
   - Return to **System Settings › Privacy & Security**, and click **Open Anyway** next to *"BioBridge" was blocked to protect your Mac*.
   - Confirm and authenticate.
   - *(Whether this second approval appears after step 2 has not been confirmed yet.)*
5. **Set up.** In the BioBridge window, read the SpliceAI license notice, tick the confirmation, and click **Start BioBridge**.
   - The first setup downloads the SpliceAI engine; the window shows its progress.
   - Your browser then opens BioBridge.
   - Keep the BioBridge window open while you work.
6. **Next time**, open BioBridge from Applications. It opens your browser directly. To reopen the page, use **Open in browser** in the BioBridge window.

**IT-managed Macs.** If your Mac is managed by your institution, the **Open Anyway** button may be unavailable; ask IT to allow BioBridge. This case has not been tested.

## Updating

Quit BioBridge, then drag the new version to Applications and choose **Replace**. Your setup and past jobs are kept.

## Removing BioBridge

Drag BioBridge from Applications to the Bin. Then delete these two folders in Finder (**Go › Go to Folder…**):

- `~/Library/Application Support/BioBridge`, which holds the engine, reference chromosomes and jobs.
- `~/Library/Logs/BioBridge`
