import os
import struct
import sys

BLOCK_SIZE = 512
MAGIC_HEADER = b'BTREEIDX'  # Unique header identifier
MIN_DEGREE = 4  # Minimum degree for the B-tree

class IndexManager:
    """Manages the index file and B-tree operations."""

    def __init__(self):
        self.index_file = None
        self.root = None

    def create_index_file(self, filename):
        """Creates a new index file with an empty B-tree."""
        if os.path.exists(filename):
            choice = input(f"File '{filename}' already exists. Overwrite? (y/n): ").lower()
            if choice != 'y':
                print("Operation cancelled.")
                return
        with open(filename, 'wb') as f:
            f.write(MAGIC_HEADER)
            f.write(struct.pack('>Q', 0))  # Root node offset (0 indicates empty tree)
            f.write(b'\x00' * (BLOCK_SIZE - len(MAGIC_HEADER) - 8))
        print(f"Index file '{filename}' created.")

    def open_index_file(self, filename):
        """Opens an existing index file and loads the B-tree root."""
        if not os.path.exists(filename):
            print(f"Error: File '{filename}' does not exist.")
            return
        with open(filename, 'rb') as f:
            magic = f.read(len(MAGIC_HEADER))
            if magic != MAGIC_HEADER:
                print("Error: Not a valid index file.")
                return
            root_offset = struct.unpack('>Q', f.read(8))[0]
            self.root = BTreeNode(self, offset=root_offset) if root_offset != 0 else None
        self.index_file = filename
        print(f"Index file '{filename}' opened.")

    def insert(self, key, value):
        """Inserts a key-value pair into the B-tree."""
        if self.index_file is None:
            print("Error: No index file is open.")
            return
        if self.root is None:
            self.root = BTreeNode(self, is_leaf=True)
            self.root.keys.append(key)
            self.root.values.append(value)
            self.root.save()
            self.update_root_offset(self.root.offset)
        else:
            if len(self.root.keys) == 2 * MIN_DEGREE - 1:
                new_root = BTreeNode(self, is_leaf=False)
                new_root.children.append(self.root.offset)
                new_root.split_child(0, self.root)
                self.root = new_root
                self.update_root_offset(self.root.offset)
            self.root.insert_non_full(key, value)
        print(f"Inserted key {key}.")

    def update_root_offset(self, offset):
        """Updates the root node offset in the index file header."""
        with open(self.index_file, 'r+b') as f:
            f.seek(len(MAGIC_HEADER))
            f.write(struct.pack('>Q', offset))

class BTreeNode:
    """Represents a node within the B-tree."""

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
        """Allocates space in the index file for a new node."""
        with open(self.index_manager.index_file, 'ab') as f:
            offset = f.tell()
            f.write(b'\x00' * BLOCK_SIZE)
        return offset

    def save(self):
        """Saves the node to the index file."""
        data = struct.pack('>?I', self.is_leaf, len(self.keys))
        data += b''.join(struct.pack('>I', key) for key in self.keys)
        data += b''.join(struct.pack('>I', value) for value in self.values)
        data += b''.join(struct.pack('>Q', child) for child in self.children)
        data += b'\x00' * (BLOCK_SIZE - len(data))
        with open(self.index_manager.index_file, 'r+b') as f:
            f.seek(self.offset)
            f.write(data)

    def load(self):
        """Loads the node from the index file."""
        with open(self.index_manager.index_file, 'rb') as f:
            f.seek(self.offset)
            data = f.read(BLOCK_SIZE)
        self.is_leaf, num_keys = struct.unpack('>?I', data[:5])
        offset = 5
        self.keys = [struct.unpack('>I', data[offset + i * 4: offset + (i + 1) * 4])[0] for i in range(num_keys)]
        offset += num_keys * 4
        self.values = [struct.unpack('>I', data[offset + i * 4: offset + (i + 1) * 4])[0] for i in range(num_keys)]
        offset += num_keys * 4
        if not self.is_leaf:
            num_children = num_keys + 1
            self.children = [struct.unpack('>Q', data[offset + i * 8: offset + (i + 1) * 8])[0] for i in range(num_children)]

    def insert_non_full(self, key, value):
        """Inserts a key-value pair into a node that is not full."""
        i = len(self.keys) - 1
        if self.is_leaf:
            self.keys.append(0)
            self.values.append(0)
            while i >= 0 and key < self.keys[i]:
                self.keys[i + 1] = self.keys[i]
                self.values[i + 1] = self.values[i]
                i -= 1
            if i >= 0 and key == self.keys[i]:
                print(f"Error: Duplicate key {key}.")
                return
            self.keys[i + 1] = key
            self.values[i + 1] = value
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

    def split_child(self, index, child):
        """Splits a full child node into two nodes."""
        new_child = BTreeNode(self.index_manager, is_leaf=child.is_leaf)
        mid = MIN_DEGREE - 1
        new_child.keys = child.keys[mid + 1:]
        new_child.values = child.values[mid + 1:]
        if not child.is_leaf:
            new_child.children = child.children[mid + 1:]
        child.keys = child.keys[:mid]
        child.values = child.values[:mid]
        if not child.is_leaf:
            child.children = child.children[:mid + 1]
        self.keys.insert(index, child.keys[mid])
        self.values.insert(index, child.values[mid])
        self.children.insert(index + 1, new_child.offset)
        child.save()
        new_child.save()
        self.save()

def main():
    """Main function to run the index manager."""
    manager = IndexManager()
    print("Welcome to the B-Tree Index Manager. Type 'help' for a list of commands.")
    while True:
        cmd = input("Command> ").strip().lower()
        if cmd in ('exit', 'quit'):
            print("Exiting.")
            break
        elif cmd.startswith('create '):
            parts = cmd.split()
            if len(parts) != 2:
                print("Usage: create <filename>")
                continue
            manager.create_index_file(parts[1])
        elif cmd.startswith('open '):
            parts = cmd.split()
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
        elif cmd == 'help':
            print("Available commands:")
            print("  create <filename> - Create a new index file")
            print("  open <filename>   - Open an existing index file")
            print("  insert <key> <value> - Insert a key-value pair")
            print("  quit or exit      - Exit the program")
        else:
            print("Unknown command. Type 'help' for a list of commands.")

if __name__ == '__main__':
    main()