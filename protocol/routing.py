import heapq
import operator
import random

from kademlia.routing import RoutingTable, KBucket
from utils.funcs import shared_prefix


class KBucketV2(KBucket):
    def __init__(self, ksize, replacementNodeFactor=5):
        super().__init__(-1, -1, ksize, replacementNodeFactor)

    def split(self, common_prefix_length=-1, target=b''):
        out = KBucketV2(self.ksize)
        for node_id in list(self.nodes.keys()):
            cur = self.nodes[node_id]
            cur_common_prefix_length = shared_prefix(node_id, target)
            if cur_common_prefix_length > common_prefix_length:
                out.nodes[node_id] = cur
                self.nodes.pop(node_id)
        return out

    def remove_node(self, node):
        if node.id in self.replacement_nodes:
            self.replacement_nodes.pop(node.id)
            return True

        if node.id in self.nodes:
            self.nodes.pop(node.id)

            if self.replacement_nodes:
                newnode_id, newnode = self.replacement_nodes.popitem()
                self.nodes[newnode_id] = newnode

            return True

        return False

    def select_node(self):
        return random.choice(self.get_nodes())


class RoutingTableV2(RoutingTable):
    def __init__(self, protocol, ksize, node):
        super().__init__(protocol, ksize, node)

    def flush(self):
        self.buckets = [KBucketV2(self.ksize) for _ in range(160)]

    def get_bucket_for(self, node):
        """
        Calculate common prefix length to get the target bucket index
        :param node: Another node which need to search
        :return: Target bucket index
        """
        bucket_index = shared_prefix(self.node.id, node.id)

        if bucket_index >= len(self.buckets):
            bucket_index = len(self.buckets) - 1

        return bucket_index

    def add_contact(self, node):
        # 如果超过bucket的容量会把节点丢弃， 这里后面再看怎么维护
        bucket_index = self.get_bucket_for(node)
        bucket = self.buckets[bucket_index]

        # bucket_nodes = bucket.get_nodes()

        if bucket.add_node(node):
            return

        if bucket_index == len(self.buckets) - 1:
            self.next_bucket()
            bucket_index = self.get_bucket_for(node)
            bucket = self.buckets[bucket_index]

            bucket.add_node(node)

    def next_bucket(self):
        bucket = self.buckets[-1]
        new_bucket = bucket.split(len(self.buckets) - 1, self.node.id)
        self.buckets.append(new_bucket)

        if len(new_bucket) >= self.ksize:
            self.next_bucket()

    def remove_contact(self, node):
        bucket_index = self.get_bucket_for(node)
        bucket = self.buckets[bucket_index]

        if bucket.remove_node(node):
            while True:
                lastBucketIndex = len(self.buckets) - 1

                if len(self.buckets) > 1 and len(self.buckets[lastBucketIndex]) == 0:
                    self.buckets.pop()
                elif len(self.buckets) >= 2 and len(self.buckets[lastBucketIndex - 1]) == 0:
                    self.buckets.pop()
                    self.buckets.pop()
                else:
                    break

            return True
        return False

    def find_neighbors(self, node, k=None, exclude=None):
        common_prefix_length = shared_prefix(self.node.id, node.id)

        if common_prefix_length >= len(self.buckets):
            common_prefix_length = len(self.buckets) - 1

        k = k or self.ksize
        nodes = []

        bucket_nodes = self.buckets[common_prefix_length].get_nodes()
        for neighbor in bucket_nodes:
            heapq.heappush(nodes, (node.distance_to(neighbor), neighbor))

        if len(nodes) < k:
            for i in range(common_prefix_length + 1, len(self.buckets)):
                bucket_nodes = self.buckets[i].get_nodes()
                for neighbor in bucket_nodes:
                    heapq.heappush(nodes, (node.distance_to(neighbor), neighbor))

        for i in range(common_prefix_length - 1, 0, -1):
            if len(nodes) >= k:
                break

            bucket_nodes = self.buckets[i].get_nodes()

            for neighbor in bucket_nodes:
                heapq.heappush(nodes, (node.distance_to(neighbor), neighbor))
                if len(nodes) >= k:
                    break

        return list(map(operator.itemgetter(1), heapq.nsmallest(k, nodes)))
