# CS4348 Project 3: B-Tree Index File Manager

## Description
This project implements an interactive program to manage index files using a B-tree data structure. The program allows users to:
- Create and open index files.
- Insert and search key-value pairs.
- Load data from files and extract data to files.
- Print the contents of the B-tree.

The program strictly adheres to the requirements of CS4348 Project 3 and is implemented in Python without external dependencies.

## Features
- **Index File Management:** Create, open, and manage index files.
- **B-Tree Data Structure:** Efficiently handle hierarchical data with minimal memory usage.
- **Interactive Command Line Interface:** Perform operations using an intuitive menu-driven interface.
- **Persistence:** Store B-tree nodes in 512-byte blocks within the index file.
- **Error Handling:** Graceful handling of invalid commands, duplicate keys, and other errors.

## Project Files
- `project3.py`: Main script implementing the functionality.
- `devlog.md`: Development log documenting the progress and challenges encountered during implementation.
- `README.md`: This file containing project details.
- **Other files** (if needed):
  - Example data files for testing (`data.csv`).

## Requirements
- Python 3.11 or higher.
- Works on CS1 and CS2 machines without IDE dependencies.

## Commands Overview
The following commands are supported:
- `create <filename>`: Create a new index file.
- `open <filename>`: Open an existing index file.
- `insert <key> <value>`: Insert a key-value pair.
- `search <key>`: Search for a key in the index.
- `load <filename>`: Load key-value pairs from a file.
- `print`: Print all key-value pairs in the index.
- `extract <filename>`: Save all key-value pairs to a file.
- `quit`: Exit the program.

## Setup Instructions
1. Clone the repository:
   ```bash
   git clone https://github.com/jasonxshetty/project3_CS4348.git