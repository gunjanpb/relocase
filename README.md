# relocase

## Synopsis

`relocase` is a command-line utility for synchronizing files between two directories, similar to `rsync`. It minimizes redundant file transfers by identifying and moving files that already exist on the target disk, even if they are in a different location. This is achieved by calculating and comparing the MD5 checksums of the files.

## Description

`relocase` is a Python-based file syncing program that efficiently transfers files between two mounted disks. It is designed to reduce file transfer rates by checking if a file with the same content already exists anywhere on the target disk. If a file with a matching MD5 checksum is found, `relocase` will move the existing file to the correct location instead of transferring it again. This is particularly useful when dealing with large files or slow network connections.

The program stores the MD5 checksums of all files on the target filesystem in a local database. When syncing a file from the source directory, it calculates the checksum of the source file and queries the database to see if a file with the same checksum already exists on the target. If a match is found, the existing file is moved to the correct location. Otherwise, the file is transferred from the source to the target.

`relocase` also features a robust dry-run mode that allows you to preview the changes that will be made without actually modifying any files. This is useful for verifying that the program will behave as expected before performing a real sync.

## Design Decisions

### MD5 Checksums

MD5 checksums are used to identify files with the same content. While MD5 is not a cryptographically secure hashing algorithm, it is sufficient for detecting accidental data corruption and identifying duplicate files. The use of MD5 checksums allows `relocase` to efficiently identify files that already exist on the target disk, even if they are in a different location.

### Local Database

The MD5 checksums of the files on the target filesystem are stored in a local database. This allows `relocase` to quickly query the checksum of a file without having to recalculate it every time. The database is automatically updated when files are added, removed, or modified on the target disk.

### Dry-Run Mode

The dry-run mode is a crucial feature of `relocase`. It allows you to preview the changes that will be made without actually modifying any files. This is useful for verifying that the program will behave as expected before performing a real sync. The dry-run mode is implemented by simulating the file transfer and move operations and printing the results to the console.

## Usage

```bash
relocase [OPTIONS] SOURCE TARGET
```

### Arguments

*   `SOURCE`: The source directory.
*   `TARGET`: The target directory.

### Options

*   `--dry-run`: Perform a dry run without actually modifying any files.
*   `--help`: Show the help message and exit.

### Examples

*   Perform a dry run to see what changes will be made:

```bash
relocase --dry-run /path/to/source /path/to/target
```

*   Sync the files from the source to the target:

```bash
relocase /path/to/source /path/to/target
```

## Installation

1.  Clone the repository:

```bash
git clone https://github.com/your-username/relocase.git
```

2.  Install the dependencies:

```bash
pip install -r requirements.txt
```

## Testing

To run the test suite, use the following command:

```bash
pytest
```
