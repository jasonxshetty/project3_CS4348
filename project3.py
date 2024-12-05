import os
import struct
import sys
import logging

BLOCK_SIZE = 512
MAGIC_HEADER = b'BTREEIDX'
MIN_DEGREE = 4

# Configure logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# Custom Exceptions
class IndexFileError(Exception):
    pass

class DuplicateKeyError(Exception):
    pass

class IndexManager:
    def __init__(self):
        self.index_file = None
        self.root = None

    def create_index_file(self, filename):
        try:
            if os.path.exists(filename):
                choice = input(f"File '{filename}' already exists. Overwrite? (y/n): ").lower()
                if choice != 'y':
                    print("Operation cancelled.")
                    return
            with open(filename, 'wb') as f:
                # Write file header: magic number + root offset + padding
                f.write(MAGIC_HEADER)
                f.write(struct.pack('>Q', 0))  # Root offset = 0 means empty tree
                f.write(b'\x00' * (BLOCK_SIZE - len(MAGIC_HEADER) - 8))
            print(f"Index file '{filename}' created.")
        except IOError as e:
            logger.error(str(e))
            print("Error creating index file.")

    def open_index_file(self, filename):
        try:
            if not os.path.exists(filename):
                print(f"Error: File '{filename}' does not exist.")
                return
            with open(filename, 'rb') as f:
                magic = f.read(len(MAGIC_HEADER))
                if magic != MAGIC_HEADER:
                    raise IndexFileError("Invalid index file format.")
                root_offset = struct.unpack('>Q', f.read(8))[0]
                self.root = BTreeNode(self, offset=root_offset) if root_offset != 0 else None
            self.index_file = filename
            print(f"Index file '{filename}' opened.")
        except IndexFileError as e:
            logger.error(str(e))
            print(e)
        except IOError as e:
            logger.error(str(e))
            print("Error opening index file.")

    def update_root_offset(self, offset):
        if self.index_file is None:
            return
        try:
            with open(self.index_file, 'r+b') as f:
                f.seek(len(MAGIC_HEADER))
                f.write(struct.pack('>Q', offset))
        except IOError as e:
            logger.error(str(e))
            print("Error updating root offset.")

    def insert(self, key, value):
        if self.index_file is None:
            print("Error: No index file is open.")
            return
        try:
            # If the tree is empty, create a new root
            if self.root is None:
                self.root = BTreeNode(self, is_leaf=True)
                self.root.keys.append(key)
                self.root.values.append(value)
                self.root.save()
                self.update_root_offset(self.root.offset)
            else:
                # If the root is full, split it before inserting
                if len(self.root.keys) == 2 * MIN_DEGREE - 1:
                    new_root = BTreeNode(self, is_leaf=False)
                    new_root.children.append(self.root.offset)
                    new_root.split_child(0, self.root)
                    self.root = new_root
                    self.update_root_offset(self.root.offset)
                self.root.insert_non_full(key, value)
            print(f"Inserted key {key}.")
        except DuplicateKeyError as e:
            logger.error(str(e))
            print(e)
        except Exception as e:
            logger.error(str(e))
            print("An error occurred during insertion.")

    def search(self, key):
        if self.index_file is None:
            print("Error: No index file is open.")
            return
        try:
            if self.root:
                value = self.root.search_key(key)
                if value is not None:
                    print(f"Found key {key} with value {value}.")
                else:
                    print(f"Key {key} not found.")
            else:
                print("The B-tree is empty.")
        except Exception as e:
            logger.error(str(e))
            print("An error occurred during search.")

    def load_data(self, filename):
        if self.index_file is None:
            print("Error: No index file is open.")
            return
        if not os.path.exists(filename):
            print(f"Error: File '{filename}' does not exist.")
            return
        try:
            with open(filename, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(',')
                    if len(parts) != 2:
                        print(f"Invalid line: {line}")
                        continue
                    try:
                        key = int(parts[0].strip())
                        value = int(parts[1].strip())
                        self.insert(key, value)
                    except ValueError:
                        print(f"Invalid key/value: {line}")
                        continue
            print(f"Data loaded from '{filename}'.")
        except IOError as e:
            logger.error(str(e))
            print("Error loading data from file.")

    def print_all(self):
        if self.index_file is None:
            print("Error: No index file is open.")
            return
        if self.root:
            print("All key-value pairs in the B-tree:")
            self.root.traverse()
        else:
            print("The B-tree is empty.")

    def extract_to_file(self, filename):
        if self.index_file is None:
            print("Error: No index file is open.")
            return
        try:
            with open(filename, 'w') as f:
                if self.root:
                    self.root.traverse(f)
                else:
                    print("The B-tree is empty.")
            print(f"Data extracted to '{filename}'.")
        except IOError as e:
            logger.error(str(e))
            print("Error extracting data to file.")

class BTreeNode:
    def __init__(self, index_manager, is_leaf=False, offset=None):
        self.index_manager = index_manager
        self.is_leaf = is_leaf
        self.keys = []
        self.values = []
        self.children = []
        self.offset = offset if offset is not None else self.allocate_offset()
        if offset is not None:
            self.load()

    def allocate_offset(self):
        try:
            with open(self.index_manager.index_file, 'ab') as f:
                pos = f.tell()
                f.write(b'\x00' * BLOCK_SIZE)
            return pos
        except IOError as e:
            logger.error(str(e))
            print("Error allocating space for node.")
            return 0

    def save(self):
        try:
            data = struct.pack('>?I', self.is_leaf, len(self.keys))
            for key in self.keys:
                data += struct.pack('>I', key)
            for val in self.values:
                data += struct.pack('>I', val)
            for child in self.children:
                data += struct.pack('>Q', child)
            data += b'\x00' * (BLOCK_SIZE - len(data))
            with open(self.index_manager.index_file, 'r+b') as f:
                f.seek(self.offset)
                f.write(data)
        except IOError as e:
            logger.error(str(e))
            print("Error saving node.")

    def load(self):
        try:
            with open(self.index_manager.index_file, 'rb') as f:
                f.seek(self.offset)
                block_data = f.read(BLOCK_SIZE)
            self.is_leaf, num_keys = struct.unpack('>?I', block_data[:5])
            offset = 5
            self.keys = [struct.unpack('>I', block_data[offset + i*4 : offset + (i+1)*4])[0] for i in range(num_keys)]
            offset += num_keys * 4
            self.values = [struct.unpack('>I', block_data[offset + i*4 : offset + (i+1)*4])[0] for i in range(num_keys)]
            offset += num_keys * 4
            if not self.is_leaf:
                num_children = num_keys + 1
                self.children = [struct.unpack('>Q', block_data[offset + i*8 : offset + (i+1)*8])[0] for i in range(num_children)]
        except IOError as e:
            logger.error(str(e))
            print("Error loading node.")

    def insert_non_full(self, key, value):
        try:
            i = len(self.keys) - 1
            if self.is_leaf:
                self.keys.append(0)
                self.values.append(0)
                while i >= 0 and key < self.keys[i]:
                    self.keys[i+1] = self.keys[i]
                    self.values[i+1] = self.values[i]
                    i -= 1
                if i >= 0 and key == self.keys[i]:
                    raise DuplicateKeyError(f"Error: Duplicate key {key}.")
                self.keys[i+1] = key
                self.values[i+1] = value
                self.save()
            else:
                while i >= 0 and key < self.keys[i]:
                    i -= 1
                i += 1
                child = BTreeNode(self.index_manager, offset=self.children[i])
                if len(child.keys) == 2 * MIN_DEGREE - 1:
                    self.split_child(i, child)
                    if key > self.keys[i]:
                        i += 1
                child = BTreeNode(self.index_manager, offset=self.children[i])
                child.insert_non_full(key, value)
        except DuplicateKeyError as e:
            raise e
        except Exception as e:
            logger.error(str(e))
            print("An error occurred during insertion.")

    def split_child(self, index, child):
        try:
            new_child = BTreeNode(self.index_manager, is_leaf=child.is_leaf)
            mid = MIN_DEGREE - 1
            new_child.keys = child.keys[mid+1:]
            new_child.values = child.values[mid+1:]
            if not child.is_leaf:
                new_child.children = child.children[mid+1:]
            # Reduce the original child
            child.keys = child.keys[:mid]
            child.values = child.values[:mid]
            if not child.is_leaf:
                child.children = child.children[:mid+1]

            self.keys.insert(index, child.keys[mid])
            self.values.insert(index, child.values[mid])
            self.children.insert(index+1, new_child.offset)

            # Write changes to disk
            child.save()
            new_child.save()
            self.save()
        except Exception as e:
            logger.error(str(e))
            print("Error splitting child node.")

    def search_key(self, key):
        i = 0
        while i < len(self.keys) and key > self.keys[i]:
            i += 1
        if i < len(self.keys) and key == self.keys[i]:
            return self.values[i]
        elif self.is_leaf:
            return None
        else:
            child = BTreeNode(self.index_manager, offset=self.children[i])
            return child.search_key(key)

    def traverse(self, output_file=None):
        # In-order traversal of the B-tree
        for i in range(len(self.keys)):
            if not self.is_leaf:
                child = BTreeNode(self.index_manager, offset=self.children[i])
                child.traverse(output_file)
            entry = f"{self.keys[i]},{self.values[i]}"
            if output_file:
                output_file.write(entry + "\n")
            else:
                print(entry)
        if not self.is_leaf:
            child = BTreeNode(self.index_manager, offset=self.children[-1])
            child.traverse(output_file)

def main():
    manager = IndexManager()
    print("Welcome to the B-Tree Index Manager. Type 'help' for a list of commands.")
    while True:
        cmd = input("Command> ").strip().lower()
        if cmd in ('exit', 'quit'):
            print("Exiting.")
            break
        elif cmd.startswith('create '):
            parts = cmd.split(maxsplit=1)
            if len(parts) != 2:
                print("Usage: create <filename>")
                continue
            manager.create_index_file(parts[1])
        elif cmd.startswith('open '):
            parts = cmd.split(maxsplit=1)
            if len(parts) != 2:
                print("Usage: open <filename>")
                continue
            manager.open_index_file(parts[1])
        elif cmd.startswith('insert '):
            parts = cmd.split()
            if len(parts) != 3:
                print("Usage: insert <key> <value>")
                continue
            try:
                key = int(parts[1])
                value = int(parts[2])
                manager.insert(key, value)
            except ValueError:
                print("Error: Key and value must be integers.")
        elif cmd.startswith('search '):
            parts = cmd.split()
            if len(parts) != 2:
                print("Usage: search <key>")
                continue
            try:
                key = int(parts[1])
                manager.search(key)
            except ValueError:
                print("Error: Key must be an integer.")
        elif cmd.startswith('load '):
            parts = cmd.split(maxsplit=1)
            if len(parts) != 2:
                print("Usage: load <filename>")
                continue
            manager.load_data(parts[1])
        elif cmd == 'print':
            manager.print_all()
        elif cmd.startswith('extract '):
            parts = cmd.split(maxsplit=1)
            if len(parts) != 2:
                print("Usage: extract <filename>")
                continue
            manager.extract_to_file(parts[1])
        elif cmd == 'help':
            print("Available commands:")
            print("  create <filename>      - Create a new index file")
            print("  open <filename>        - Open an existing index file")
            print("  insert <key> <value>   - Insert a key-value pair")
            print("  search <key>           - Search for a key")
            print("  load <filename>        - Load key-value pairs from a file")
            print("  print                  - Print all key-value pairs in the B-tree")
            print("  extract <filename>     - Extract all key-value pairs to a file")
            print("  quit or exit           - Exit the program")
        else:
            print("Unknown command. Type 'help' for a list of commands.")

if __name__ == '__main__':
    main()