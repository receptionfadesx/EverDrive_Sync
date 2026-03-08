# Sync Tool for EverDrive GB X7

*Disclaimer: This is an unofficial community tool and is not associated with, endorsed by, or affiliated with Krikzz or the official EverDrive brand in any way.*

**⚠️ WARNING: USE AT YOUR OWN RISK. It is highly recommended to test this tool using a secondary or backup SD card first before modifying your primary library.**

A comprehensive, power-user GUI utility built in PowerShell for managing, organizing, and syncing legally backed-up Game Boy and Game Boy Color ROMs to EverDrive-GB X7 (and similar) flash cartridges. 

EverDrive cartridges often exhibit specific quirks such as requiring FAT32 alphabetical directory sorting, and strict folder structures for save files and OS files (e.g., `GBCSYS`, `EDGB`). This script automates the tedious process of formatting, organizing ROMs into series or A-Z folders, standardizing filenames, and ensuring your precious save files remain intact and correctly linked.

## Features

- **Intuitive GUI**: Easy-to-use graphical interface built directly in PowerShell via `System.Windows.Forms`. Configures your source, destination, and sync options without needing to touch the command line.
- **Hardware-Compliant Copying**: Copies files strictly in alphabetical order to ensure menus sort correctly on the EverDrive hardware (which relies on FAT32 write-order).
- **Smart Sync**: Intelligently updates your SD card by moving existing ROMs/saves locally and only copying new files, drastically speeding up the sync process compared to a full wipe and copy. 
- **Force Full Copy**: Wipes the SD card and rewrites everything cleanly to fix stubborn alphabetical sorting issues on the flash cart. Protects crucial system folders (e.g., `GBCSYS`, `EDGB`) from being deleted.
- **Auto-Reorganization & Series Grouping**: 
  - Automatically identifies known franchise titles (e.g., *Pokemon*, *Zelda*, *Mario*) and creates dedicated folders.
  - Dynamically clusters similarly named games into series folders (requires at least 3 games).
  - Subdivides loose/remaining games into `A-Z` alphabetical folders to prevent directory limits and slow loading.
- **1G1R (1 Game 1 ROM) Filter**: Filters large "No-Intro" sets down to just one version per game, favoring regions in a customizable priority (USA > World > Europe > Japan), and preferring newer revisions, bugfixes, and translation hacks over original base ROMs.
- **ROM Naming Sanitizer**:
  - Un-nests trailing suffixes. Restructures titles like *"The Legend of Zelda"* to *"Legend of Zelda, The"* for perfect alphabetical sorting.
  - Cleans up cluttered No-Intro tags such as `(Rev A)`, `(USA, Europe)`, and `[!]`.
  - Normalizes accents (e.g., *Pokémon* -> *Pokemon*) to guarantee reliable matching and filesystem safety.
- **Integrated `.zip` Extraction**: Can seamlessly extract `.gb` or `.gbc` ROMs directly from `.zip` archives during the sync process.
- **Dedicated ROM Hacks Support**: Treat ROM hacks as first-class citizens. Keeps them properly sorted with their own saves without clashing with base games.
- **Save File & RTC Management**:
  - Automatically backs up `.sav`, `.rtc`, and `.snap` files from your SD card to your PC before making drastic changes.
  - Restores saves perfectly, matching them to dynamically renamed ROMs.
  - Routes save files into the correct flat hardware directory (e.g., `GBCSYS/SAVE` or `EDGB/SAVE`).

## Requirements

- **OS**: Windows 10 / Windows 11
- **PowerShell**: Version 5.1 or higher
- **Hardware**: Krikzz EverDrive-GB X7 (or compatible flash cartridge)

## Quick Start

1. Right-click `Sync-EverDriveSorted.ps1` and select **Run with PowerShell**.
   *(If prompted by execution policies, you may need to run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy Bypass` in your PowerShell console first).*
2. **Choose Source**: Select the folder containing your legally backed-up Game Boy and Game Boy Color ROMs.
3. **Choose SD Card**: Select the root drive letter of your EverDrive SD card.
4. **Select Options**: Check the boxes matching your desired library configuration (e.g., 1G1R filtering, auto-sorting).
5. **Start Sync**: Click the green "Start Sync" button and let the script handle the heavy lifting!

> **Note:** The script will automatically save your selected paths and options to `~/.everdrive_sync_config.json` for your next session.

## Save Restorations

If you accidentally wipe your EverDrive or want to restore states from a previous sync, the script maintains your files in a local `Saves_Backup` directory in your Source ROM folder. Use the **Restore Saves (Backup)** button on the GUI to safely push these back to the required system folders without messing up your sync state.
