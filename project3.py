import os
import struct
import sys

BLOCK_SIZE = 512
MAGIC_NUMBER = b'BTREE_IDX'
MIN_DEGREE = 3  # Adjusted for simplicity

class IndexManager:
    def __init__(self):
        self.filename = None
        self.file = None
        self.root = None

    def create_index(self, filename):
        if os.path.exists(filename):
            choice = input(f"File '{filename}' exists. Overwrite? (y/n): ").lower()
            if choice != 'y':
                print("Operation canceled.")
                return
        with open(filename, 'wb') as f:
            f.write(MAGIC_NUMBER)
            f.write(struct.pack('>Q', 0))  # Root node position
            f.write(b'\x00' * (BLOCK_SIZE - len(MAGIC_NUMBER) - 8))
        print(f"Index file '{filename}' created.")

    def open_index(self, filename):
        if not os.path.exists(filename):
            print(f"File '{filename}' not found.")
            return
        self.filename = filename
        with open(filename, 'rb') as f:
            magic = f.read(len(MAGIC_NUMBER))
            if magic != MAGIC_NUMBER:
                print("Invalid index file.")
                self.filename = None
                return
            root_pos = struct.unpack('>Q', f.read(8))[0]
        self.root = BTreeNode(self, position=root_pos) if root_pos else None
        print(f"Index file '{filename}' opened.")

    def insert(self, key, value):
        if not self.filename:
            print("No index file is open.")
            return
        if self.root is None:
            self.root = BTreeNode(self, is_leaf=True)
            self.root.keys.append(key)
            self.root.values.append(value)
            self.root.write_node()
            self.update_root(self.root.position)
        else:
            if self.root.is_full():
                new_root = BTreeNode(self, is_leaf=False)
                new_root.children.append(self.root.position)
                new_root.split_child(0, self.root)
                self.root = new_root
                self.update_root(self.root.position)
            self.root.insert_non_full(key, value)
        print(f"Key {key} inserted.")

    def update_root(self, position):
        with open(self.filename, 'r+b') as f:
            f.seek(len(MAGIC_NUMBER))
            f.write(struct.pack('>Q', position))

class BTreeNode:
    def __init__(self, manager, is_leaf=False, position=None):
        self.manager = manager
        self.is_leaf = is_leaf
        self.keys = []
        self.values = []
        self.children = []
        self.position = position if position is not None else self.allocate_position()

        if position is not None:
            self.read_node()

    def allocate_position(self):
        with open(self.manager.filename, 'ab') as f:
            pos = f.tell()
            f.write(b'\x00' * BLOCK_SIZE)
        return pos

    def write_node(self):
        data = bytearray()
        data.extend(struct.pack('>?', self.is_leaf))
        data.extend(struct.pack('>I', len(self.keys)))
        for key in self.keys:
            data.extend(struct.pack('>I', key))
        for value in self.values:
            data.extend(struct.pack('>I', value))
        for child in self.children:
            data.extend(struct.pack('>Q', child))
        data.extend(b'\x00' * (BLOCK_SIZE - len(data)))
        with open(self.manager.filename, 'r+b') as f:
            f.seek(self.position)
            f.write(data)

    def read_node(self):
        with open(self.manager.filename, 'rb') as f:
            f.seek(self.position)
            data = f.read(BLOCK_SIZE)
        self.is_leaf = struct.unpack('>?', data[:1])[0]
        num_keys = struct.unpack('>I', data[1:5])[0]
        offset = 5
        self.keys = [struct.unpack('>I', data[offset + i*4: offset + (i+1)*4])[0] for i in range(num_keys)]
        offset += num_keys * 4
        self.values = [struct.unpack('>I', data[offset + i*4: offset + (i+1)*4])[0] for i in range(num_keys)]
        offset += num_keys * 4
        if not self.is_leaf:
            self.children = [struct.unpack('>Q', data[offset + i*8: offset + (i+1)*8])[0] for i in range(num_keys + 1)]

    def is_full(self):
        return len(self.keys) == (2 * MIN_DEGREE - 1)

    def insert_non_full(self, key, value):
        i = len(self.keys) - 1
        if self.is_leaf:
            self.keys.append(0)
            self.values.append(0)
            while i >= 0 and key < self.keys[i]:
                self.keys[i+1] = self.keys[i]
                self.values[i+1] = self.values[i]
                i -= 1
            if i >= 0 and key == self.keys[i]:
                print(f"Key {key} already exists.")
                return
            self.keys[i+1] = key
            self.values[i+1] = value
            self.write_node()
        else:
            while i >= 0 and key < self.keys[i]:
                i -= 1
            i += 1
            child = BTreeNode(self.manager, position=self.children[i])
            if child.is_full():
                self.split_child(i, child)
                if key > self.keys[i]:
                    i += 1
            child.insert_non_full(key, value)

    def split_child(self, index, node):
        new_node = BTreeNode(self.manager, is_leaf=node.is_leaf)
        mid = MIN_DEGREE - 1
        new_node.keys = node.keys[mid+1:]
        new_node.values = node.values[mid+1:]
        if not node.is_leaf:
            new_node.children = node.children[mid+1:]
        node.keys = node.keys[:mid]
        node.values = node.values[:mid]
        node.children = node.children[:mid+1] if not node.is_leaf else []
        self.keys.insert(index, node.keys[mid])
        self.values.insert(index, node.values[mid])
        self.children.insert(index+1, new_node.position)
        node.write_node()
        new_node.write_node()
        self.write_node()

def main():
    manager = IndexManager()
    print("B-Tree Index Manager. Type 'help' for commands.")
    while True:
        cmd = input(">>> ").strip().lower()
        if cmd == 'exit' or cmd == 'quit':
            print("Exiting.")
            break
        elif cmd.startswith('create'):
            _, filename = cmd.split()
            manager.create_index(filename)
        elif cmd.startswith('open'):
            _, filename = cmd.split()
            manager.open_index(filename)
        elif cmd.startswith('insert'):
            parts = cmd.split()
            if len(parts) != 3:
                print("Usage: insert <key> <value>")
                continue
            key, value = int(parts[1]), int(parts[2])
            manager.insert(key, value)
        elif cmd == 'help':
            print("Commands: create <file>, open <file>, insert <key> <value>, quit")
        else:
            print("Unknown command. Type 'help' for a list of commands.")

if __name__ == '__main__':
    main()