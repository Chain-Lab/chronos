import binascii

from utils.funcs import sum256_byte


class MerkleNode(object):
    def __init__(self, data, left_node=None, right_node=None):
        self.left = left_node
        self.right = right_node

        if not self.left and not self.right:
            self.data = sum256_byte(data)
            return

        self.data = self.left.data + self.right.data
        self.data = sum256_byte(self.data)


class MerkleTree(object):
    def __init__(self, datas):
        nodes = []
        for item in datas:
            node = MerkleNode(item)
            nodes.append(node)

        for _ in range(len(datas) // 2):
            new_level = []
            for j in range(0, len(nodes), 2):
                if j + 1 >= len(nodes):
                    node = MerkleNode(None, nodes[j], "")
                else:
                    node = MerkleNode(None, nodes[j], nodes[j + 1])
                new_level.append(node)
            nodes = new_level
        self.root_node = nodes[0]

    @property
    def root_hash(self):
        return binascii.b2a_hex(self.root_node.data).decode()
